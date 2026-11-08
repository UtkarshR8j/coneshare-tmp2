from unittest.mock import patch

import pytest

from assetbrowser.models import AssetSnapshot
from core.models import APIKey


@pytest.fixture(autouse=True)
def bound_org(organization):
    """These tests cover browsing itself, so the org owns every space in the fake tree."""
    organization.oc_space_ids = ['users:user-1', 'projects:proj-1']
    organization.save(update_fields=['oc_space_ids'])
    return organization


@pytest.fixture
def fs():
    with patch('assetbrowser.services.fileserver_client') as client:
        client.upload_file.side_effect = lambda key, f, **kw: f.read()
        yield client


@pytest.fixture
def admin_room(admin_user, organization):
    from datarooms.models import Dataroom
    return Dataroom.objects.create(name='Room', organization=organization, created_by=admin_user)


@pytest.mark.django_db
class TestAccess:
    @pytest.mark.parametrize('url', ['/api/v1/assets/spaces/', '/api/v1/assets/browse/?space_id=users:user-1', '/api/v1/assets/search/?q=gif'])
    def test_member_forbidden(self, api_client, assets_root, url):
        assert api_client.get(url).status_code == 403

    def test_anonymous_unauthorized(self, public_client, assets_root):
        assert public_client.get('/api/v1/assets/spaces/').status_code == 401

    def test_api_key_forbidden_even_for_admin(self, admin_user, assets_root):
        from rest_framework.test import APIClient
        client = APIClient()
        client.force_authenticate(user=admin_user, token=APIKey())
        assert client.get('/api/v1/assets/spaces/').status_code == 403

    def test_503_when_not_configured(self, admin_api_client, settings):
        settings.ASSETS_RO_ROOT = ''
        assert admin_api_client.get('/api/v1/assets/spaces/').status_code == 503


@pytest.mark.django_db
class TestBrowse:
    def test_spaces(self, admin_api_client, assets_root):
        ids = {s['id'] for s in admin_api_client.get('/api/v1/assets/spaces/').json()}
        assert ids == {'users:user-1', 'projects:proj-1'}

    def test_browse(self, admin_api_client, assets_root):
        data = admin_api_client.get('/api/v1/assets/browse/', {'space_id': 'users:user-1', 'path': 'Invoices'}).json()
        assert [i['name'] for i in data['items']] == ['inv.gif']

    def test_traversal_400(self, admin_api_client, assets_root):
        r = admin_api_client.get('/api/v1/assets/browse/', {'space_id': 'users:user-1', 'path': '../..'})
        assert r.status_code == 400

    def test_search(self, admin_api_client, assets_root):
        data = admin_api_client.get('/api/v1/assets/search/', {'q': 'inv'}).json()
        assert [i['path'] for i in data['items']] == ['Invoices/inv.gif'] and data['truncated'] is False

    def test_search_needs_two_chars(self, admin_api_client, assets_root):
        assert admin_api_client.get('/api/v1/assets/search/', {'q': 'i'}).status_code == 400


@pytest.mark.django_db
class TestAdd:
    def url(self, room):
        return f'/api/v1/datarooms/{room.id}/assets/add/'

    def test_add_returns_202_and_snapshot_finishes(self, admin_api_client, admin_user, assets_root, fs, admin_room):
        r = admin_api_client.post(self.url(admin_room), {'items': [{'space_id': 'users:user-1', 'path': 'top.gif'}]}, format='json')
        assert r.status_code == 202
        snap = AssetSnapshot.objects.get(id=r.json()['snapshots'][0]['id'])
        assert snap.status == AssetSnapshot.STATUS_READY  # tasks run eagerly under pytest
        assert snap.added_by == admin_user and snap.source_space_name == 'Utkarsh' and snap.source_file_id == 'node-id'

    def test_missing_file_400_and_nothing_queued(self, admin_api_client, assets_root, fs, admin_room):
        r = admin_api_client.post(self.url(admin_room), {'items': [
            {'space_id': 'users:user-1', 'path': 'top.gif'},
            {'space_id': 'users:user-1', 'path': 'nope.gif'},
        ]}, format='json')
        assert r.status_code == 400
        assert AssetSnapshot.objects.count() == 0

    def test_member_forbidden(self, api_client, assets_root, fs, dataroom):
        r = api_client.post(self.url(dataroom), {'items': [{'space_id': 'users:user-1', 'path': 'top.gif'}]}, format='json')
        assert r.status_code == 403

    def test_folder_from_other_room_rejected(self, admin_api_client, assets_root, fs, admin_room, organization, admin_user):
        from datarooms.models import Dataroom, DataroomFolder
        other = Dataroom.objects.create(name='O', organization=organization, created_by=admin_user)
        folder = DataroomFolder.objects.create(name='F', dataroom=other)
        r = admin_api_client.post(self.url(admin_room), {'items': [{'space_id': 'users:user-1', 'path': 'top.gif'}], 'destination_folder_id': str(folder.id)}, format='json')
        assert r.status_code == 400

    def test_works_while_upload_lock_is_on(self, admin_api_client, assets_root, fs, admin_room, settings):
        settings.DOCUMENT_UPLOADS_DISABLED = True
        r = admin_api_client.post(self.url(admin_room), {'items': [{'space_id': 'users:user-1', 'path': 'top.gif'}]}, format='json')
        assert r.status_code == 202

    def test_snapshots_endpoint_filters_by_ids(self, admin_api_client, assets_root, fs, admin_room):
        add = admin_api_client.post(self.url(admin_room), {'items': [{'space_id': 'users:user-1', 'path': 'top.gif'}]}, format='json').json()
        sid = add['snapshots'][0]['id']
        rows = admin_api_client.get(f'/api/v1/datarooms/{admin_room.id}/assets/snapshots/', {'ids': sid}).json()
        assert [row['id'] for row in rows] == [sid] and rows[0]['status'] == 'ready'


@pytest.mark.django_db
class TestPreview:
    url = '/api/v1/assets/preview/'

    def test_member_forbidden(self, api_client, assets_root):
        assert api_client.get(self.url, {'space_id': 'users:user-1', 'path': 'top.gif'}).status_code == 403

    def test_serves_allowlisted_type_inline(self, admin_api_client, assets_root):
        r = admin_api_client.get(self.url, {'space_id': 'users:user-1', 'path': 'top.gif'})
        assert r.status_code == 200
        assert b''.join(r.streaming_content) == b'top-bytes'
        assert r['Content-Type'] == 'image/gif'
        assert r['Content-Disposition'].startswith('inline')
        assert r['X-Content-Type-Options'] == 'nosniff'

    @pytest.mark.parametrize('name', ['page.html', 'logo.svg', 'noextension'])
    def test_scriptable_or_unknown_types_rejected(self, admin_api_client, assets_root, name):
        (assets_root / 'users' / 'user-1' / name).write_bytes(b'<script>alert(1)</script>')
        r = admin_api_client.get(self.url, {'space_id': 'users:user-1', 'path': name})
        assert r.status_code == 415

    def test_traversal_400(self, admin_api_client, assets_root):
        r = admin_api_client.get(self.url, {'space_id': 'users:user-1', 'path': '../../secret.gif'})
        assert r.status_code == 400

    def test_missing_file_404(self, admin_api_client, assets_root):
        r = admin_api_client.get(self.url, {'space_id': 'users:user-1', 'path': 'nope.gif'})
        assert r.status_code == 404
