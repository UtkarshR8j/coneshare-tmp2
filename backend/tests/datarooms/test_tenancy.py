"""Org tenancy for datarooms: one room per org, visible to the whole org."""
import pytest
from rest_framework import status
from rest_framework.test import APIClient

from core.models import Organization, User
from datarooms.models import Dataroom, DataroomCollaborator


@pytest.fixture
def other_org(db):
    return Organization.objects.create(name='Other Org')


@pytest.fixture
def outsider(other_org):
    return User.objects.create_user(
        username='outsider@other.com', email='outsider@other.com', password='password', organization=other_org,
    )


def client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
class TestOneRoomPerOrg:
    def test_second_create_is_409(self, api_client, user2, organization):
        assert api_client.post('/api/v1/datarooms/', {'name': 'First'}).status_code == status.HTTP_201_CREATED

        response = client_for(user2).post('/api/v1/datarooms/', {'name': 'Second'})

        assert response.status_code == status.HTTP_409_CONFLICT
        assert 'one dataroom per organization' in response.data['detail']
        assert Dataroom.objects.filter(organization=organization).count() == 1

    def test_other_org_can_still_create(self, dataroom, outsider, other_org):
        response = client_for(outsider).post('/api/v1/datarooms/', {'name': 'Theirs'})
        assert response.status_code == status.HTTP_201_CREATED
        assert Dataroom.objects.get(id=response.data['id']).organization == other_org


@pytest.mark.django_db
class TestOrgVisibility:
    def test_org_member_sees_room_without_collaborator_row(self, dataroom, user2):
        assert not DataroomCollaborator.objects.filter(dataroom=dataroom, user=user2).exists()
        client = client_for(user2)

        listed = client.get('/api/v1/datarooms/')
        assert [str(r['id']) for r in listed.data] == [str(dataroom.id)]
        assert client.get(f'/api/v1/datarooms/{dataroom.id}/').status_code == status.HTTP_200_OK

    def test_other_org_user_does_not_see_room(self, dataroom, outsider):
        client = client_for(outsider)
        assert client.get('/api/v1/datarooms/').data == []
        assert client.get(f'/api/v1/datarooms/{dataroom.id}/').status_code == status.HTTP_404_NOT_FOUND

    def test_guest_collaborator_from_other_org_sees_room(self, dataroom, outsider):
        DataroomCollaborator.objects.create(dataroom=dataroom, user=outsider)
        listed = client_for(outsider).get('/api/v1/datarooms/')
        assert [str(r['id']) for r in listed.data] == [str(dataroom.id)]

    def test_org_member_cannot_delete_room_they_do_not_own(self, dataroom, user2):
        response = client_for(user2).delete(f'/api/v1/datarooms/{dataroom.id}/')
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert Dataroom.objects.filter(id=dataroom.id).exists()
