"""Tests for the telemetry app: ingest, hourly aggregation, guarded reads."""
from __future__ import annotations

import datetime as dt
import io

import openpyxl
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APIClient

from datarooms.models import Dataroom
from sharelinks.models import ShareLink
from telemetry.ingest import IngestError, ingest_excel
from telemetry.models import TelemetryDataset, TelemetryEvent, TelemetryHourly, TelemetryReading

pytestmark = pytest.mark.django_db

RAW_HEADER = [
    'timestamp', 'operating_state', 'feed_rate_kg_per_h',
    'inner_chamber_temp_celsius', 'outer_chamber_temp_celsius',
    'biochar_output_flow_kg_per_h', 'reactor_pressure_mbar',
    'flue_gas_line_pressure_mbar', 'flue_gas_flowrate_m3_per_h',
]


def make_workbook(rows: list[list], header: list[str] | None = None) -> bytes:
    """Build a Bluelayer SIM workbook in memory."""
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = 'Raw Telemetry (10-min)'
    ws.append(header if header is not None else RAW_HEADER)
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    wb.close()
    return buf.getvalue()


def sim_rows(start: dt.datetime, hours: int, running: bool = True) -> list[list]:
    """Six 10-minute samples per hour, matching the SIM cadence."""
    rows = []
    for h in range(hours):
        base = start + dt.timedelta(hours=h)
        for step in range(6):
            ts = base + dt.timedelta(minutes=10 * step)
            rows.append([
                ts.strftime('%Y-%m-%d %H:%M'),
                'Running' if running else 'Stopped',
                120.0 if running else 0.0,      # feed_rate_kg_per_h
                500.0 if running else 80.0,     # inner (pyrolysis)
                300.0 if running else 60.0,     # outer (finishing)
                40.0 if running else 0.0,       # biochar flow
                1013.0,
                1010.0,
                25.0 if running else 0.0,       # syngas
            ])
    return rows


@pytest.fixture
def dataset(dataroom):
    return TelemetryDataset.objects.create(
        dataroom=dataroom, name='Kiln 1', location='Kusumkhunti, Kalahandi'
    )


@pytest.fixture
def window_start():
    return dt.datetime(2026, 8, 1, 0, 0)


