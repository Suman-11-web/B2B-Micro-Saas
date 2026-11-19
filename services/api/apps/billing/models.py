"""
Billing models for subscriptions, invoices, and usage tracking.
"""
import uuid
from django.db import models
from apps.accounts.models import TenantModel, Company, User, SubscriptionPlan, Subscription


class Invoice(TenantModel):
    """Invoice for subscription billing."""
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        OPEN = 'open', 'Open'
        PAID = 'paid', 'Paid'
        VOID = 'void', 'Void'
        UNCOLLECTIBLE = 'uncollectible', 'Uncollectible'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='invoices')
    provider = models.CharField(max_length=20, choices=Subscription.Provider.choices)
    provider_invoice_id = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    amount_inr = models.PositiveIntegerField(default=0)
    amount_usd = models.PositiveIntegerField(default=0)
    currency = models.CharField(max_length=3, default='INR')
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    due_date = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    pdf_url = models.URLField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'invoices'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'status']),
            models.Index(fields=['provider', 'provider_invoice_id']),
        ]

    def __str__(self):
        return f"Invoice {self.id} - {self.amount_inr} INR ({self.status})"


class UsageSummary(TenantModel):
    """Aggregated usage for billing period."""
    class PeriodType(models.TextChoices):
        DAILY = 'daily', 'Daily'
        MONTHLY = 'monthly', 'Monthly'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='usage_summaries')
    period_type = models.CharField(max_length=10, choices=PeriodType.choices)
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    queries_count = models.PositiveIntegerField(default=0)
    embeddings_count = models.PositiveIntegerField(default=0)
    storage_bytes = models.BigIntegerField(default=0)
    analytics_count = models.PositiveIntegerField(default=0)
    api_calls_count = models.PositiveIntegerField(default=0)
    overage_charges_inr = models.PositiveIntegerField(default=0)
    overage_charges_usd = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'usage_summaries'
        unique_together = ['subscription', 'period_type', 'period_start']
        ordering = ['-period_start']
        indexes = [
            models.Index(fields=['company', 'period_type', 'period_start']),
        ]


class QuotaCheck(TenantModel):
    """Quota check results for enforcement."""
    class Resource(models.TextChoices):
        QUERIES = 'queries', 'Queries'
        STORAGE = 'storage', 'Storage'
        USERS = 'users', 'Users'
        EMBEDDINGS = 'embeddings', 'Embeddings'

    class Status(models.TextChoices):
        OK = 'ok', 'OK'
        WARNING = 'warning', 'Warning (80%+)'
        EXCEEDED = 'exceeded', 'Exceeded'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    resource = models.CharField(max_length=20, choices=Resource.choices)
    current_usage = models.BigIntegerField(default=0)
    limit = models.BigIntegerField(default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OK)
    checked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'quota_checks'
        ordering = ['-checked_at']
        indexes = [
            models.Index(fields=['company', 'resource', 'checked_at']),
        ]


class WebhookEvent(models.Model):
    """Track processed webhook events for idempotency."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.CharField(max_length=20, choices=Subscription.Provider.choices)
    event_id = models.CharField(max_length=255, unique=True)
    event_type = models.CharField(max_length=100)
    processed = models.BooleanField(default=False)
    payload = models.JSONField(default=dict)
    error = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'webhook_events'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['provider', 'event_type']),
            models.Index(fields=['processed', 'created_at']),
        ]

    def __str__(self):
        return f"{self.provider} - {self.event_type} ({'processed' if self.processed else 'pending'})"