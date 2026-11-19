"""
Django admin configuration for billing app.
"""
from django.contrib import admin
from apps.billing.models import Invoice, UsageSummary, QuotaCheck, WebhookEvent


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['company', 'subscription', 'provider', 'status', 'amount_inr', 'amount_usd', 'currency', 'paid_at']
    list_filter = ['status', 'provider', 'currency', 'paid_at']
    search_fields = ['company__name', 'provider_invoice_id']
    ordering = ['-created_at']

    readonly_fields = [f.name for f in Invoice._meta.fields]


@admin.register(UsageSummary)
class UsageSummaryAdmin(admin.ModelAdmin):
    list_display = ['company', 'period_type', 'period_start', 'period_end', 'queries_count', 'storage_bytes']
    list_filter = ['period_type', 'period_start']
    search_fields = ['company__name']
    ordering = ['-period_start']

    readonly_fields = [f.name for f in UsageSummary._meta.fields]


@admin.register(QuotaCheck)
class QuotaCheckAdmin(admin.ModelAdmin):
    list_display = ['company', 'resource', 'current_usage', 'limit', 'status', 'checked_at']
    list_filter = ['resource', 'status', 'checked_at']
    search_fields = ['company__name']
    ordering = ['-checked_at']

    readonly_fields = [f.name for f in QuotaCheck._meta.fields]


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ['provider', 'event_id', 'event_type', 'processed', 'created_at']
    list_filter = ['provider', 'processed', 'event_type', 'created_at']
    search_fields = ['event_id', 'event_type']
    ordering = ['-created_at']

    readonly_fields = [f.name for f in WebhookEvent._meta.fields]