class TestIngest:
    def test_ingest_builds_hourly_rows(self, dataset, window_start):
        payload = make_workbook(sim_rows(window_start, hours=6))
        summary = ingest_excel(dataset, payload, source_name='august_2026_report.xlsx')

        assert summary['raw_rows'] == 36
        assert summary['hourly_rows'] == 6
        assert TelemetryHourly.objects.filter(dataset=dataset).count() == 6
        # A real ingest clears the simulated placeholder flag.
        dataset.refresh_from_db()
        assert dataset.is_simulated is False

        first = TelemetryHourly.objects.filter(dataset=dataset).order_by('ts').first()
        assert first.running is True
        # 120 kg/h held for the whole hour -> 120 kg in the hour.
        assert first.feed_kg == pytest.approx(120.0, rel=0.01)
        assert first.temp_pyrolysis == pytest.approx(500.0, rel=0.01)
        assert first.quality == pytest.approx(1.0)

    def test_ingest_is_idempotent(self, dataset, window_start):
        payload = make_workbook(sim_rows(window_start, hours=3))
        ingest_excel(dataset, payload, source_name='a.xlsx')
        ingest_excel(dataset, payload, source_name='a.xlsx')

        assert TelemetryReading.objects.filter(dataset=dataset).count() == 18
        assert TelemetryHourly.objects.filter(dataset=dataset).count() == 3

    def test_reingest_with_reason_supersedes_rows(self, dataset, window_start):
        """A correction is a new row with a reason, not a silent edit."""
        ingest_excel(dataset, make_workbook(sim_rows(window_start, hours=2)), source_name='orig.xlsx')

        corrected = sim_rows(window_start, hours=2)
        for row in corrected:
            row[3] = 520.0  # corrected pyrolysis temperature
        ingest_excel(
            dataset, make_workbook(corrected),
            source_name='corrected.xlsx', reason='thermocouple recalibrated',
        )

        readings = TelemetryReading.objects.filter(dataset=dataset).order_by('ts')
        assert readings.count() == 12  # not doubled
        assert readings.first().correction_reason == 'thermocouple recalibrated'
        hourly = TelemetryHourly.objects.filter(dataset=dataset).order_by('ts').first()
        assert hourly.temp_pyrolysis == pytest.approx(520.0, rel=0.01)

    def test_rejects_workbook_without_raw_sheet(self, dataset):
        wb = openpyxl.Workbook()
        wb.active.title = 'Summary'
        buf = io.BytesIO()
        wb.save(buf)
        with pytest.raises(IngestError):
            ingest_excel(dataset, buf.getvalue())

    def test_rejects_missing_required_columns(self, dataset):
        payload = make_workbook([['2026-08-01 00:00', 1.0]], header=['timestamp', 'other'])
        with pytest.raises(IngestError) as exc:
            ingest_excel(dataset, payload)
        assert 'feed_rate_kg_per_h' in str(exc.value)

    def test_skips_rows_without_timestamp(self, dataset):
        rows = sim_rows(dt.datetime(2026, 8, 1), hours=1)
        rows.append(['not-a-date', 'Running', 1, 1, 1, 1, 1, 1, 1])
        summary = ingest_excel(dataset, make_workbook(rows))
        assert summary['raw_rows'] == 6
        assert summary['skipped_rows'] == 1

    def test_unknown_columns_are_kept_not_dropped(self, dataset):
        header = RAW_HEADER + ['custom_sensor']
        rows = [r + [42] for r in sim_rows(dt.datetime(2026, 8, 1), hours=1)]
        summary = ingest_excel(dataset, make_workbook(rows, header=header))
        assert 'custom_sensor' in summary['extra_columns_kept']
        reading = TelemetryReading.objects.filter(dataset=dataset).first()
        assert reading.extra['custom_sensor'] == 42

    def test_stopped_hour_is_not_running(self, dataset):
        payload = make_workbook(sim_rows(dt.datetime(2026, 8, 1), hours=2, running=False))
        ingest_excel(dataset, payload)
        hours = TelemetryHourly.objects.filter(dataset=dataset).order_by('ts')
        assert all(h.running is False for h in hours)
        assert all(h.feed_kg == 0.0 for h in hours)


class TestEvents:
    def test_events_derived_from_hourly(self, dataset):
        # 3 running hours then 3 stopped hours.
        start = dt.datetime(2026, 8, 1, 0, 0)
        rows = sim_rows(start, hours=3, running=True) + sim_rows(
            start + dt.timedelta(hours=3), hours=3, running=False
        )
        ingest_excel(dataset, make_workbook(rows))

        pairs = list(
            TelemetryEvent.objects.filter(dataset=dataset)
            .order_by('ts').values_list('ts', 'kind')
        )
        # A transition running -> stopped is one 'stopped' event. The
        # dataset starts with no prior state, so the first hour cannot
        # emit a 'started' - that would be a guess about the past.
        kinds = [k for _, k in pairs]
        assert kinds == ['stopped']

    def test_out_of_range_emits_event(self, dataset):
        rows = sim_rows(dt.datetime(2026, 8, 1), hours=2, running=True)
        for row in rows:
            row[3] = 620.0  # above the 450-550 band
        ingest_excel(dataset, make_workbook(rows))
        assert TelemetryEvent.objects.filter(
            dataset=dataset, kind='out_of_range'
        ).exists()


