"""Copies one picked OpenCloud file into coneshare's store and attaches it to a room."""
import hashlib
import logging
import mimetypes
import os
import posixpath
import time

from django.conf import settings
from django.db import IntegrityError, OperationalError, transaction
from rest_framework.exceptions import APIException

from backend.utils import get_unique_name
from datarooms.models import Dataroom, DataroomDocument, DataroomItemOrder
from datarooms.services import (
    get_dataroom_storage_used_bytes,
    get_or_create_dataroom_storage_folder,
    touch_dataroom_folder_ancestors,
)
from documents.fileserver import fileserver_client
from documents.services import create_document_from_upload, generate_storage_key
from . import scanner
from .models import AssetSnapshot

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1024 * 1024
UPLOAD_TIMEOUT = (10, 1800)
ATTACH_ATTEMPTS = 5


class SnapshotRejected(Exception):
    """A reason the operator should see, as opposed to an internal fault."""


def _fingerprint(f):
    st = os.fstat(f.fileno())
    return st.st_size, st.st_mtime_ns


def _hash_stream(f):
    sha256, md5, size = hashlib.sha256(), hashlib.md5(usedforsecurity=False), 0
    while chunk := f.read(CHUNK_SIZE):
        sha256.update(chunk)
        md5.update(chunk)
        size += len(chunk)
    return sha256.hexdigest(), md5.hexdigest(), size


def _find_reusable_document(organization_id, sha256):
    prior = (
        AssetSnapshot.objects.filter(
            organization_id=organization_id,
            sha256=sha256,
            status=AssetSnapshot.STATUS_READY,
            document__isnull=False,
            document__deleted_at__isnull=True,
        )
        .exclude(document__status='error')
        .select_related('document')
        .first()
    )
    return prior.document if prior else None


def _delete_blob_quietly(storage_key):
    try:
        fileserver_client.delete_file(storage_key)
    except APIException as e:
        logger.error('Could not remove orphan snapshot blob %s: %s', storage_key, e)


def _append_item_order(room, folder, room_document):
    # Same logic as DataroomViewSet._append_item_order, kept here so upstream views stay untouched.
    last = (
        DataroomItemOrder.objects.filter(dataroom=room, parent_folder=folder)
        .order_by('-position').values_list('position', flat=True).first()
    )
    DataroomItemOrder.objects.create(
        dataroom=room,
        parent_folder=folder,
        item_type=DataroomItemOrder.ITEM_TYPE_DOCUMENT,
        dataroom_document=room_document,
        position=(last + 1) if last is not None else 0,
    )


def _attach(snapshot, name, content_type, sha256, md5, size, storage_key):
    """Returns True if storage_key was used. Mirrors DataroomViewSet.upload_finalize."""
    folder = snapshot.destination_folder
    with transaction.atomic():
        room = Dataroom.objects.select_for_update().get(id=snapshot.dataroom_id)
        document = _find_reusable_document(snapshot.organization_id, sha256)
        if document is None and storage_key is None:
            raise SnapshotRejected('The earlier copy of this file was removed. Add it again.')
        reused = document is not None

        already_in_room = reused and DataroomDocument.objects.filter(dataroom=room, document=document).exists()
        if room.storage_quota_mb and room.storage_quota_mb > 0 and not already_in_room:
            if get_dataroom_storage_used_bytes(room) + size > room.storage_quota_mb * 1024 * 1024:
                raise SnapshotRejected(f'Adding this file would exceed the Dataroom storage limit of {room.storage_quota_mb} MB.')

        if document is None:
            document = create_document_from_upload(
                requesting_user=snapshot.added_by,
                folder=get_or_create_dataroom_storage_folder(room, requesting_user=snapshot.added_by),
                storage_key=storage_key,
                unique_name=name,
                file_size=size,
                content_type=content_type,
                track_user_quota=room.storage_version < 2,
            )

        room_document = DataroomDocument.objects.filter(dataroom=room, document=document, folder=folder).first()
        if room_document is None:
            room_document = DataroomDocument.objects.create(
                dataroom=room,
                document=document,
                folder=folder,
                name=get_unique_name(DataroomDocument, name, {'dataroom': room, 'folder': folder}, has_extension=True),
                is_direct_upload=True,
            )
            has_order = DataroomItemOrder.objects.filter(dataroom=room, parent_folder=folder).exists()
            if room.show_file_index and has_order:
                _append_item_order(room, folder, room_document)
            if folder:
                touch_dataroom_folder_ancestors(folder)

        snapshot.document = document
        snapshot.dataroom_document = room_document
        snapshot.sha256 = sha256
        snapshot.source_md5 = md5
        snapshot.file_size = size
        snapshot.reused_document = reused
        snapshot.status = AssetSnapshot.STATUS_READY
        snapshot.error = ''
        snapshot.save()
    return not reused


def _attach_with_retry(*args):
    # SQLite ignores select_for_update, so concurrent workers can collide here.
    for attempt in range(ATTACH_ATTEMPTS):
        try:
            return _attach(*args)
        except (IntegrityError, OperationalError):
            if attempt == ATTACH_ATTEMPTS - 1:
                raise
            time.sleep(0.5 * (attempt + 1))


def run_snapshot(snapshot):
    name = posixpath.basename(snapshot.source_path)
    content_type = mimetypes.guess_type(name)[0] or 'application/octet-stream'
    max_bytes = settings.ASSETS_MAX_SNAPSHOT_MB * 1024 * 1024

    with scanner.open_file(snapshot.source_space_id, snapshot.source_path) as src:
        before = _fingerprint(src)
        if before[0] > max_bytes:
            raise SnapshotRejected(f'File exceeds the {settings.ASSETS_MAX_SNAPSHOT_MB} MB snapshot limit.')
        sha256, md5, size = _hash_stream(src)

        storage_key = None
        if _find_reusable_document(snapshot.organization_id, sha256) is None:
            storage_key = generate_storage_key(snapshot.organization_id, name)
            # Same descriptor as the hash: OpenCloud replaces files by rename, so this fd stays stable.
            src.seek(0)
            fileserver_client.upload_file(storage_key, src, content_type=content_type, timeout=UPLOAD_TIMEOUT)

        # Catches in-place writes, e.g. an OpenCloud revision restore (posix/tree/revisions.go).
        changed = _fingerprint(src) != before

    if changed:
        if storage_key:
            _delete_blob_quietly(storage_key)
        raise SnapshotRejected('The file changed while it was being copied. Add it again.')

    try:
        used_key = _attach_with_retry(snapshot, name, content_type, sha256, md5, size, storage_key)
    except Exception:
        if storage_key:
            _delete_blob_quietly(storage_key)
        raise
    if storage_key and not used_key:
        _delete_blob_quietly(storage_key)  # another worker won the race with the same bytes
