"""
Serializers for analytics app.
"""
from rest_framework import serializers
from apps.analytics.models import AnalyticsJob, DataProfile


class AnalyticsJobSerializer(serializers.ModelSerializer):
    """Serializer for AnalyticsJob."""

    class Meta:
        model = AnalyticsJob
        fields = [
            'id', 'analysis_type', 'parameters', 'status',
            'result_data', 'chart_spec', 'chart_data',
            'error_message', 'started_at', 'completed_at', 'created_at',
        ]
        read_only_fields = fields


class DataProfileSerializer(serializers.ModelSerializer):
    """Serializer for DataProfile."""

    class Meta:
        model = DataProfile
        fields = [
            'id', 'document', 'column_name', 'data_type',
            'stats', 'sample_values', 'created_at',
        ]
        read_only_fields = fields