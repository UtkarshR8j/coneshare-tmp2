"""ShareLink.audience_mode: who may pass the email gate of a share link."""
from unittest.mock import patch

import pytest
from rest_framework import status

from core.models import Organization, User
from datarooms.models import Dataroom, DataroomCollaborator, DataroomDocument
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
def collaborator(organization):
    return User.objects.create_user(
        username='collab@example.com', email='collab@example.com', password='password', organization=organization,
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
class TestOrgMode:
    def test_org_member_passes_case_insensitive(self, public_client, room_link, user2):
        set_audience(room_link, ShareLink.AUDIENCE_ORG)
        response = request_access(public_client, room_link, 'TEST2@Example.com')
        assert response.status_code == status.HTTP_200_OK

    def test_foreign_email_403_on_instant_grant_path(self, public_client, room_link, outsider):
        set_audience(room_link, ShareLink.AUDIENCE_ORG)
        response = request_access(public_client, room_link, outsider.email)

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json() == {'message': RESTRICTED}
        assert not Viewer.objects.filter(email=outsider.email).exists()
        # The session was not authorized.
        assert public_client.get(f'/api/v1/links/{room_link.slug}/view-data/').status_code == status.HTTP_401_UNAUTHORIZED

    @patch('sharelinks.views.send_mail')
    def test_foreign_email_403_on_verification_path(self, mock_send_mail, public_client, room_link, outsider):
        set_audience(room_link, ShareLink.AUDIENCE_ORG, verify=True)
        response = request_access(public_client, room_link, outsider.email)

        assert response.status_code == status.HTTP_403_FORBIDDEN
        mock_send_mail.assert_not_called()
        assert EmailVerificationToken.objects.count() == 0

    def test_inactive_org_member_rejected(self, public_client, room_link, user2):
        user2.is_active = False
        user2.save(update_fields=['is_active'])
        set_audience(room_link, ShareLink.AUDIENCE_ORG)
        assert request_access(public_client, room_link, user2.email).status_code == status.HTTP_403_FORBIDDEN

    def test_document_link_uses_document_org(self, public_client, share_link_requires_email, user2, outsider):
        set_audience(share_link_requires_email, ShareLink.AUDIENCE_ORG)
        assert request_access(public_client, share_link_requires_email, user2.email).status_code == status.HTTP_200_OK
        assert request_access(public_client, share_link_requires_email, outsider.email).status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestCollaboratorsMode:
    def test_collaborator_passes(self, public_client, room_link, dataroom, collaborator):
        DataroomCollaborator.objects.create(dataroom=dataroom, user=collaborator)
        set_audience(room_link, ShareLink.AUDIENCE_COLLABORATORS)
        assert request_access(public_client, room_link, 'Collab@Example.com').status_code == status.HTTP_200_OK

    def test_non_collaborator_403_on_instant_grant_path(self, public_client, room_link, user2):
        # Same org but no collaborator row: org membership is not enough for this mode.
        set_audience(room_link, ShareLink.AUDIENCE_COLLABORATORS)
        response = request_access(public_client, room_link, user2.email)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json() == {'message': RESTRICTED}

    @patch('sharelinks.views.send_mail')
    def test_non_collaborator_403_on_verification_path(self, mock_send_mail, public_client, room_link, outsider):
        set_audience(room_link, ShareLink.AUDIENCE_COLLABORATORS, verify=True)
        assert request_access(public_client, room_link, outsider.email).status_code == status.HTTP_403_FORBIDDEN
        mock_send_mail.assert_not_called()

    def test_document_link_resolves_via_its_dataroom(self, public_client, share_link_requires_email, document, dataroom, collaborator, user2):
        DataroomDocument.objects.create(dataroom=dataroom, document=document)
        DataroomCollaborator.objects.create(dataroom=dataroom, user=collaborator)
        set_audience(share_link_requires_email, ShareLink.AUDIENCE_COLLABORATORS)
        assert request_access(public_client, share_link_requires_email, collaborator.email).status_code == status.HTTP_200_OK
        assert request_access(public_client, share_link_requires_email, user2.email).status_code == status.HTTP_403_FORBIDDEN

    def test_document_link_without_dataroom_rejects(self, public_client, share_link_requires_email, user):
        set_audience(share_link_requires_email, ShareLink.AUDIENCE_COLLABORATORS)
        # Even the link's own creator is not a collaborator on a room that does not exist.
        assert request_access(public_client, share_link_requires_email, user.email).status_code == status.HTTP_403_FORBIDDEN


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
class TestRestrictedLinkAlwaysAsksForEmail:
    def test_model_forces_requires_email(self, share_link):
        assert share_link.requires_email is False
        share_link.audience_mode = ShareLink.AUDIENCE_ORG
        share_link.save(update_fields=['audience_mode'])
        share_link.refresh_from_db()
        assert share_link.requires_email is True

    def test_stale_row_still_gated(self, public_client, share_link, outsider):
        # A row written behind save() (e.g. queryset.update) cannot skip the email gate.
        ShareLink.objects.filter(id=share_link.id).update(audience_mode=ShareLink.AUDIENCE_ORG, requires_email=False)
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

    def test_invalid_email_rejected(self, api_client, document):
        response = api_client.post(self.url, {
            'document': str(document.id), 'name': 'L', 'audience_mode': 'allowlist', 'audience_emails': ['not-an-email'],
        }, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.parametrize('mode', ['anyone', 'org', 'collaborators'])
    def test_other_modes_clear_the_list(self, api_client, document, mode):
        response = api_client.post(self.url, {
            'document': str(document.id), 'name': 'L', 'audience_mode': mode, 'audience_emails': ['x@example.com'],
        }, format='json')
        assert response.status_code == status.HTTP_201_CREATED, response.json()
        assert ShareLink.objects.get(id=response.json()['id']).audience_emails == []

    def test_switching_from_allowlist_clears_list_on_update(self, api_client, document):
        created = api_client.post(self.url, {
            'document': str(document.id), 'name': 'L', 'audience_mode': 'allowlist', 'audience_emails': ['a@example.com'],
        }, format='json').json()
        response = api_client.patch(f"{self.url}{created['id']}/", {'audience_mode': 'org'}, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['audience_emails'] == []

    def test_invalid_mode_rejected(self, api_client, document):
        response = api_client.post(self.url, {'document': str(document.id), 'name': 'L', 'audience_mode': 'everyone'}, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_default_create_is_anyone(self, api_client, document):
        response = api_client.post(self.url, {'document': str(document.id), 'name': 'L'}, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()['audience_mode'] == 'anyone' and response.json()['audience_emails'] == []
        assert response.json()['requires_email'] is False
