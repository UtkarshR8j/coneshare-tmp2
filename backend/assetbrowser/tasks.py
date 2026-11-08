import logging

from celery import shared_task

from .models import AssetSnapshot
from .scanner import AssetError
from .services import SnapshotRejected, run_snapshot

logger = logging.getLogger('tasks')


@shared_task
def snapshot_asset_task(snapshot_id):
    claimed = AssetSnapshot.objects.filter(id=snapshot_id, status=AssetSnapshot.STATUS_QUEUED).update(
        status=AssetSnapshot.STATUS_COPYING
    )
    if not claimed:
        return
    snapshot = AssetSnapshot.objects.select_related('destination_folder', 'added_by').get(id=snapshot_id)
    try:
        run_snapshot(snapshot)
    except (AssetError, SnapshotRejected) as e:
        _fail(snapshot_id, str(e))
    except Exception:
        logger.exception('Asset snapshot %s failed', snapshot_id)
        _fail(snapshot_id, 'An unexpected error occurred while copying the file.')


def _fail(snapshot_id, message):
    AssetSnapshot.objects.filter(id=snapshot_id).update(status=AssetSnapshot.STATUS_FAILED, error=message[:500])
