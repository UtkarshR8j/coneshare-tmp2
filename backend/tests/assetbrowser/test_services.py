import hashlib
import os
from unittest.mock import patch

import pytest
import requests
from rest_framework.exceptions import APIException

from assetbrowser import scanner
from assetbrowser.models import AssetSnapshot
from assetbrowser.services import run_snapshot, SnapshotRejected
from datarooms.models import Dataroom, DataroomDocument
from documents.fileserver import fileserver_client
from documents.models import Document

BYTES = b'top-bytes'


def make_snapshot(dataroom, user, path='top.gif'):
    return AssetSnapshot.objects.create(
        organization=dataroom.organization, dataroom=dataroom, added_by=user,
        source_space_id='users:user-1', source_space_name='Utkarsh', source_path=path,
    )


@pytest.fixture
def fs():
    with patch('assetbrowser.services.fileserver_client') as client:
        client.upload_file.side_effect = lambda key, f, **kw: f.read()
        yield client


@pytest.mark.django_db
class TestRunSnapshot:
    def test_copies_and_records_provenance(self, assets_root, fs, dataroom, user):
        snap = make_snapshot(dataroom, user)
        run_snapshot(snap)
        snap.refresh_from_db()
        assert snap.status == AssetSnapshot.STATUS_READY
        assert snap.sha256 == hashlib.sha256(BYTES).hexdigest()
        assert snap.source_md5 == hashlib.md5(BYTES).hexdigest()
        assert snap.file_size == len(BYTES)
        assert snap.reused_document is False
        assert fs.upload_file.call_count == 1
        room_doc = snap.dataroom_document
        assert room_doc.dataroom == dataroom and room_doc.name == 'top.gif' and room_doc.is_direct_upload is True

    def test_same_bytes_in_second_room_reuses_document(self, assets_root, fs, dataroom, user, organization):
        run_snapshot(make_snapshot(dataroom, user))
        other = Dataroom.objects.create(name='Other', organization=organization, created_by=user)
        snap = make_snapshot(other, user)
        run_snapshot(snap)
        snap.refresh_from_db()
        assert snap.reused_document is True
        assert fs.upload_file.call_count == 1
        assert Document.objects.count() == 1
        assert DataroomDocument.objects.count() == 2

    def test_readd_unchanged_in_same_room_adds_no_row(self, assets_root, fs, dataroom, user):
        run_snapshot(make_snapshot(dataroom, user))
        second = make_snapshot(dataroom, user)
        run_snapshot(second)
        second.refresh_from_db()
        assert second.status == AssetSnapshot.STATUS_READY
        assert DataroomDocument.objects.filter(dataroom=dataroom).count() == 1

    def test_edit_at_source_does_not_change_existing_snapshot(self, assets_root, fs, dataroom, user):
        first = make_snapshot(dataroom, user)
        run_snapshot(first)
        (assets_root / 'users' / 'user-1' / 'top.gif').write_bytes(b'edited-bytes')
        second = make_snapshot(dataroom, user)
        run_snapshot(second)
        first.refresh_from_db()
        second.refresh_from_db()
        assert first.sha256 != second.sha256
        assert first.document_id != second.document_id
        assert DataroomDocument.objects.filter(dataroom=dataroom).count() == 2

    def test_room_quota_rejected_and_blob_removed(self, assets_root, fs, dataroom, user):
        dataroom.storage_quota_mb = 1
        dataroom.save()
        Document.objects.create(name='big', organization=dataroom.organization, created_by=user, file_size=2 * 1024 * 1024, status='ready')
        DataroomDocument.objects.create(dataroom=dataroom, document=Document.objects.get(name='big'), name='big')
        with pytest.raises(SnapshotRejected):
            run_snapshot(make_snapshot(dataroom, user))
        assert fs.delete_file.call_count == 1

    def test_file_changing_during_copy_is_rejected(self, assets_root, fs, dataroom, user):
        def mutate(key, f, **kw):
            (assets_root / 'users' / 'user-1' / 'top.gif').write_bytes(b'longer-different-bytes')
        fs.upload_file.side_effect = mutate
        with pytest.raises(SnapshotRejected):
            run_snapshot(make_snapshot(dataroom, user))
        assert fs.delete_file.call_count == 1

    def test_size_cap(self, assets_root, fs, dataroom, user, settings):
        settings.ASSETS_MAX_SNAPSHOT_MB = 0
        with pytest.raises(SnapshotRejected):
            run_snapshot(make_snapshot(dataroom, user))
        assert fs.upload_file.call_count == 0


@pytest.mark.django_db
class TestSnapshotTask:
    def test_failure_is_recorded(self, assets_root, fs, dataroom, user):
        from assetbrowser.tasks import snapshot_asset_task
        snap = make_snapshot(dataroom, user, path='missing.gif')
        snapshot_asset_task(snap.id)
        snap.refresh_from_db()
        assert snap.status == AssetSnapshot.STATUS_FAILED and snap.error

    def test_internal_error_hides_details(self, assets_root, fs, dataroom, user):
        from assetbrowser.tasks import snapshot_asset_task
        fs.upload_file.side_effect = RuntimeError('secret internal detail')
        snap = make_snapshot(dataroom, user)
        snapshot_asset_task(snap.id)
        snap.refresh_from_db()
        assert snap.status == AssetSnapshot.STATUS_FAILED
        assert 'secret' not in snap.error

    def test_already_finished_snapshot_is_skipped(self, assets_root, fs, dataroom, user):
        from assetbrowser.tasks import snapshot_asset_task
        snap = make_snapshot(dataroom, user)
        snapshot_asset_task(snap.id)
        snapshot_asset_task(snap.id)
        assert fs.upload_file.call_count == 1


@pytest.mark.django_db
def test_snapshot_end_to_end_with_real_xattrs_and_file_server(settings, tmp_path, dataroom, user):
    """No mocks: real xattrs on disk, real bytes through the running core file server."""
    root = tmp_path / 'assets-ro'
    space = root / 'users' / 'user-1'
    space.mkdir(parents=True)
    source = space / 'real.gif'
    payload = b'GIF89a' + b'real-bytes' * 300_000  # larger than one read chunk
    source.write_bytes(payload)
    try:
        os.setxattr(source, scanner.XATTR_ID, b'real-node-id')
        os.setxattr(source, scanner.XATTR_MD5, hashlib.md5(payload).digest())
    except OSError:
        pytest.skip('filesystem has no user xattrs')
    settings.ASSETS_RO_ROOT = str(root)

    assert scanner.stat_file('users:user-1', 'real.gif')['md5'] == hashlib.md5(payload).hexdigest()
    try:
        fileserver_client.generate_download_url('probe', is_internal=True)
    except APIException:
        pytest.skip('core file server is not running')

    snap = make_snapshot(dataroom, user, path='real.gif')
    run_snapshot(snap)
    snap.refresh_from_db()

    key = snap.document.original_storage_key
    stored = requests.get(fileserver_client.generate_download_url(key, is_internal=True), timeout=30)
    assert stored.status_code == 200 and stored.content == payload
    assert snap.source_md5 == hashlib.md5(payload).hexdigest()
    assert snap.sha256 == hashlib.sha256(payload).hexdigest()
    assert snap.file_size == len(payload)
    fileserver_client.delete_file(key)
