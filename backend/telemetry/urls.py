"""URLs for the telemetry app.

Owner routes sit under /api/v1/ alongside the other authenticated
endpoints. The public read routes live under /api/v1/links/<slug>/
telemetry/ so the share viewer reaches them with the same slug it
already uses, and inherit that link's guards.
"""
from django.urls import path

from . import views

urlpatterns = [
    # Owner (authenticated). Dataroom ids are ULIDs, so the converter
    # must be <str:>, not <int:> - an <int:> route never matches.
    path(
        'datarooms/<str:dataroom_id>/telemetry/',
        views.TelemetryDatasetDetailView.as_view(),
        name='telemetry-dataset-detail',
    ),
    path(
        'datarooms/<str:dataroom_id>/telemetry/ingest/',
        views.TelemetryIngestView.as_view(),
        name='telemetry-ingest',
    ),
    path(
        'datarooms/<str:dataroom_id>/telemetry/hourly/',
        views.TelemetryHourlyListView.as_view(),
        name='telemetry-hourly-list',
    ),
    # Public (guarded by the share link's own protections)
    path(
        'links/<slug:slug>/telemetry/',
        views.PublicTelemetryView.as_view(),
        name='public-telemetry',
    ),
]
