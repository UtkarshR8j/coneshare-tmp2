from django.urls import include, path
from rest_framework.routers import DefaultRouter

from core import views
from core.oidc_views import OIDCCallbackView, OIDCLoginView

router = DefaultRouter()
router.register(r'organizations', views.OrganizationViewSet)
router.register(r'users', views.UserViewSet)
router.register(r'groups', views.UserGroupViewSet)
router.register(r'api-keys', views.APIKeyViewSet, basename='api-key')

urlpatterns = [
    path('_health/', views.HealthCheckView.as_view(), name='health-check'),
    path('oidc/login/', OIDCLoginView.as_view(), name='oidc_login'),
    path('oidc/callback/', OIDCCallbackView.as_view(), name='oidc_callback'),
    path('', include(router.urls)),
]
