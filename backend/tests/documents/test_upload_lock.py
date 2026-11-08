import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import URLPattern, URLResolver, get_resolver

from documents.upload_lock import LOCKED_URL_NAMES

LOCKED_PATHS = [
    '/api/v1/uploads/document/request/',
    '/api/v1/uploads/document/finalize/',
    '/api/v1/uploads/document/doc1/versions/request/',
    '/api/v1/uploads/document/doc1/versions/finalize/',
    '/api/v1/datarooms/room1/uploads/request/',
    '/api/v1/datarooms/room1/uploads/finalize/',
    '/api/v1/cloud/connections/c1/import/',
    '/api/v1/cloud/documents/doc1/refresh/',
    '/api/v1/cloud/documents/doc1/import_version/',
    '/api/v1/public/file-requests/some-slug/request-upload/',
    '/api/v1/public/file-requests/some-slug/finalize-upload/',
]
GIF = (b'GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,'
       b'\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;')


def _all_url_names(patterns):
    for p in patterns:
        if isinstance(p, URLResolver):
            # Django admin model routes (e.g. filerequests_uploadedfile_add) are staff-only and carry no file bytes in.
            if p.namespace != 'admin':
                yield from _all_url_names(p.url_patterns)
        elif isinstance(p, URLPattern) and p.name:
            yield p.name


@pytest.mark.django_db
class TestUploadLock:
    @pytest.mark.parametrize('path', LOCKED_PATHS)
    def test_locked_when_disabled(self, api_client, settings, path):
        settings.DOCUMENT_UPLOADS_DISABLED = True
        response = api_client.post(path, {}, format='json')
        assert response.status_code == 403
        assert response.json()['code'] == 'document_uploads_disabled'
        assert 'assets.longstraw.earth' in response.json()['detail']

    @pytest.mark.parametrize('path', LOCKED_PATHS)
    def test_not_locked_by_default(self, api_client, path):
        response = api_client.post(path, {}, format='json')
        if response.status_code == 403:
            assert response.json().get('code') != 'document_uploads_disabled'

    def test_branding_upload_still_works(self, api_client, settings, dataroom, tmp_path):
        settings.DOCUMENT_UPLOADS_DISABLED = True
        settings.MEDIA_ROOT = str(tmp_path)
        banner = SimpleUploadedFile('banner.gif', GIF, content_type='image/gif')
        response = api_client.patch(f'/api/v1/datarooms/{dataroom.id}/', {'branding_banner': banner}, format='multipart')
        assert response.status_code == 200
        dataroom.refresh_from_db()
        assert dataroom.branding_banner

    def test_no_upload_or_import_route_escapes_the_lock(self):
        names = set(_all_url_names(get_resolver().url_patterns))
        suspicious = {n for n in names if 'upload' in n or 'import' in n}
        assert suspicious <= LOCKED_URL_NAMES, suspicious - LOCKED_URL_NAMES
