"""
Analytics models for statistical analysis results.
"""
import uuid
from django.db import models
from apps.accounts.models import TenantModel, Company, User


class AnalyticsJob(TenantModel):
    """Analytics job triggered from queries."""
    class AnalysisType(models.TextChoices):
        DISTRIBUTION = 'distribution', 'Distribution'
        CORRELATION = 'correlation', 'Correlation'
        REGRESSION = 'regression', 'Regression'
        TTEST = 'ttest', 'T-Test'
        TIMESERIES = 'timeseries', 'Time Series'
        ANOVA = 'anova', 'ANOVA'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        RUNNING = 'running', 'Running'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    query = models.ForeignKey('queries.Query', on_delete=models.CASCADE, related_name='analytics_jobs')
    analysis_type = models.CharField(max_length=20, choices=AnalysisType.choices)
    parameters = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    result_data = models.JSONField(default=dict, blank=True)
    chart_spec = models.JSONField(default=dict, blank=True)
    chart_data = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True, null=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'analytics_jobs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'query']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.analysis_type} for query {self.query.id}"


class DataProfile(TenantModel):
    """Statistical profile of a dataset."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey('documents.Document', on_delete=models.CASCADE, related_name='data_profiles')
    column_name = models.CharField(max_length=255)
    data_type = models.CharField(max_length=50)  # numeric, categorical, datetime
    stats = models.JSONField(default=dict, blank=True)  # mean, std, min, max, quartiles, etc.
    sample_values = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'data_profiles'
        unique_together = ['document', 'column_name']
        indexes = [
            models.Index(fields=['company', 'document']),
        ]