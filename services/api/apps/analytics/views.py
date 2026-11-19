"""
Views for analytics app.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.analytics.models import AnalyticsJob, DataProfile
from apps.analytics.serializers import AnalyticsJobSerializer, DataProfileSerializer
from apps.accounts.permissions import BelongsToTenant, HasPermission


class AnalyticsJobViewSet(viewsets.ReadOnlyModelViewSet):
    """Analytics job viewing."""
    queryset = AnalyticsJob.objects.all()
    serializer_class = AnalyticsJobSerializer
    permission_classes = [BelongsToTenant, HasPermission('view_analytics')]
    filterset_fields = ['analysis_type', 'status']
    ordering = ['-created_at']

    def get_queryset(self):
        return AnalyticsJob.objects.filter(company=self.request.company).select_related('query')


class DataProfileViewSet(viewsets.ReadOnlyModelViewSet):
    """Data profile viewing."""
    queryset = DataProfile.objects.all()
    serializer_class = DataProfileSerializer
    permission_classes = [BelongsToTenant, HasPermission('view_analytics')]
    filterset_fields = ['document', 'data_type']

    def get_queryset(self):
        return DataProfile.objects.filter(company=self.request.company).select_related('document')