"""OIDC relying-party flow: Google sign-in through Dex.

Dex (issuer https://assets.longstraw.earth/dex) already carries the Google
connector, so ConeShare only acts as an OIDC client:

  /api/v1/oidc/login/   -> signs state+nonce+PKCE verifier into a short-lived
                           cookie and redirects the browser to Dex
  Dex                    -> Google (or Dex local login for tests)
  /api/v1/oidc/callback/-> exchanges the code, verifies the id_token against
                           Dex JWKS, provisions the user, then redirects to the
                           SPA /auth/callback with the JWTs in the URL fragment
                           so they never reach server access logs.
"""

import base64
import hashlib
import logging
import secrets
from urllib.parse import urlencode

import jwt as pyjwt
import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in
from django.core import signing
from django.http import HttpResponse
from django.shortcuts import redirect
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import Organization

User = get_user_model()

logger = logging.getLogger(__name__)

STATE_COOKIE = 'coneshare_oidc_state'
STATE_SALT = 'core.oidc'
STATE_MAX_AGE = 600


class OIDCError(Exception):
    """Any failure in the RP flow. Always ends in a friendly redirect."""


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b'=').decode('ascii')


def _frontend_url(path: str, params: dict) -> str:
    return f"{settings.SITE_DOMAIN.rstrip('/')}{path}#{urlencode(params)}"


def _failure(error: str) -> HttpResponse:
    return redirect(_frontend_url('/auth/callback', {'error': error}))


def _decode_id_token(id_token: str, nonce: str) -> dict:
    """Verify signature + standard claims, then match our nonce.

    Split out from the view so tests can exercise the surrounding flow with a
    mocked verifier while the real crypto path stays exercised elsewhere.
    """
    jwks = pyjwt.PyJWKClient(settings.OIDC_JWKS_URL, cache_jwk_set=True, cache_keys=True)
    try:
        key = jwks.get_signing_key_from_jwt(id_token)
        claims = pyjwt.decode(
            id_token,
            key.key,
            algorithms=['RS256'],
            audience=settings.OIDC_CLIENT_ID,
            issuer=settings.OIDC_ISSUER,
            options={'require': ['exp', 'iat', 'iss', 'aud']},
        )
    except pyjwt.PyJWKClientError as exc:
        raise OIDCError('invalid_key') from exc
    except pyjwt.InvalidTokenError as exc:
        logger.warning('OIDC id_token rejected: %s', exc.__class__.__name__)
        raise OIDCError('invalid_token') from exc
    if claims.get('nonce') != nonce:
        raise OIDCError('invalid_nonce')
    return claims


def _exchange_code(code: str, code_verifier: str) -> dict:
    try:
        response = requests.post(
            settings.OIDC_TOKEN_URL,
            data={
                'grant_type': 'authorization_code',
                'code': code,
                'redirect_uri': settings.OIDC_REDIRECT_URI,
                'client_id': settings.OIDC_CLIENT_ID,
                'client_secret': settings.OIDC_CLIENT_SECRET,
                'code_verifier': code_verifier,
            },
            timeout=15,
        )
    except requests.RequestException as exc:
        logger.warning('OIDC token endpoint unreachable: %s', exc.__class__.__name__)
        raise OIDCError('token_endpoint_unreachable') from exc
    if response.status_code != 200:
        # Never log the body: it can carry tokens.
        logger.warning('OIDC token exchange failed with HTTP %s', response.status_code)
        raise OIDCError('token_exchange_failed')
    try:
        payload = response.json()
    except ValueError as exc:
        raise OIDCError('token_exchange_failed') from exc
    if not payload.get('id_token'):
        raise OIDCError('missing_id_token')
    return payload


def _provision_user(email: str, name: str = '') -> User:
    """Find the account for this email, creating an ordinary member on first use."""
    email = email.strip().lower()
    user = User.objects.filter(email__iexact=email).first()
    if user:
        if not user.is_active:
            user.is_active = True
            user.updated_at = timezone.now()
            user.save(update_fields=['is_active', 'updated_at'])
        return user
    try:
        return User.objects.create_user(
            username=email,
            email=email,
            password=None,
            name=(name or '').strip(),
            is_active=True,
        )
    except RuntimeError as exc:
        raise OIDCError('no_default_organization') from exc


class OIDCLoginView(APIView):
    """Start the authorization-code + PKCE flow at Dex."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request):
        if not settings.OIDC_LOGIN_ENABLED:
            return Response({'detail': 'Single sign-on is not configured.'},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)

        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        params = {
            'client_id': settings.OIDC_CLIENT_ID,
            'response_type': 'code',
            'scope': settings.OIDC_SCOPES,
            'redirect_uri': settings.OIDC_REDIRECT_URI,
            'state': state,
            'nonce': nonce,
            'code_challenge': _b64url(hashlib.sha256(verifier.encode('ascii')).digest()),
            'code_challenge_method': 'S256',
        }
        # Google-first: the longstraw.earth button deep-links Dex's Google
        # connector (/dex/auth/google) so users never see the connector picker.
        response = redirect(f'{settings.OIDC_AUTHORIZE_URL}/google?{urlencode(params)}')
        response.set_cookie(
            STATE_COOKIE,
            signing.dumps({'state': state, 'nonce': nonce, 'verifier': verifier}, salt=STATE_SALT),
            max_age=STATE_MAX_AGE,
            httponly=True,
            samesite='Lax',
            secure=settings.SITE_DOMAIN.startswith('https'),
            path='/',
        )
        return response


class OIDCCallbackView(APIView):
    """Land back from Dex: verify, provision, then hand the JWTs to the SPA."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request):
        if request.GET.get('error'):
            logger.warning('OIDC provider reported error: %s', request.GET.get('error'))
            return _failure('idp_error')

        code = request.GET.get('code')
        state = request.GET.get('state')
        raw_state = request.COOKIES.get(STATE_COOKIE)
        if not code or not state or not raw_state:
            return _failure('missing_parameters')

        try:
            stored = signing.loads(raw_state, salt=STATE_SALT, max_age=STATE_MAX_AGE)
        except signing.BadSignature:
            return _failure('invalid_state')
        if not isinstance(stored, dict) or stored.get('state') != state:
            return _failure('state_mismatch')

        try:
            payload = _exchange_code(code, stored.get('verifier', ''))
            claims = _decode_id_token(payload['id_token'], stored.get('nonce'))
        except (OIDCError, KeyError) as exc:
            logger.warning('OIDC callback rejected: %s', exc)
            return _failure(str(exc) if isinstance(exc, OIDCError) else 'invalid_token')

        email = (claims.get('email') or '').strip()
        if not email:
            return _failure('missing_email')

        try:
            user = _provision_user(email, claims.get('name') or '')
        except OIDCError as exc:
            logger.warning('OIDC provisioning failed: %s', exc)
            return _failure(str(exc))

        refresh = RefreshToken.for_user(user)
        user_logged_in.send(sender=User, request=request, user=user)

        response = redirect(_frontend_url('/auth/callback', {
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        }))
        response.delete_cookie(STATE_COOKIE, path='/')
        return response
