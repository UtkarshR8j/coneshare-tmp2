"""OIDC relying-party tests (Dex as identity provider, mocked at the wire)."""

from urllib.parse import parse_qs, urlparse

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from core.oidc_views import OIDCError
from core.models import Organization

User = get_user_model()

ISSUER = 'https://assets.longstraw.earth/dex'
REDIRECT_URI = 'https://dev.dataroom.longstraw.earth/api/v1/oidc/callback/'


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def oidc_env(settings):
    settings.OIDC_LOGIN_ENABLED = True
    settings.OIDC_CLIENT_ID = 'coneshare-dev'
    settings.OIDC_CLIENT_SECRET = 'test-secret-value'
    settings.OIDC_ISSUER = ISSUER
    settings.OIDC_SCOPES = 'openid profile email'
    settings.OIDC_AUTHORIZE_URL = f'{ISSUER}/auth'
    settings.OIDC_TOKEN_URL = f'{ISSUER}/token'
    settings.OIDC_JWKS_URL = f'{ISSUER}/keys'
    settings.OIDC_REDIRECT_URI = REDIRECT_URI
    return settings


def _begin(client):
    """Walk the login endpoint, returning (state, nonce) from the Dex redirect."""
    response = client.get(reverse('oidc_login'))
    assert response.status_code == status.HTTP_302_FOUND
    location = response['Location']
    assert location.startswith(f'{ISSUER}/auth?')
    query = parse_qs(urlparse(location).query)
    assert query['client_id'] == ['coneshare-dev']
    assert query['response_type'] == ['code']
    assert query['code_challenge_method'] == ['S256']
    assert query['redirect_uri'] == [REDIRECT_URI]
    assert response.cookies.get('coneshare_oidc_state') is not None
    return query['state'][0], query['nonce'][0]


def _callback(client, state, code='auth-code'):
    return client.get(reverse('oidc_callback'), {'code': code, 'state': state})


def _error_of(response):
    fragment = urlparse(response['Location']).fragment
    return parse_qs(fragment).get('error', [None])[0]


@pytest.mark.django_db
def test_login_redirects_to_dex_with_pkce(client, oidc_env):
    _begin(client)


@pytest.mark.django_db
def test_login_is_disabled_without_client_credentials(client, settings):
    settings.OIDC_LOGIN_ENABLED = False
    response = client.get(reverse('oidc_login'))
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


@pytest.mark.django_db
def test_state_mismatch_is_rejected(client, oidc_env, monkeypatch):
    state, _nonce = _begin(client)

    def _should_not_run(*args, **kwargs):
        raise AssertionError('token exchange must not run on a state mismatch')

    monkeypatch.setattr('core.oidc_views._exchange_code', _should_not_run)
    response = _callback(client, 'tampered-state')
    assert response.status_code == status.HTTP_302_FOUND
    assert _error_of(response) == 'state_mismatch'
    assert User.objects.filter(email__iexact='sso@example.com').exists() is False


@pytest.mark.django_db
def test_callback_without_state_cookie_is_rejected(client, oidc_env):
    client.cookies.clear()
    response = client.get(reverse('oidc_callback'), {'code': 'c', 'state': 's'})
    assert response.status_code == status.HTTP_302_FOUND
    assert _error_of(response) == 'missing_parameters'


@pytest.mark.django_db
def test_bad_signature_is_rejected(client, oidc_env, monkeypatch):
    state, _nonce = _begin(client)
    monkeypatch.setattr(
        'core.oidc_views._exchange_code',
        lambda code, verifier: {'id_token': 'forged-token'},
    )
    monkeypatch.setattr(
        'core.oidc_views._decode_id_token',
        lambda id_token, nonce: (_ for _ in ()).throw(OIDCError('invalid_token')),
    )
    response = _callback(client, state)
    assert response.status_code == status.HTTP_302_FOUND
    assert _error_of(response) == 'invalid_token'
    assert User.objects.filter(email__iexact='sso@example.com').exists() is False


@pytest.mark.django_db
def test_happy_path_returns_the_same_jwt_shape_as_password_login(
    client, user, oidc_env, monkeypatch
):
    state, nonce = _begin(client)
    captured = {}

    def fake_exchange(code, code_verifier):
        captured['exchange'] = {'code': code, 'verifier': code_verifier}
        return {'access_token': 'at', 'id_token': 'signed-token', 'token_type': 'Bearer'}

    def fake_decode(id_token, nonce_arg):
        captured['nonce'] = nonce_arg
        return {'email': user.email, 'name': user.name, 'nonce': nonce_arg}

    monkeypatch.setattr('core.oidc_views._exchange_code', fake_exchange)
    monkeypatch.setattr('core.oidc_views._decode_id_token', fake_decode)

    response = _callback(client, state)
    assert response.status_code == status.HTTP_302_FOUND

    fragment = parse_qs(urlparse(response['Location']).fragment)
    assert fragment['access'], 'access token missing from the redirect fragment'
    assert fragment['refresh'], 'refresh token missing from the redirect fragment'
    assert captured['exchange']['code'] == 'auth-code'
    assert captured['exchange']['verifier']
    assert captured['nonce'] == nonce

    # Same contract the password login returns.
    password = APIClient().post(reverse('token_obtain_pair'),
                                {'email': user.email, 'password': 'password'})
    assert password.status_code == status.HTTP_200_OK
    assert set(fragment) >= set(password.data)

    # The state cookie is consumed exactly once: delete_cookie() sends an
    # empty replacement morsel on the redirect.
    assert response.cookies['coneshare_oidc_state'].value == ''


@pytest.mark.django_db
def test_first_login_autoprovisions_an_active_non_admin_user(
    client, oidc_env, monkeypatch
):
    state, nonce = _begin(client)
    monkeypatch.setattr(
        'core.oidc_views._exchange_code',
        lambda code, verifier: {'id_token': 'signed-token'},
    )
    monkeypatch.setattr(
        'core.oidc_views._decode_id_token',
        lambda id_token, nonce_arg: {
            'email': 'New.SSO.User@Example.com',
            'name': 'New SSO User',
            'nonce': nonce_arg,
        },
    )

    response = _callback(client, state)
    assert response.status_code == status.HTTP_302_FOUND
    assert _error_of(response) is None

    created = User.objects.get(email='new.sso.user@example.com')
    assert created.is_active is True
    assert created.is_superuser is False
    assert created.is_staff is False
    assert created.role == 'member'
    assert created.organization_id == Organization.objects.first().id
    assert created.has_usable_password() is False

    fragment = parse_qs(urlparse(response['Location']).fragment)
    assert fragment['access'][0]


@pytest.mark.django_db
def test_second_login_finds_the_existing_user(client, user, oidc_env, monkeypatch):
    monkeypatch.setattr(
        'core.oidc_views._exchange_code',
        lambda code, verifier: {'id_token': 'signed-token'},
    )
    monkeypatch.setattr(
        'core.oidc_views._decode_id_token',
        lambda id_token, nonce_arg: {'email': user.email, 'name': '', 'nonce': nonce_arg},
    )

    before = User.objects.count()
    for _ in range(2):
        state, _nonce = _begin(client)
        response = _callback(client, state)
        assert response.status_code == status.HTTP_302_FOUND
        assert _error_of(response) is None

    assert User.objects.count() == before
    assert User.objects.filter(pk=user.pk).count() == 1
