"""
Django admin configuration for analytics app.
"""
from django.contrib import admin
from apps.analytics.models import AnalyticsJob, DataProfile


@admin.register(AnalyticsJob)
class AnalyticsJobAdmin(admin.ModelAdmin):
    list_display = ['query', 'analysis_type', 'status', 'started_at', 'completed_at', 'created_at']
    list_filter = ['analysis_type', 'status', 'started_at']
    search_fields = ['query__question']
    ordering = ['-created_at']

    readonly_fields = [f.name for f in AnalyticsJob._meta.fields]


@admin.register(DataProfile)
class DataProfileAdmin(admin.ModelAdmin):
    list_display = ['document', 'column_name', 'data_type', 'created_at']
    list_filter = ['data_type', 'created_at']
    search_fields = ['document__filename', 'column_name']
    ordering = ['-created_at']

    readonly_fields = [f.name for f in DataProfile._meta.fields]