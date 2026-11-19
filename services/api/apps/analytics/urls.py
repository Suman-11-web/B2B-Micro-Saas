from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.analytics.views import AnalyticsJobViewSet, DataProfileViewSet

router = DefaultRouter()
router.register(r'analytics-jobs', AnalyticsJobViewSet, basename='analyticsjob')
router.register(r'data-profiles', DataProfileViewSet, basename='dataprofile')

urlpatterns = [
    path('', include(router.urls)),
]