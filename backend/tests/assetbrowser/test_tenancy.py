"""Org tenancy for the assets bridge: every org only sees and adds from its own OpenCloud spaces."""
from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from assetbrowser import scanner
from assetbrowser.models import AssetSnapshot
from core.models import Organization, User
from datarooms.models import Dataroom


@pytest.fixture
def fs():
    with patch('assetbrowser.services.fileserver_client') as client:
        client.upload_file.side_effect = lambda key, f, **kw: f.read()
        yield client


@pytest.fixture
def org_a(organization):
    organization.oc_space_ids = ['users:user-1']
    organization.save(update_fields=['oc_space_ids'])
    return organization


@pytest.fixture
def org_b(db):
    return Organization.objects.create(name='Org B', oc_space_ids=['projects:proj-1'])


@pytest.fixture
def admin_b(org_b):
    return User.objects.create_user(
        username='admin-b@example.com', email='admin-b@example.com', password='password', role='admin', organization=org_b,
    )


@pytest.fixture
def client_b(admin_b):
    client = APIClient()
    client.force_authenticate(user=admin_b)
    return client


@pytest.fixture
def room_a(org_a, admin_user):
    return Dataroom.objects.create(name='Room A', organization=org_a, created_by=admin_user)


def add_url(room):
    return f'/api/v1/datarooms/{room.id}/assets/add/'


@pytest.mark.django_db
class TestPickerScoping:
    def test_spaces_only_lists_own_binding(self, admin_api_client, client_b, org_a, assets_root):
        assert [s['id'] for s in admin_api_client.get('/api/v1/assets/spaces/').json()] == ['users:user-1']
        assert [s['id'] for s in client_b.get('/api/v1/assets/spaces/').json()] == ['projects:proj-1']

    def test_browse_other_org_space_is_404(self, admin_api_client, org_a, assets_root):
        r = admin_api_client.get('/api/v1/assets/browse/', {'space_id': 'projects:proj-1'})
        assert r.status_code == 404

    def test_preview_other_org_space_is_404(self, client_b, org_a, assets_root):
        r = client_b.get('/api/v1/assets/preview/', {'space_id': 'users:user-1', 'path': 'top.gif'})
        assert r.status_code == 404

    def test_search_skips_other_org_spaces(self, client_b, org_a, assets_root):
        assert client_b.get('/api/v1/assets/search/', {'q': 'gif'}).json() == {'items': [], 'truncated': False}
        assert client_b.get('/api/v1/assets/search/', {'q': 'gif', 'space_id': 'users:user-1'}).status_code == 404

    def test_empty_binding_fails_closed(self, admin_api_client, organization, assets_root):
        assert organization.oc_space_ids == []
        assert admin_api_client.get('/api/v1/assets/spaces/').json() == []
        assert admin_api_client.get('/api/v1/assets/search/', {'q': 'gif'}).json() == {'items': [], 'truncated': False}
        assert admin_api_client.get('/api/v1/assets/browse/', {'space_id': 'users:user-1'}).status_code == 404
        assert admin_api_client.get('/api/v1/assets/preview/', {'space_id': 'users:user-1', 'path': 'top.gif'}).status_code == 404

    @pytest.mark.parametrize('binding', ['users:user-1', {'id': 'users:user-1'}, [None, 5, '']])
    def test_malformed_binding_fails_closed(self, admin_api_client, organization, assets_root, binding):
        Organization.objects.filter(id=organization.id).update(oc_space_ids=binding)
        assert admin_api_client.get('/api/v1/assets/spaces/').json() == []


@pytest.mark.django_db
class TestAddWall:
    def test_space_outside_room_org_binding_400(self, admin_api_client, room_a, assets_root, fs):
        r = admin_api_client.post(add_url(room_a), {'items': [{'space_id': 'projects:proj-1', 'path': 'x.gif'}]}, format='json')
        assert r.status_code == 400
        assert AssetSnapshot.objects.count() == 0

    def test_space_in_binding_succeeds(self, admin_api_client, room_a, assets_root, fs):
        r = admin_api_client.post(add_url(room_a), {'items': [{'space_id': 'users:user-1', 'path': 'top.gif'}]}, format='json')
        assert r.status_code == 202
        assert AssetSnapshot.objects.filter(dataroom=room_a, source_space_id='users:user-1').count() == 1

    def test_one_foreign_item_rejects_whole_batch(self, admin_api_client, room_a, assets_root, fs):
        r = admin_api_client.post(add_url(room_a), {'items': [
            {'space_id': 'users:user-1', 'path': 'top.gif'},
            {'space_id': 'projects:proj-1', 'path': 'x.gif'},
        ]}, format='json')
        assert r.status_code == 400
        assert AssetSnapshot.objects.count() == 0

    def test_wall_runs_before_filesystem(self, admin_api_client, room_a, assets_root, fs):
        with patch.object(scanner, 'stat_file') as stat_file, patch.object(scanner, 'list_spaces') as list_spaces:
            r = admin_api_client.post(add_url(room_a), {'items': [{'space_id': 'projects:proj-1', 'path': 'x.gif'}]}, format='json')
        assert r.status_code == 400
        stat_file.assert_not_called()
        list_spaces.assert_not_called()

    def test_empty_room_org_binding_rejects(self, admin_api_client, admin_user, organization, assets_root, fs):
        room = Dataroom.objects.create(name='Unbound', organization=organization, created_by=admin_user)
        r = admin_api_client.post(add_url(room), {'items': [{'space_id': 'users:user-1', 'path': 'top.gif'}]}, format='json')
        assert r.status_code == 400

    def test_guest_admin_cannot_push_own_space_into_other_org_room(self, client_b, admin_b, room_a, assets_root, fs):
        from datarooms.models import DataroomCollaborator
        DataroomCollaborator.objects.create(dataroom=room_a, user=admin_b)
        r = client_b.post(add_url(room_a), {'items': [{'space_id': 'projects:proj-1', 'path': 'x.gif'}]}, format='json')
        assert r.status_code == 400
        assert AssetSnapshot.objects.count() == 0

    def test_existing_snapshots_survive_unbinding(self, admin_api_client, room_a, org_a, assets_root, fs):
        add = admin_api_client.post(add_url(room_a), {'items': [{'space_id': 'users:user-1', 'path': 'top.gif'}]}, format='json').json()
        sid = add['snapshots'][0]['id']
        org_a.oc_space_ids = []
        org_a.save(update_fields=['oc_space_ids'])
        rows = admin_api_client.get(f'/api/v1/datarooms/{room_a.id}/assets/snapshots/').json()
        assert [row['id'] for row in rows] == [sid] and rows[0]['status'] == 'ready'
