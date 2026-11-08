from django.urls import path

from . import views

urlpatterns = [
    path('assets/spaces/', views.AssetSpacesView.as_view(), name='asset-spaces'),
    path('assets/browse/', views.AssetBrowseView.as_view(), name='asset-browse'),
    path('assets/search/', views.AssetSearchView.as_view(), name='asset-search'),
    path('assets/preview/', views.AssetPreviewView.as_view(), name='asset-preview'),
    path('datarooms/<str:dataroom_id>/assets/add/', views.DataroomAssetsAddView.as_view(), name='dataroom-assets-add'),
    path('datarooms/<str:dataroom_id>/assets/snapshots/', views.DataroomAssetSnapshotsView.as_view(), name='dataroom-assets-snapshots'),
]
