from django.db import models

from core.models import BaseModel, Organization, User


class AssetSnapshot(BaseModel):
    """Job status and permanent provenance for one 'add from assets' action."""
    STATUS_QUEUED = 'queued'
    STATUS_COPYING = 'copying'
    STATUS_READY = 'ready'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_QUEUED, 'Queued'),
        (STATUS_COPYING, 'Copying'),
        (STATUS_READY, 'Ready'),
        (STATUS_FAILED, 'Failed'),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='asset_snapshots')
    dataroom = models.ForeignKey('datarooms.Dataroom', on_delete=models.SET_NULL, null=True, related_name='asset_snapshots')
    destination_folder = models.ForeignKey('datarooms.DataroomFolder', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    dataroom_document = models.ForeignKey('datarooms.DataroomDocument', on_delete=models.SET_NULL, null=True, blank=True, related_name='asset_snapshots')
    document = models.ForeignKey('documents.Document', on_delete=models.SET_NULL, null=True, blank=True, related_name='asset_snapshots')

    source_space_id = models.CharField(max_length=128)
    source_space_name = models.CharField(max_length=255, blank=True)
    source_path = models.CharField(max_length=2048)
    source_file_id = models.CharField(max_length=255, blank=True)
    source_md5 = models.CharField(max_length=32, blank=True)
    sha256 = models.CharField(max_length=64, blank=True, db_index=True)
    file_size = models.BigIntegerField(null=True, blank=True)
    reused_document = models.BooleanField(default=False)

    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_QUEUED, db_index=True)
    error = models.TextField(blank=True)
    added_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='asset_snapshots')

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [models.Index(fields=['organization', 'sha256'])]

    def __str__(self):
        return f'{self.source_path} -> {self.dataroom_id} ({self.status})'
