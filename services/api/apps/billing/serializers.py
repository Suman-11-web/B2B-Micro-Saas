"""
Serializers for billing app.
"""
from rest_framework import serializers
from apps.billing.models import Invoice, UsageSummary, QuotaCheck, WebhookEvent
from apps.accounts.serializers import SubscriptionPlanSerializer, SubscriptionSerializer


class InvoiceSerializer(serializers.ModelSerializer):
    """Serializer for Invoice."""

    class Meta:
        model = Invoice
        fields = [
            'id', 'subscription', 'provider', 'provider_invoice_id',
            'status', 'amount_inr', 'amount_usd', 'currency',
            'period_start', 'period_end', 'due_date', 'paid_at',
            'pdf_url', 'created_at',
        ]
        read_only_fields = fields


class UsageSummarySerializer(serializers.ModelSerializer):
    """Serializer for UsageSummary."""

    class Meta:
        model = UsageSummary
        fields = [
            'id', 'subscription', 'period_type', 'period_start', 'period_end',
            'queries_count', 'embeddings_count', 'storage_bytes',
            'analytics_count', 'api_calls_count',
            'overage_charges_inr', 'overage_charges_usd',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields


class QuotaCheckSerializer(serializers.ModelSerializer):
    """Serializer for QuotaCheck."""

    class Meta:
        model = QuotaCheck
        fields = [
            'id', 'resource', 'current_usage', 'limit', 'status', 'checked_at',
        ]
        read_only_fields = fields


class QuotaStatusSerializer(serializers.Serializer):
    """Current quota status for all resources."""
    queries = QuotaCheckSerializer()
    storage = QuotaCheckSerializer()
    users = QuotaCheckSerializer()
    embeddings = QuotaCheckSerializer()


class WebhookEventSerializer(serializers.ModelSerializer):
    """Serializer for WebhookEvent."""

    class Meta:
        model = WebhookEvent
        fields = [
            'id', 'provider', 'event_id', 'event_type',
            'processed', 'error', 'created_at', 'processed_at',
        ]
        read_only_fields = fields


class BillingOverviewSerializer(serializers.Serializer):
    """Combined billing overview."""
    subscription = SubscriptionSerializer()
    plan = SubscriptionPlanSerializer()
    invoices = InvoiceSerializer(many=True)
    current_usage = UsageSummarySerializer()
    quota_status = QuotaStatusSerializer()