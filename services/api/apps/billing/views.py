"""
Views for billing app.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.billing.models import Invoice, UsageSummary, QuotaCheck, WebhookEvent
from apps.billing.serializers import (
    InvoiceSerializer, UsageSummarySerializer, QuotaCheckSerializer,
    WebhookEventSerializer, BillingOverviewSerializer, QuotaStatusSerializer
)
from apps.accounts.serializers import SubscriptionSerializer, SubscriptionPlanSerializer
from apps.accounts.permissions import BelongsToTenant, IsOwnerOrAdmin, HasPermission


class InvoiceViewSet(viewsets.ReadOnlyModelViewSet):
    """Invoice viewing."""
    queryset = Invoice.objects.all()
    serializer_class = InvoiceSerializer
    permission_classes = [BelongsToTenant, IsOwnerOrAdmin]
    ordering = ['-created_at']

    def get_queryset(self):
        return Invoice.objects.filter(company=self.request.company).select_related('subscription__plan')


class UsageSummaryViewSet(viewsets.ReadOnlyModelViewSet):
    """Usage summary viewing."""
    queryset = UsageSummary.objects.all()
    serializer_class = UsageSummarySerializer
    permission_classes = [BelongsToTenant, HasPermission('view_analytics')]
    filterset_fields = ['period_type', 'period_start']
    ordering = ['-period_start']

    def get_queryset(self):
        return UsageSummary.objects.filter(company=self.request.company).select_related('subscription__plan')


class QuotaCheckViewSet(viewsets.ReadOnlyModelViewSet):
    """Quota check viewing."""
    queryset = QuotaCheck.objects.all()
    serializer_class = QuotaCheckSerializer
    permission_classes = [BelongsToTenant, HasPermission('view_analytics')]
    filterset_fields = ['resource', 'status']
    ordering = ['-checked_at']

    def get_queryset(self):
        return QuotaCheck.objects.filter(company=self.request.company)

    @action(detail=False, methods=['get'])
    def current(self, request):
        """Get current quota status for all resources."""
        quotas = {}
        resources = ['queries', 'storage', 'users', 'embeddings']

        for resource in resources:
            quota = QuotaCheck.objects.filter(
                company=request.company,
                resource=resource
            ).last()

            if quota:
                quotas[resource] = QuotaCheckSerializer(quota).data
            else:
                quotas[resource] = {
                    'resource': resource,
                    'current_usage': 0,
                    'limit': 0,
                    'status': 'ok',
                }

        return Response(quotas)


class WebhookEventViewSet(viewsets.ReadOnlyModelViewSet):
    """Webhook event viewing (for debugging)."""
    queryset = WebhookEvent.objects.all()
    serializer_class = WebhookEventSerializer
    permission_classes = [BelongsToTenant, IsOwnerOrAdmin]
    filterset_fields = ['provider', 'processed', 'event_type']
    ordering = ['-created_at']


class BillingViewSet(viewsets.GenericViewSet):
    """Billing overview endpoint."""
    permission_classes = [BelongsToTenant, IsOwnerOrAdmin]

    @action(detail=False, methods=['get'])
    def overview(self, request):
        """Get complete billing overview."""
        from apps.accounts.models import Subscription

        company = request.company
        subscription = company.active_subscription

        # Get subscription
        if subscription:
            sub_data = SubscriptionSerializer(subscription).data
            plan_data = subscription.plan
        else:
            sub_data = None
            plan_data = None

        # Get recent invoices
        invoices = Invoice.objects.filter(company=company).order_by('-created_at')[:10]
        invoices_data = InvoiceSerializer(invoices, many=True).data

        # Get current usage
        from apps.billing.models import UsageSummary
        usage = UsageSummary.objects.filter(
            subscription=subscription
        ).order_by('-period_start').first() if subscription else None

        # Get quota checks
        quotas = {}
        for resource in ['queries', 'storage', 'users']:
            quota = QuotaCheck.objects.filter(
                company=company,
                resource=resource
            ).last()
            if quota:
                quotas[resource] = QuotaCheckSerializer(quota).data

        return Response({
            'subscription': sub_data,
            'plan': SubscriptionPlanSerializer(plan_data).data if plan_data else None,
            'invoices': invoices_data,
            'current_usage': UsageSummarySerializer(usage).data if usage else None,
            'quota_status': quotas,
        })