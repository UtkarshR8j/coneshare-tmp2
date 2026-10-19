"""Telemetry views.

Owner routes reuse the dataroom permission gate so anyone who can edit
the dataroom can manage its telemetry. The public route resolves the
share link and runs the same protection checks the viewer runs, so a
password-protected dataroom stays protected here too.
"""
from __future__ import annotations

import datetime as dt
import logging

from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from datarooms.models import Dataroom
from datarooms.views import is_dataroom_owner_or_admin
from sharelinks.models import ShareLink
from sharelinks.views import _is_nda_accepted

from .ingest import IngestError, ingest_excel
from .models import TelemetryDataset, TelemetryEvent, TelemetryHourly
from .serializers import (
    TelemetryDatasetSerializer,
    TelemetryEventSerializer,
    TelemetryHourlySerializer,
    TelemetryIngestSerializer,
)

logger = logging.getLogger(__name__)

# The page is a pure function of one compact payload: hourly rows for
# the window plus events. 12 months of hourly rows is 8,760 rows.
MAX_HOURS = 24 * 370


def _get_dataset_or_404(dataroom_id: str, user) -> TelemetryDataset:
    # Dataroom pks are ULIDs; a non-ULID segment must 404 rather than
    # raise out of the field's from_db_value.
    try:
        dataroom = get_object_or_404(Dataroom, pk=dataroom_id)
    except (ValueError, ValidationError):
        raise Http404("Dataroom not found.")
    if not is_dataroom_owner_or_admin(user, dataroom):
        raise PermissionDenied("You do not have access to this dataroom.")
    dataset, _created = TelemetryDataset.objects.get_or_create(dataroom=dataroom)
    return dataset


class TelemetryDatasetDetailView(APIView):
    """GET the dataset record, PATCH its name / MRV factor / location."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, dataroom_id):
        dataset = _get_dataset_or_404(dataroom_id, request.user)
        return Response(TelemetryDatasetSerializer(dataset).data)

    def patch(self, request, dataroom_id):
        dataset = _get_dataset_or_404(dataroom_id, request.user)
        serializer = TelemetryDatasetSerializer(
            dataset, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


@method_decorator(csrf_exempt, name='dispatch')
class TelemetryIngestView(APIView):
    """Upload a Bluelayer SIM workbook and rebuild the hourly table."""

    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request, dataroom_id):
        dataset = _get_dataset_or_404(dataroom_id, request.user)
        form = TelemetryIngestSerializer(data=request.data)
        form.is_valid(raise_exception=True)

        payload = form.validated_data['file'].read()
        try:
            summary = ingest_excel(
                dataset,
                payload,
                source_name=form.validated_data.get('source_name') or '',
                reason=form.validated_data.get('correction_reason') or '',
            )
        except IngestError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:  # noqa: BLE001
            logger.exception("Telemetry ingest failed for dataset %s", dataset.pk)
            return Response(
                {'detail': 'Ingest failed while building the hourly table.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response(summary)


class TelemetryHourlyListView(APIView):
    """Hourly rows and events for a window - the owner-side read API."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, dataroom_id):
        dataset = _get_dataset_or_404(dataroom_id, request.user)
        since, until = self._parse_window(request)
        hours = TelemetryHourly.objects.filter(
            dataset=dataset, ts__gte=since, ts__lt=until
        ).order_by('ts')[:MAX_HOURS]
        events = TelemetryEvent.objects.filter(
            dataset=dataset, ts__gte=since, ts__lt=until
        ).order_by('ts')
        return Response({
            'dataset': TelemetryDatasetSerializer(dataset).data,
            'hourly': TelemetryHourlySerializer(hours, many=True).data,
            'events': TelemetryEventSerializer(events, many=True).data,
        })

    @staticmethod
    def _parse_window(request) -> tuple[dt.datetime, dt.datetime]:
        raw_since = request.query_params.get('since')
        raw_until = request.query_params.get('until')
        since = parse_datetime(raw_since) if raw_since else None
        until = parse_datetime(raw_until) if raw_until else None
        if since is None:
            since = timezone.now() - dt.timedelta(days=370)
        if until is None:
            until = timezone.now() + dt.timedelta(days=1)
        if since.tzinfo is None:
            since = timezone.make_aware(since)
        if until.tzinfo is None:
            until = timezone.make_aware(until)
        if until <= since:
            raise ValidationError({'until': 'Must be after since.'})
        return since, until


class PublicTelemetryView(APIView):
    """The payload the public telemetry page fetches.

    Reachable through the share link slug, gated exactly like the
    viewer: active link, unexpired, password / email / NDA cleared in
    this session, and the dataroom's telemetry toggle on.
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request, slug):
        link = ShareLink.objects.select_related(
            'dataroom'
        ).filter(slug=slug, is_active=True).first()
        if link is None:
            raise Http404("Share link not found.")
        if link.expires_at and link.expires_at < timezone.now():
            return Response({'message': 'This link has expired.'}, status=status.HTTP_410_GONE)
        if link.dataroom is None:
            raise Http404("This link does not expose a dataroom.")
        if not link.dataroom.enable_telemetry_access:
            raise PermissionDenied("Telemetry access is disabled for this dataroom.")

        # Same session authorization the viewer writes once its own
        # checks pass; a viewer who never cleared the password does not
        # get to read telemetry through this slug.
        auth_status = request.session.get('authorized_share_links', {}).get(str(link.id), {})
        if link.password and not auth_status.get('password_verified'):
            return Response(
                {'message': 'This link is password-protected. Please enter the password to continue.',
                 'protectionType': 'password'},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        if link.requires_email and not auth_status.get('email_verified'):
            return Response(
                {'message': 'This link requires an email address to view.',
                 'protectionType': 'email'},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        if link.require_nda and not _is_nda_accepted(link, request, auth_status):
            return Response(
                {'message': 'NDA acceptance is required to view this content.',
                 'protectionType': 'nda'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        dataset = getattr(link.dataroom, 'telemetry_dataset', None)
        if dataset is None:
            raise Http404("No telemetry is attached to this dataroom.")

        since, until = TelemetryHourlyListView._parse_window(request)
        hours = TelemetryHourly.objects.filter(
            dataset=dataset, ts__gte=since, ts__lt=until
        ).order_by('ts')[:MAX_HOURS]
        events = TelemetryEvent.objects.filter(
            dataset=dataset, ts__gte=since, ts__lt=until
        ).order_by('ts')

        return Response({
            'name': dataset.name,
            'location': dataset.location,
            'is_simulated': dataset.is_simulated,
            'co2e_factor_t_per_t': (
                float(dataset.co2e_factor_t_per_t)
                if dataset.co2e_factor_t_per_t is not None else None
            ),
            'co2e_factor_source': dataset.co2e_factor_source,
            'generated_at': timezone.now().isoformat(),
            'hourly': TelemetryHourlySerializer(hours, many=True).data,
            'events': TelemetryEventSerializer(events, many=True).data,
        })
