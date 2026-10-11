"""Build the hourly telemetry table from raw readings.

Raw readings arrive at 1-5 minute intervals (see ingest.py). This
module derives one TelemetryHourly row per hour per dataset: means for
temperatures and rates, sums for mass, a running flag, and a quality
score for how much of the hour actually showed up.

Deduplicated and idempotent: re-running over the same raw window
overwrites the derived rows for that window rather than duplicating.
"""
from __future__ import annotations

import datetime as dt
import logging
from typing import Iterable

from django.db import transaction
from django.utils import timezone

from .models import TelemetryHourly, TelemetryReading

logger = logging.getLogger(__name__)

# Expected readings per hour at the 10-minute export cadence used by
# the Bluelayer SIM workbook. Quality is measured against this.
EXPECTED_PER_HOUR = 6


def _hour_floor(ts: dt.datetime) -> dt.datetime:
    """Floor a timestamp to the start of its hour, naive-UTC."""
    return ts.replace(minute=0, second=0, microsecond=0)


def build_hourly_from_raw(
    dataset, since: dt.datetime | None = None, until: dt.datetime | None = None
) -> int:
    """Aggregate raw readings into hourly rows.

    Returns the number of hourly rows written.
    """
    readings = TelemetryReading.objects.filter(dataset=dataset)
    if since is not None:
        readings = readings.filter(ts__gte=since)
    if until is not None:
        readings = readings.filter(ts__lt=until)
    readings = readings.order_by('ts')

    buckets: dict[dt.datetime, list] = {}
    for r in readings.iterator(chunk_size=2000):
        hour = _hour_floor(r.ts)
        buckets.setdefault(hour, []).append(r)

    if not buckets:
        return 0

    rows: list[TelemetryHourly] = []
    for hour, raws in buckets.items():
        n = len(raws)

        temps_pyr = [x.temp_pyrolysis for x in raws if x.temp_pyrolysis is not None]
        temps_fin = [x.temp_finishing for x in raws if x.temp_finishing is not None]
        syngas = [x.syngas_nm3h for x in raws if x.syngas_nm3h is not None]
        rpm = [x.drum_rpm for x in raws if x.drum_rpm is not None]

        # Mass: rate (kg/h) sampled n times over the hour, each sample
        # covering 1/n of the hour -> sum(rate)/n is the hour's mass.
        feed_rates = [x.feed_kg_rate for x in raws if x.feed_kg_rate is not None]
        char_rates = [x.char_kg_rate for x in raws if x.char_kg_rate is not None]
        feed_kg = (sum(feed_rates) / n) if feed_rates else 0.0
        char_kg = (sum(char_rates) / n) if char_rates else 0.0

        # Running: drum turning and feed above threshold for most of
        # the hour. The SIM export has no drum channel, so fall back to
        # feed presence plus the exported operating_state.
        running_ticks = 0
        for x in raws:
            state = (x.operating_state or '').strip().lower()
            feed = x.feed_kg_rate or 0.0
            if feed > 0 or state in ('running', 'active', 'on'):
                running_ticks += 1
        running = running_ticks > (n / 2)

        quality = min(1.0, n / EXPECTED_PER_HOUR)

        rows.append(
            TelemetryHourly(
                dataset=dataset,
                ts=hour,
                running=running,
                # The Bluelayer SIM export carries no separate drying
                # channel, so this stays None rather than being
                # guessed from the pyrolysis reading.
                temp_drying=None,
                temp_pyrolysis=(sum(temps_pyr) / len(temps_pyr)) if temps_pyr else None,
                temp_finishing=(sum(temps_fin) / len(temps_fin)) if temps_fin else None,
                feed_kg=feed_kg,
                char_kg=char_kg,
                syngas_nm3h=(sum(syngas) / len(syngas)) if syngas else None,
                drum_rpm=(sum(rpm) / len(rpm)) if rpm else None,
                quality=quality,
            )
        )

    with transaction.atomic():
        # Upsert: clear the derived rows we are about to rewrite.
        hours = [r.ts for r in rows]
        TelemetryHourly.objects.filter(dataset=dataset, ts__in=hours).delete()
        TelemetryHourly.objects.bulk_create(rows, batch_size=500)

    logger.info(
        "Built %d hourly rows for dataset %s (raw hours=%d)",
        len(rows), dataset.pk, len(buckets),
    )
    return len(rows)


def build_events_from_hourly(dataset) -> int:
    """Derive start/stop/out-of-range events from the hourly table."""
    from .models import TelemetryEvent

    hours = list(
        TelemetryHourly.objects.filter(dataset=dataset).order_by('ts')
    )
    events = []
    prev_running = None
    for h in hours:
        if prev_running is not None and h.running != prev_running:
            events.append(
                TelemetryEvent(
                    dataset=dataset,
                    ts=h.ts,
                    kind='started' if h.running else 'stopped',
                    detail='Derived from hourly telemetry',
                )
            )
        # Out of range: pyrolysis outside 450-550 C while running.
        if (
            h.running
            and h.temp_pyrolysis is not None
            and not (450.0 <= h.temp_pyrolysis <= 550.0)
        ):
            events.append(
                TelemetryEvent(
                    dataset=dataset,
                    ts=h.ts,
                    kind='out_of_range',
                    detail=f"Pyrolysis {h.temp_pyrolysis:.0f} C",
                )
            )
        prev_running = h.running

    with transaction.atomic():
        TelemetryEvent.objects.filter(dataset=dataset).delete()
        if events:
            TelemetryEvent.objects.bulk_create(events, batch_size=500)
    return len(events)