class TestOwnerApi:
    def test_ingest_endpoint(self, api_client, dataroom):
        payload = make_workbook(sim_rows(dt.datetime(2026, 8, 1), hours=4))
        upload = SimpleUploadedFile('sim.xlsx', payload, content_type='application/vnd.ms-excel')

        resp = api_client.post(
            f'/api/v1/datarooms/{dataroom.id}/telemetry/ingest/',
            {'file': upload}, format='multipart',
        )
        assert resp.status_code == status.HTTP_200_OK, resp.data
        assert resp.data['hourly_rows'] == 4

    def test_ingest_endpoint_rejects_garbage(self, api_client, dataroom):
        upload = SimpleUploadedFile('bad.xlsx', b'not a workbook', content_type='application/ms-excel')
        resp = api_client.post(
            f'/api/v1/datarooms/{dataroom.id}/telemetry/ingest/',
            {'file': upload}, format='multipart',
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_hourly_read_requires_auth(self, dataroom):
        client = APIClient()
        resp = client.get(f'/api/v1/datarooms/{dataroom.id}/telemetry/hourly/')
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_hourly_read_scoped_to_other_users_dataroom(
        self, api_client, user2, organization
    ):
        other = Dataroom.objects.create(
            name='Other', organization=organization, created_by=user2
        )
        resp = api_client.get(f'/api/v1/datarooms/{other.id}/telemetry/hourly/')
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_hourly_read_returns_window(self, api_client, dataroom):
        payload = make_workbook(sim_rows(dt.datetime(2026, 8, 1), hours=5))
        ingest_excel(
            TelemetryDataset.objects.create(dataroom=dataroom, name='Kiln 1'),
            payload, source_name='x.xlsx',
        )
        resp = api_client.get(
            f'/api/v1/datarooms/{dataroom.id}/telemetry/hourly/',
            {'since': '2026-08-01T00:00:00Z', 'until': '2026-08-01T05:00:00Z'},
        )
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data['hourly']) == 5

    def test_hourly_read_rejects_inverted_window(self, api_client, dataroom):
        resp = api_client.get(
            f'/api/v1/datarooms/{dataroom.id}/telemetry/hourly/',
            {'since': '2026-08-02T00:00:00Z', 'until': '2026-08-01T00:00:00Z'},
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_dataset_patch_updates_mrv_factor(self, api_client, dataroom):
        resp = api_client.patch(
            f'/api/v1/datarooms/{dataroom.id}/telemetry/',
            {'co2e_factor_t_per_t': '2.4000', 'co2e_factor_source': 'ISCC ARB'},
            format='json',
        )
        assert resp.status_code == status.HTTP_200_OK
        # DRF's default COERCE_DECIMAL_TO_STRING sends Decimals as
        # strings so JSON precision is not lost.
        assert resp.data['co2e_factor_t_per_t'] == '2.4000'
        assert resp.data['co2e_factor_source'] == 'ISCC ARB'

    def test_dataset_patch_bad_decimal_rejected(self, api_client, dataroom):
        resp = api_client.patch(
            f'/api/v1/datarooms/{dataroom.id}/telemetry/',
            {'co2e_factor_t_per_t': 'not-a-number'},
            format='json',
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


@pytest.fixture
def dataroom_share_link(dataroom, user):
    """An active share link into a dataroom (no password)."""
    return ShareLink.objects.create(
        dataroom=dataroom, created_by=user, name='Room link'
    )


def _authorize(client: APIClient, link: ShareLink):
    """Mirror the session keys the viewer writes once checks pass."""
    session = client.session
    session['authorized_share_links'] = {
        str(link.id): {
            'password_verified': True,
            'email_verified': True,
            'viewer_email': '',
            'nda_accepted_version': 0,
        }
    }
    session.save()


class TestPublicRead:
    @pytest.fixture
    def seeded(self, dataroom_share_link):
        dataroom = dataroom_share_link.dataroom
        dataset = TelemetryDataset.objects.create(dataroom=dataroom, name='Kiln 1')
        payload = make_workbook(sim_rows(dt.datetime(2026, 8, 1), hours=6))
        ingest_excel(dataset, payload, source_name='x.xlsx')
        return dataroom_share_link

    def test_public_read_blocked_when_toggle_off(self, seeded):
        client = APIClient()
        _authorize(client, seeded)
        resp = client.get(f'/api/v1/links/{seeded.slug}/telemetry/')
        # enable_telemetry_access defaults to False.
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_public_read_open_when_toggle_on_and_authorized(self, seeded):
        dataroom = seeded.dataroom
        dataroom.enable_telemetry_access = True
        dataroom.save(update_fields=['enable_telemetry_access'])

        client = APIClient()
        _authorize(client, seeded)
        resp = client.get(
            f'/api/v1/links/{seeded.slug}/telemetry/',
            {'since': '2026-08-01T00:00:00Z', 'until': '2026-08-01T06:00:00Z'},
        )
        assert resp.status_code == status.HTTP_200_OK, resp.data
        assert len(resp.data['hourly']) == 6
        assert resp.data['is_simulated'] is False

    def test_public_read_inherits_password_guard(self, seeded):
        """A viewer who never cleared the password gets no telemetry."""
        dataroom = seeded.dataroom
        dataroom.enable_telemetry_access = True
        dataroom.save(update_fields=['enable_telemetry_access'])
        seeded.password = 'secret123'
        seeded.save(update_fields=['password'])

        client = APIClient()  # no session authorization at all
        resp = client.get(f'/api/v1/links/{seeded.slug}/telemetry/')
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
        assert resp.data['protectionType'] == 'password'

    def test_public_read_allows_authorized_password_session(self, seeded):
        dataroom = seeded.dataroom
        dataroom.enable_telemetry_access = True
        dataroom.save(update_fields=['enable_telemetry_access'])
        seeded.password = 'secret123'
        seeded.save(update_fields=['password'])

        client = APIClient()
        _authorize(client, seeded)
        resp = client.get(f'/api/v1/links/{seeded.slug}/telemetry/')
        assert resp.status_code == status.HTTP_200_OK

    def test_public_read_requires_email_when_link_does(self, seeded):
        dataroom = seeded.dataroom
        dataroom.enable_telemetry_access = True
        dataroom.save(update_fields=['enable_telemetry_access'])
        seeded.requires_email = True
        seeded.save(update_fields=['requires_email'])

        client = APIClient()  # no email verified in session
        resp = client.get(f'/api/v1/links/{seeded.slug}/telemetry/')
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
        assert resp.data['protectionType'] == 'email'

    def test_public_read_missing_dataset_404(self, dataroom_share_link):
        dataroom = dataroom_share_link.dataroom
        dataroom.enable_telemetry_access = True
        dataroom.save(update_fields=['enable_telemetry_access'])

        client = APIClient()
        _authorize(client, dataroom_share_link)
        resp = client.get(f'/api/v1/links/{dataroom_share_link.slug}/telemetry/')
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_public_read_unknown_slug_404(self):
        client = APIClient()
        resp = client.get('/api/v1/links/nope-not-real/telemetry/')
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_public_read_expired_link_410(self, seeded):
        dataroom = seeded.dataroom
        dataroom.enable_telemetry_access = True
        dataroom.save(update_fields=['enable_telemetry_access'])
        seeded.expires_at = dt.datetime(2020, 1, 1, tzinfo=dt.timezone.utc)
        seeded.save(update_fields=['expires_at'])

        client = APIClient()
        _authorize(client, seeded)
        resp = client.get(f'/api/v1/links/{seeded.slug}/telemetry/')
        assert resp.status_code == status.HTTP_410_GONE

    def test_public_read_inactive_link_404(self, seeded):
        dataroom = seeded.dataroom
        dataroom.enable_telemetry_access = True
        dataroom.save(update_fields=['enable_telemetry_access'])
        seeded.is_active = False
        seeded.save(update_fields=['is_active'])

        client = APIClient()
        _authorize(client, seeded)
        resp = client.get(f'/api/v1/links/{seeded.slug}/telemetry/')
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_document_link_with_no_dataroom_404(self, share_link):
        """A link to a single document exposes no dataroom telemetry."""
        client = APIClient()
        _authorize(client, share_link)
        resp = client.get(f'/api/v1/links/{share_link.slug}/telemetry/')
        assert resp.status_code == status.HTTP_404_NOT_FOUND
