from django.conf import settings
from django.http import JsonResponse
from django.urls import Resolver404, resolve

LOCKED_URL_NAMES = frozenset({
    'document-upload-request',
    'document-upload-finalize',
    'document-version-upload-request',
    'document-version-upload-finalize',
    'dataroom-upload-request',
    'dataroom-upload-finalize',
    'cloud-import',
    'cloud-document-refresh',
    'cloud-document-import-version',
    'public-file-request-upload-request',
    'public-file-request-finalize-upload',
})


class DocumentUploadLockMiddleware:
    """Rejects every route that brings outside document bytes into coneshare."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.DOCUMENT_UPLOADS_DISABLED and self._is_locked(request.path_info):
            url = settings.ASSETS_PORTAL_URL
            return JsonResponse(
                {
                    'detail': f'Document uploads are disabled here. Upload on {url}, then add the file from the Assets browser.',
                    'code': 'document_uploads_disabled',
                    'assets_url': url,
                },
                status=403,
            )
        return self.get_response(request)

    @staticmethod
    def _is_locked(path):
        try:
            return resolve(path).url_name in LOCKED_URL_NAMES
        except Resolver404:
            return False
