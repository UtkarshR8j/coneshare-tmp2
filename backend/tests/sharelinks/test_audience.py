"""ShareLink.audience_mode: who may pass the email gate of a share link.

Two modes only: 'anyone' (default, no gate) and 'allowlist' (an exact email or a
wildcard pattern such as *@partner.com).
"""
from unittest.mock import patch

import pytest
from rest_framework import status

from core.models import Organization, User
from sharelinks.models import EmailVerificationToken, ShareLink, Viewer

RESTRICTED = 'This link is restricted to specific recipients.'


@pytest.fixture
def other_org(db):
    return Organization.objects.create(name='Other Org')


@pytest.fixture
def outsider(other_org):
    return User.objects.create_user(
        username='outsider@other.com', email='outsider@other.com', password='password', organization=other_org,
    )


@pytest.fixture
def room_link(dataroom, user):
    return ShareLink.objects.create(dataroom=dataroom, created_by=user, name='Room link', requires_email=True)


def request_access(client, link, email):
    return client.post(f'/api/v1/links/{link.slug}/request-access/', {'email': email})


def set_audience(link, mode, emails=None, verify=False):
    link.audience_mode = mode
    link.audience_emails = emails or []
    link.requires_email_verification = verify
    link.save()
    return link


@pytest.mark.django_db
class TestAnyone:
    def test_default_mode_is_anyone_and_unchanged(self, public_client, share_link_requires_email):
        assert share_link_requires_email.audience_mode == ShareLink.AUDIENCE_ANYONE
        response = request_access(public_client, share_link_requires_email, 'stranger@nowhere.com')
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['verification_required'] is False


