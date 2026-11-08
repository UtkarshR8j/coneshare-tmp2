import mimetypes
import posixpath

from django.http import FileResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import APIKey
from core.permissions import IsAdmin
from core.services import get_dynamic_setting
from datarooms.models import DataroomFolder
from datarooms.views import get_dataroom_queryset_for_user
from . import scanner
from .models import AssetSnapshot
from .serializers import AddAssetsSerializer, AssetSnapshotSerializer
from .tasks import snapshot_asset_task

MIN_QUERY_LENGTH = 2
MAX_SEARCH_LIMIT = 500
# Never SVG or HTML: those could run script on the app origin.
PREVIEW_CONTENT_TYPES = frozenset({'application/pdf', 'image/png', 'image/jpeg', 'image/gif', 'image/webp'})


class IsInteractiveUser(permissions.BasePermission):
    """These routes expose every private OpenCloud file, so scriptable API keys are refused."""
    def has_permission(self, request, view):
        return not isinstance(request.auth, APIKey)


class AssetsBaseView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdmin, IsInteractiveUser]

    def handle_exception(self, exc):
        if isinstance(exc, scanner.AssetsNotConfigured):
            return Response({'detail': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        if isinstance(exc, scanner.InvalidAssetPath):
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        if isinstance(exc, scanner.AssetNotFound):
            return Response({'detail': str(exc)}, status=status.HTTP_404_NOT_FOUND)
        return super().handle_exception(exc)


@extend_schema(tags=['assets'])
class AssetSpacesView(AssetsBaseView):
    def get(self, request):
        return Response(scanner.list_spaces())


@extend_schema(tags=['assets'])
class AssetBrowseView(AssetsBaseView):
    def get(self, request):
        space_id = request.query_params.get('space_id', '')
        path = request.query_params.get('path', '')
        return Response({'space_id': space_id, 'path': path, 'items': scanner.list_dir(space_id, path)})


@extend_schema(tags=['assets'])
class AssetSearchView(AssetsBaseView):
    def get(self, request):
        query = request.query_params.get('q', '').strip()
        if len(query) < MIN_QUERY_LENGTH:
            return Response({'detail': f'Search needs at least {MIN_QUERY_LENGTH} characters.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            limit = min(int(request.query_params.get('limit', 200)), MAX_SEARCH_LIMIT)
        except ValueError:
            return Response({'detail': 'limit must be a number.'}, status=status.HTTP_400_BAD_REQUEST)
        items, truncated = scanner.search(query, request.query_params.get('space_id') or None, max(limit, 1))
        return Response({'items': items, 'truncated': truncated})


@extend_schema(tags=['assets'])
class AssetPreviewView(AssetsBaseView):
    def get(self, request):
        space_id = request.query_params.get('space_id', '')
        path = request.query_params.get('path', '')
        name = posixpath.basename(path)
        content_type = mimetypes.guess_type(name)[0]
        if content_type not in PREVIEW_CONTENT_TYPES:
            scanner.stat_file(space_id, path)  # bad paths and missing files keep their own errors
            return Response({'detail': 'This file type cannot be previewed.'}, status=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)
        response = FileResponse(scanner.open_file(space_id, path), as_attachment=False, filename=name, content_type=content_type)
        response['X-Content-Type-Options'] = 'nosniff'
        return response


def _space_name(space_id, spaces):
    return next((s['name'] for s in spaces if s['id'] == space_id), '')


@extend_schema(tags=['assets'])
class DataroomAssetsAddView(AssetsBaseView):
    def post(self, request, dataroom_id):
        room = get_object_or_404(get_dataroom_queryset_for_user(request.user), id=dataroom_id)
        serializer = AddAssetsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        max_items = get_dynamic_setting('MAX_FILES_PER_UPLOAD')
        if max_items and len(data['items']) > max_items:
            return Response({'detail': f'At most {max_items} files can be added at a time.'}, status=status.HTTP_400_BAD_REQUEST)

        folder = None
        if data.get('destination_folder_id'):
            folder = DataroomFolder.objects.filter(id=data['destination_folder_id'], dataroom=room).first()
            if folder is None:
                return Response({'detail': 'Destination folder does not belong to this dataroom.'}, status=status.HTTP_400_BAD_REQUEST)

        # Validate the whole batch first, so a bad item queues nothing.
        for item in data['items']:
            try:
                scanner.stat_file(item['space_id'], item['path'])
            except scanner.AssetNotFound:
                return Response({'detail': f"File not found: {item['path']}"}, status=status.HTTP_400_BAD_REQUEST)

        spaces = scanner.list_spaces()
        snapshots = [
            AssetSnapshot.objects.create(
                organization=room.organization,
                dataroom=room,
                destination_folder=folder,
                source_space_id=item['space_id'],
                source_space_name=_space_name(item['space_id'], spaces),
                source_path=item['path'],
                source_file_id=scanner.file_id(item['space_id'], item['path']),
                added_by=request.user,
            )
            for item in data['items']
        ]
        for snapshot in snapshots:
            snapshot_asset_task.delay(snapshot.id)
        for snapshot in snapshots:
            snapshot.refresh_from_db()  # picks up eager results under pytest
        return Response({'snapshots': AssetSnapshotSerializer(snapshots, many=True).data}, status=status.HTTP_202_ACCEPTED)


@extend_schema(tags=['assets'])
class DataroomAssetSnapshotsView(AssetsBaseView):
    def get(self, request, dataroom_id):
        room = get_object_or_404(get_dataroom_queryset_for_user(request.user), id=dataroom_id)
        qs = AssetSnapshot.objects.filter(dataroom=room).select_related('added_by')
        ids = [i for i in request.query_params.get('ids', '').split(',') if i]
        if ids:
            qs = qs.filter(id__in=ids)
        return Response(AssetSnapshotSerializer(qs[:200], many=True).data)
