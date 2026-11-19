"""
Main URL configuration for B2B Micro-SaaS API.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from rest_framework import permissions
from drf_spectacular.generators import SchemaGenerator

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),

    # Health checks (no auth - for load balancer/health checks)
    path('health/', include('apps.health.urls')),

    # API v1
    path('api/v1/', include('apps.accounts.urls')),
    path('api/v1/', include('apps.documents.urls')),
    path('api/v1/', include('apps.queries.urls')),
    path('api/v1/', include('apps.analytics.urls')),
    path('api/v1/', include('apps.billing.urls')),
    # path('api/v1/', include('apps.dataconnect.urls')),  # Add when ready
    path('api/v1/', include('apps.audit.urls')),  # Add if exists

    # OpenAPI Schema
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/schema/swagger/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # Prometheus metrics
    path('metrics/', include('django_prometheus.urls')),
]

# Static/media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)