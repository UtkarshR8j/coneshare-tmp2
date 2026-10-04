"""Serializers for the telemetry read and ingest APIs."""
from __future__ import annotations

from rest_framework import serializers

from .models import TelemetryDataset, TelemetryEvent, TelemetryHourly


class TelemetryDatasetSerializer(serializers.ModelSerializer):
    """Owner-facing dataset record (name, MRV factor, simulated flag)."""

    dataroom_name = serializers.CharField(source='dataroom.name', read_only=True)

    class Meta:
        model = TelemetryDataset
        fields = [
            'id', 'dataroom', 'dataroom_name', 'name', 'location',
            'co2e_factor_t_per_t', 'co2e_factor_source', 'is_simulated',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['is_simulated', 'created_at', 'updated_at']


class TelemetryHourlySerializer(serializers.ModelSerializer):
    class Meta:
        model = TelemetryHourly
        fields = [
            'ts', 'running', 'temp_drying', 'temp_pyrolysis', 'temp_finishing',
            'feed_kg', 'char_kg', 'syngas_nm3h', 'drum_rpm', 'quality',
        ]


class TelemetryEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = TelemetryEvent
        fields = ['ts', 'kind', 'detail']


class TelemetryIngestSerializer(serializers.Serializer):
    """Multipart upload of a Bluelayer SIM workbook."""

    file = serializers.FileField()
    source_name = serializers.CharField(required=False, allow_blank=True, default='')
    correction_reason = serializers.CharField(
        required=False,
        allow_blank=True,
        default='',
        help_text="Reason for this ingest. A correction replaces prior rows "
                  "for the same instants; it never edits rows already stored.",
    )
