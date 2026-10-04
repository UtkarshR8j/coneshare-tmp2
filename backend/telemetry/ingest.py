"""Ingest telemetry from the Bluelayer SIM Excel export.

The workbook layout matches /opt/data/simulation/august_2026_report.xlsx
(made by make_august_excel.py):

  Sheet "Raw Telemetry (10-min)"
    timestamp, operating_state, feed_rate_kg_per_h,
    inner_chamber_temp_celsius, outer_chamber_temp_celsius,
    biochar_output_flow_kg_per_h, reactor_pressure_mbar,
    flue_gas_line_pressure_mbar, flue_gas_flowrate_m3_per_h

We read that sheet, store immutable raw rows, then rebuild the hourly
table for the touched window. Corrections are new raw rows with a
reason - never edits to rows already stored.
"""
from __future__ import annotations

import datetime as dt
import logging
from io import BytesIO
from typing import Any

import openpyxl

from .aggregator import build_events_from_hourly, build_hourly_from_raw
from .models import TelemetryDataset, TelemetryReading

logger = logging.getLogger(__name__)

RAW_SHEET_CANDIDATES = ('Raw Telemetry (10-min)', 'Raw Telemetry', 'Raw Telemetry (10 min)')

REQUIRED_COLUMNS = ('timestamp', 'feed_rate_kg_per_h', 'inner_chamber_temp_celsius')

# Bluelayer SIM column -> TelemetryReading field. Unlisted columns are
# kept in the opaque `extra` JSON so nothing is silently dropped.
COLUMN_MAP = {
    'timestamp': 'ts',
    'feed_rate_kg_per_h': 'feed_kg_rate',
    'inner_chamber_temp_celsius': 'temp_pyrolysis',
    'outer_chamber_temp_celsius': 'temp_finishing',
    'biochar_output_flow_kg_per_h': 'char_kg_rate',
    'reactor_pressure_mbar': 'reactor_pressure_mbar',
    'flue_gas_line_pressure_mbar': 'flue_gas_line_pressure_mbar',
    'flue_gas_flowrate_m3_per_h': 'syngas_nm3h',
    'operating_state': 'operating_state',
    'drum_rpm': 'drum_rpm',
}


class IngestError(ValueError):
    """Raised when the workbook does not match the expected format."""


def _to_float(value: Any) -> float | None:
    if value is None or value == '':
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _to_datetime(value: Any) -> dt.datetime | None:
    if value is None or value == '':
        return None
    if isinstance(value, dt.datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    if isinstance(value, dt.date):
        return dt.datetime(value.year, value.month, value.day)
    text = str(value).strip()
    for fmt in ('%Y-%m-%d %H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            return dt.datetime.strptime(text, fmt)
        except ValueError:
            continue
    try:
        from openpyxl.utils.datetime import from_excel

        return from_excel(float(text))
    except Exception:
        return None


def _find_raw_sheet(workbook: openpyxl.Workbook) -> openpyxl.worksheet.worksheet.Worksheet:
    for name in RAW_SHEET_CANDIDATES:
        if name in workbook.sheetnames:
            return workbook[name]
    raise IngestError(
        "Workbook has no raw telemetry sheet. Expected one of: "
        + ", ".join(RAW_SHEET_CANDIDATES)
    )


def _read_rows(workbook: openpyxl.Workbook) -> list[dict[str, Any]]:
    sheet = _find_raw_sheet(workbook)
    rows = sheet.iter_rows(values_only=True)
    try:
        header = next(rows)
    except StopIteration:
        raise IngestError("Raw telemetry sheet is empty.")

    header = [str(h).strip() if h is not None else '' for h in header]
    missing = [c for c in REQUIRED_COLUMNS if c not in header]
    if missing:
        raise IngestError(
            "Raw telemetry sheet is missing required columns: " + ", ".join(missing)
        )

    out: list[dict[str, Any]] = []
    for raw in rows:
        if raw is None or all(v is None or v == '' for v in raw):
            continue
        record: dict[str, Any] = {}
        for key, value in zip(header, raw):
            if not key:
                continue
            field = COLUMN_MAP.get(key)
            if field is None:
                record.setdefault('extra', {})[key] = value
            else:
                record[field] = value
        out.append(record)
    return out


def ingest_excel(
    dataset: TelemetryDataset,
    payload: bytes,
    source_name: str = '',
    reason: str = '',
) -> dict[str, Any]:
    """Parse a Bluelayer SIM workbook, store raw rows, rebuild hourly.

    Returns a summary dict. Ingesting the same file twice is safe: raw
    rows are deduplicated on (dataset, ts), and the hourly table is
    rebuilt over the touched window.
    """
    try:
        workbook = openpyxl.load_workbook(BytesIO(payload), read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001 - surfaced to the caller
        raise IngestError(f"Could not read workbook: {exc}") from exc

    try:
        records = _read_rows(workbook)
    finally:
        try:
            workbook.close()
        except Exception:  # noqa: BLE001
            pass

    parsed: list[TelemetryReading] = []
    skipped = 0
    extra_keys: set[str] = set()
    for rec in records:
        ts = _to_datetime(rec.get('ts'))
        if ts is None:
            skipped += 1
            continue
        extra = rec.get('extra') or {}
        extra_keys.update(extra.keys())
        parsed.append(
            TelemetryReading(
                dataset=dataset,
                ts=ts,
                operating_state=str(rec.get('operating_state') or ''),
                feed_kg_rate=_to_float(rec.get('feed_kg_rate')),
                char_kg_rate=_to_float(rec.get('char_kg_rate')),
                temp_pyrolysis=_to_float(rec.get('temp_pyrolysis')),
                temp_finishing=_to_float(rec.get('temp_finishing')),
                syngas_nm3h=_to_float(rec.get('syngas_nm3h')),
                drum_rpm=_to_float(rec.get('drum_rpm')),
                reactor_pressure_mbar=_to_float(rec.get('reactor_pressure_mbar')),
                flue_gas_line_pressure_mbar=_to_float(
                    rec.get('flue_gas_line_pressure_mbar')
                ),
                source_name=source_name,
                correction_reason=reason,
                extra=extra,
            )
        )

    if not parsed:
        raise IngestError(
            "No usable rows found (every row lacked a parseable timestamp)."
        )

    from django.db import transaction

    with transaction.atomic():
        # Deduplicate on (dataset, ts): an ingest with a reason is a
        # correction and supersedes the prior row for that instant.
        incoming = {r.ts for r in parsed}
        TelemetryReading.objects.filter(dataset=dataset, ts__in=incoming).delete()
        TelemetryReading.objects.bulk_create(parsed, batch_size=1000)

        since = min(incoming)
        until = max(incoming) + dt.timedelta(hours=1)
        hourly_written = build_hourly_from_raw(dataset, since=since, until=until)
        events_written = build_events_from_hourly(dataset)

    dataset.is_simulated = False
    dataset.save(update_fields=['is_simulated', 'updated_at'])

    return {
        'raw_rows': len(parsed),
        'skipped_rows': skipped,
        'hourly_rows': hourly_written,
        'events': events_written,
        'window_start': since.isoformat(),
        'window_end': (until - dt.timedelta(hours=1)).isoformat(),
        'extra_columns_kept': sorted(extra_keys),
    }