@pytest.mark.django_db
class TestAllowlistMode:
    def test_listed_email_passes_case_insensitive(self, public_client, room_link):
        set_audience(room_link, ShareLink.AUDIENCE_ALLOWLIST, ['partner@acme.com'])
        assert request_access(public_client, room_link, 'Partner@ACME.com').status_code == status.HTTP_200_OK

    def test_unlisted_email_403_on_instant_grant_path(self, public_client, room_link, user2):
        set_audience(room_link, ShareLink.AUDIENCE_ALLOWLIST, ['partner@acme.com'])
        response = request_access(public_client, room_link, user2.email)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json() == {'message': RESTRICTED}
        assert not Viewer.objects.filter(email=user2.email).exists()

    @patch('sharelinks.views.send_mail')
    def test_unlisted_email_403_on_verification_path(self, mock_send_mail, public_client, room_link):
        set_audience(room_link, ShareLink.AUDIENCE_ALLOWLIST, ['partner@acme.com'], verify=True)
        assert request_access(public_client, room_link, 'intruder@acme.com').status_code == status.HTTP_403_FORBIDDEN
        mock_send_mail.assert_not_called()

    @patch('sharelinks.views.send_mail')
    def test_listed_email_gets_magic_link(self, mock_send_mail, public_client, room_link):
        set_audience(room_link, ShareLink.AUDIENCE_ALLOWLIST, ['partner@acme.com'], verify=True)
        response = request_access(public_client, room_link, 'partner@acme.com')
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['verification_required'] is True
        mock_send_mail.assert_called_once()

    def test_token_issued_before_narrowing_is_rejected_on_confirm(self, public_client, room_link):
        set_audience(room_link, ShareLink.AUDIENCE_ANYONE, verify=True)
        token = EmailVerificationToken.objects.create(share_link=room_link, email='old@acme.com')
        # Opening the magic link stores the pending verification in the session.
        public_client.get(f'/api/v1/links/{room_link.slug}/view-data/?accessToken={token.token}')
        set_audience(room_link, ShareLink.AUDIENCE_ALLOWLIST, ['partner@acme.com'], verify=True)

        response = public_client.post(
            f'/api/v1/links/{room_link.slug}/verify-access-token/confirm/', {'token': str(token.token)}, format='json',
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json() == {'message': RESTRICTED}
        assert not EmailVerificationToken.objects.filter(id=token.id).exists()


@pytest.mark.django_db
class TestAllowlistWildcards:
    def test_domain_wildcard_lets_anyone_at_the_domain_in(self, public_client, room_link):
        set_audience(room_link, ShareLink.AUDIENCE_ALLOWLIST, ['*@acme.com'])
        assert request_access(public_client, room_link, 'first@acme.com').status_code == status.HTTP_200_OK
        assert request_access(public_client, room_link, 'Second.Person@ACME.com').status_code == status.HTTP_200_OK

    def test_domain_wildcard_does_not_leak_to_lookalike_domains(self, public_client, room_link):
        set_audience(room_link, ShareLink.AUDIENCE_ALLOWLIST, ['*@acme.com'])
        assert request_access(public_client, room_link, 'bob@notacme.com').status_code == status.HTTP_403_FORBIDDEN
        assert request_access(public_client, room_link, 'bob@acme.com.evil.com').status_code == status.HTTP_403_FORBIDDEN

    def test_local_part_wildcard_matches_any_domain(self, public_client, room_link):
        set_audience(room_link, ShareLink.AUDIENCE_ALLOWLIST, ['utkarsh@*'])
        assert request_access(public_client, room_link, 'utkarsh@longstraw.in').status_code == status.HTTP_200_OK
        assert request_access(public_client, room_link, 'someone@longstraw.in').status_code == status.HTTP_403_FORBIDDEN

    def test_multiple_patterns_are_or_ed(self, public_client, room_link):
        set_audience(room_link, ShareLink.AUDIENCE_ALLOWLIST, ['*@acme.com', 'auditor@sylvera.com'])
        assert request_access(public_client, room_link, 'anyone@acme.com').status_code == status.HTTP_200_OK
        assert request_access(public_client, room_link, 'auditor@sylvera.com').status_code == status.HTTP_200_OK
        assert request_access(public_client, room_link, 'auditor@sylvera.co').status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestRestrictedLinkAlwaysAsksForEmail:
    def test_model_forces_requires_email(self, share_link):
        assert share_link.requires_email is False
        share_link.audience_mode = ShareLink.AUDIENCE_ALLOWLIST
        share_link.audience_emails = ['partner@acme.com']
        share_link.save(update_fields=['audience_mode', 'audience_emails'])
        share_link.refresh_from_db()
        assert share_link.requires_email is True

    def test_stale_row_still_gated(self, public_client, share_link, outsider):
        # A row written behind save() (e.g. queryset.update) cannot skip the email gate.
        ShareLink.objects.filter(id=share_link.id).update(
            audience_mode=ShareLink.AUDIENCE_ALLOWLIST, audience_emails=['partner@acme.com'], requires_email=False,
        )
        assert public_client.get(f'/api/v1/links/{share_link.slug}/view-data/').status_code == status.HTTP_401_UNAUTHORIZED
        assert request_access(public_client, share_link, outsider.email).status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestAudienceSerializer:
    url = '/api/v1/share-links/'

    def test_allowlist_with_empty_list_rejected(self, api_client, document):
        response = api_client.post(self.url, {
            'document': str(document.id), 'name': 'L', 'audience_mode': 'allowlist', 'audience_emails': [],
        }, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'audience_emails' in response.json()

    def test_allowlist_without_list_rejected(self, api_client, document):
        response = api_client.post(self.url, {'document': str(document.id), 'name': 'L', 'audience_mode': 'allowlist'}, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_allowlist_normalized_and_requires_email(self, api_client, document):
        response = api_client.post(self.url, {
            'document': str(document.id), 'name': 'L', 'audience_mode': 'allowlist',
            'audience_emails': ['Alice@Example.com', 'alice@example.com', 'BOB@example.com'],
        }, format='json')
        assert response.status_code == status.HTTP_201_CREATED, response.json()
        link = ShareLink.objects.get(id=response.json()['id'])
        assert link.audience_emails == ['alice@example.com', 'bob@example.com']
        assert link.requires_email is True
        assert response.json()['audience_mode'] == 'allowlist'

    def test_wildcard_entries_are_accepted_and_lowercased(self, api_client, document):
        response = api_client.post(self.url, {
            'document': str(document.id), 'name': 'L', 'audience_mode': 'allowlist',
            'audience_emails': ['*@ACME.com', 'utkarsh@*'],
        }, format='json')
        assert response.status_code == status.HTTP_201_CREATED, response.json()
        assert ShareLink.objects.get(id=response.json()['id']).audience_emails == ['*@acme.com', 'utkarsh@*']

    @pytest.mark.parametrize('bad', ['not-an-email', 'a@', '@acme.com', 'bob@acme', 'bob smith@acme.com', '*@', 'bob@acme..com'])
    def test_invalid_entries_rejected(self, api_client, document, bad):
        response = api_client.post(self.url, {
            'document': str(document.id), 'name': 'L', 'audience_mode': 'allowlist', 'audience_emails': [bad],
        }, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_anyone_clears_the_list(self, api_client, document):
        response = api_client.post(self.url, {
            'document': str(document.id), 'name': 'L', 'audience_mode': 'anyone', 'audience_emails': ['x@example.com'],
        }, format='json')
        assert response.status_code == status.HTTP_201_CREATED, response.json()
        assert ShareLink.objects.get(id=response.json()['id']).audience_emails == []

    def test_switching_from_allowlist_clears_list_on_update(self, api_client, document):
        created = api_client.post(self.url, {
            'document': str(document.id), 'name': 'L', 'audience_mode': 'allowlist', 'audience_emails': ['a@example.com'],
        }, format='json').json()
        response = api_client.patch(f"{self.url}{created['id']}/", {'audience_mode': 'anyone'}, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['audience_emails'] == []

    @pytest.mark.parametrize('mode', ['org', 'collaborators', 'everyone'])
    def test_retired_modes_rejected(self, api_client, document, mode):
        response = api_client.post(self.url, {'document': str(document.id), 'name': 'L', 'audience_mode': mode}, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_default_create_is_anyone(self, api_client, document):
        response = api_client.post(self.url, {'document': str(document.id), 'name': 'L'}, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()['audience_mode'] == 'anyone' and response.json()['audience_emails'] == []
        assert response.json()['requires_email'] is False
