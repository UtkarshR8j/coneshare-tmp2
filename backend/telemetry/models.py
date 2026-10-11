"""Telemetry app: kiln hourly data, ingest, and guarded read APIs.

Holds one row per hour per telemetry dataset (see TelemetryDataset).
The public share viewer reaches these through the share-link slug and
inherits that link's password/email/NDA guards, so a dataroom's
"Access to Telemetry" toggle gates the button while the link's own
protections gate the data.
"""
from __future__ import annotations

from django.db import models


class TelemetryDataset(models.Model):
    """One kiln/site's telemetry, attached to a dataroom."""

    dataroom = models.OneToOneField(
        'datarooms.Dataroom',
        on_delete=models.CASCADE,
        related_name='telemetry_dataset',
    )
    name = models.CharField(max_length=255, default='Kiln')
    location = models.CharField(max_length=255, blank=True, default='')

    # MRV factor: t CO2e per tonne of biochar. MUST come from the
    # project's verified methodology - never a guessed constant. The
    # UI shows this value and its source, so keep source_name honest.
    co2e_factor_t_per_t = models.DecimalField(
        max_digits=8, decimal_places=4, null=True, blank=True
    )
    co2e_factor_source = models.CharField(max_length=255, blank=True, default='')

    # Pinned in place while real telemetry flows in, per the concept
    # package: the page ships with simulated rows until the edge
    # logger feed replaces them.
    is_simulated = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Matches the local convention used across this codebase.
        abstract = False

    def __str__(self) -> str:
        return f"{self.name} ({self.dataroom_id})"


class TelemetryReading(models.Model):
    """Immutable raw reading at 1-5 minute cadence.

    Corrections are new rows carrying a reason; existing rows are never
    edited, so the audit trail stays intact. (dataset, ts) is unique,
    so re-ingesting the same file replaces the prior row for that
    instant instead of duplicating it.
    """

    dataset = models.ForeignKey(
        TelemetryDataset, on_delete=models.CASCADE, related_name='readings'
    )
    ts = models.DateTimeField()  # naive UTC, as exported

    operating_state = models.CharField(max_length=64, blank=True, default='')

    feed_kg_rate = models.FloatField(null=True, blank=True)  # kg/h
    char_kg_rate = models.FloatField(null=True, blank=True)  # kg/h
    temp_pyrolysis = models.FloatField(null=True, blank=True)  # deg C
    temp_finishing = models.FloatField(null=True, blank=True)  # deg C
    syngas_nm3h = models.FloatField(null=True, blank=True)
    drum_rpm = models.FloatField(null=True, blank=True)

    # SIM-only channels kept raw; not part of the hourly contract.
    reactor_pressure_mbar = models.FloatField(null=True, blank=True)
    flue_gas_line_pressure_mbar = models.FloatField(null=True, blank=True)

    source_name = models.CharField(max_length=255, blank=True, default='')
    correction_reason = models.CharField(max_length=255, blank=True, default='')
    # Any column outside COLUMN_MAP is parked here rather than dropped.
    extra = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['ts']
        constraints = [
            models.UniqueConstraint(
                fields=['dataset', 'ts'], name='telemetry_reading_unique'
            )
        ]
        indexes = [
            models.Index(fields=['dataset', 'ts'], name='telemetry_reading_ds_ts'),
        ]

    def __str__(self) -> str:
        return f"{self.dataset_id} {self.ts.isoformat()}"


class TelemetryHourly(models.Model):
    """One row per hour, derived from 1-5 minute raw readings.

    Stored in UTC; the UI renders Asia/Kolkata. See
    kiln-dashboard-build-guidelines.md for the data contract.
    """

    dataset = models.ForeignKey(
        TelemetryDataset, on_delete=models.CASCADE, related_name='hourly'
    )
    ts = models.DateTimeField()  # start of the hour, UTC

    running = models.BooleanField(default=False)

    temp_drying = models.FloatField(null=True, blank=True)  # deg C
    temp_pyrolysis = models.FloatField(null=True, blank=True)
    temp_finishing = models.FloatField(null=True, blank=True)

    feed_kg = models.FloatField(default=0.0)  # husk in during the hour
    char_kg = models.FloatField(default=0.0)  # biochar out during the hour
    syngas_nm3h = models.FloatField(null=True, blank=True)  # hourly mean
    drum_rpm = models.FloatField(null=True, blank=True)  # hourly mean
    quality = models.FloatField(default=1.0)  # 0..1, share received

    class Meta:
        ordering = ['ts']
        constraints = [
            models.UniqueConstraint(
                fields=['dataset', 'ts'], name='telemetry_hourly_unique'
            )
        ]
        indexes = [
            models.Index(fields=['dataset', 'ts'], name='telemetry_hourly_ds_ts'),
        ]

    def __str__(self) -> str:
        return f"{self.dataset_id} {self.ts.isoformat()}"


class TelemetryEvent(models.Model):
    """Started / stopped / out-of-range entries for the event log."""

    KIND_CHOICES = [
        ('started', 'Started'),
        ('stopped', 'Stopped'),
        ('out_of_range', 'Temperature out of range'),
    ]

    dataset = models.ForeignKey(
        TelemetryDataset, on_delete=models.CASCADE, related_name='events'
    )
    ts = models.DateTimeField()
    kind = models.CharField(max_length=32, choices=KIND_CHOICES)
    detail = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        ordering = ['ts']
        indexes = [
            models.Index(fields=['dataset', 'ts'], name='telemetry_event_ds_ts'),
        ]

    def __str__(self) -> str:
        return f"{self.kind} @ {self.ts.isoformat()}"
