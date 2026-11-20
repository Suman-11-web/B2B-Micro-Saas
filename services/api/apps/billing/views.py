"""
Views for billing app - invoices, usage, quotas, webhooks, and UPI plan upgrades.
"""
from datetime import timedelta
from django.db.models import Sum
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.billing.models import Invoice, UsageSummary, QuotaCheck, WebhookEvent
from apps.billing.serializers import (
    InvoiceSerializer, UsageSummarySerializer, QuotaCheckSerializer,
    WebhookEventSerializer,
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
        """Get live quota status for all resources."""
        from apps.accounts.models import UsageEvent, Membership
        from apps.documents.models import Document

        company = request.company
        sub = company.active_subscription or company.subscriptions.order_by('-created_at').first()
        plan = sub.plan if sub else None

        month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        queries_used = UsageEvent.objects.filter(
            company=company,
            event_type=UsageEvent.EventType.QUERY,
            created_at__gte=month_start,
        ).aggregate(total=Sum('quantity'))['total'] or 0

        storage_used = Document.objects.filter(company=company).exclude(
            status=Document.Status.DELETED
        ).aggregate(total=Sum('file_size'))['total'] or 0

        users_count = Membership.objects.filter(
            company=company,
            status__in=[Membership.Status.ACTIVE, Membership.Status.INVITED],
        ).count()

        def _status(used, limit):
            if limit <= 0:
                return 'ok'
            if used >= limit:
                return 'exceeded'
            if used >= limit * 0.8:
                return 'warning'
            return 'ok'

        q_limit = plan.query_limit_monthly if plan else 50
        s_limit = plan.storage_limit_bytes if plan else 1024 * 1024 * 1024
        u_limit = plan.user_limit if plan else 2

        return Response({
            'queries': {'resource': 'queries', 'current_usage': queries_used, 'limit': q_limit, 'status': _status(queries_used, q_limit)},
            'storage': {'resource': 'storage', 'current_usage': storage_used, 'limit': s_limit, 'status': _status(storage_used, s_limit)},
            'users': {'resource': 'users', 'current_usage': users_count, 'limit': u_limit, 'status': _status(users_count, u_limit)},
        })


class WebhookEventViewSet(viewsets.ReadOnlyModelViewSet):
    """Webhook event viewing (for debugging)."""
    queryset = WebhookEvent.objects.all()
    serializer_class = WebhookEventSerializer
    permission_classes = [BelongsToTenant, IsOwnerOrAdmin]
    filterset_fields = ['provider', 'processed', 'event_type']
    ordering = ['-created_at']


class BillingViewSet(viewsets.GenericViewSet):
    """Billing overview and UPI plan upgrade endpoints."""
    permission_classes = [BelongsToTenant, IsOwnerOrAdmin]

    @action(detail=False, methods=['get'])
    def overview(self, request):
        """Get complete billing overview with live usage and invoices."""
        from apps.accounts.models import SubscriptionPlan, UsageEvent, Membership
        from apps.documents.models import Document

        company = request.company
        subscription = company.active_subscription or company.subscriptions.order_by('-created_at').first()

        sub_data = SubscriptionSerializer(subscription).data if subscription else None
        plan_data = SubscriptionPlanSerializer(subscription.plan).data if subscription and subscription.plan else None

        invoices = Invoice.objects.filter(company=company).order_by('-created_at')[:15]
        invoices_data = InvoiceSerializer(invoices, many=True).data

        month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        queries_used = UsageEvent.objects.filter(
            company=company,
            event_type=UsageEvent.EventType.QUERY,
            created_at__gte=month_start,
        ).aggregate(total=Sum('quantity'))['total'] or 0

        storage_used = Document.objects.filter(company=company).exclude(
            status=Document.Status.DELETED
        ).aggregate(total=Sum('file_size'))['total'] or 0

        users_count = Membership.objects.filter(
            company=company,
            status__in=[Membership.Status.ACTIVE, Membership.Status.INVITED],
        ).count()

        plan = subscription.plan if subscription else None
        plans = SubscriptionPlan.objects.filter(is_active=True).order_by('sort_order')

        return Response({
            'subscription': sub_data,
            'plan': plan_data,
            'available_plans': SubscriptionPlanSerializer(plans, many=True).data,
            'invoices': invoices_data,
            'live_usage': {
                'queries_used': queries_used,
                'query_limit': plan.query_limit_monthly if plan else 50,
                'storage_used_bytes': storage_used,
                'storage_limit_bytes': plan.storage_limit_bytes if plan else 1024 * 1024 * 1024,
                'users_count': users_count,
                'user_limit': plan.user_limit if plan else 2,
            },
        })

    @action(detail=False, methods=['post'], url_path='upi-upgrade')
    def upi_upgrade(self, request):
        """Record a UPI payment (UTR / Reference ID) and upgrade the company's subscription."""
        from apps.accounts.models import Subscription, SubscriptionPlan

        plan_key = (request.data.get('plan_key') or '').strip().lower()
        utr_number = (request.data.get('utr_number') or '').strip()
        payer_upi_id = (request.data.get('payer_upi_id') or '').strip()

        if not plan_key:
            return Response(
                {'error': 'missing_plan', 'message': 'Please select a subscription plan.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            plan = SubscriptionPlan.objects.get(key=plan_key, is_active=True)
        except SubscriptionPlan.DoesNotExist:
            return Response(
                {'error': 'invalid_plan', 'message': 'Selected plan does not exist.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if plan.price_monthly_inr > 0 and len(utr_number) < 6:
            return Response(
                {'error': 'invalid_utr', 'message': 'Please enter a valid UPI Transaction ID / UTR number (at least 6 characters).'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if plan.price_monthly_inr > 0 and Invoice.objects.filter(provider_invoice_id=utr_number).exists():
            return Response(
                {'error': 'duplicate_utr', 'message': 'This UPI Transaction ID / UTR has already been used.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        company = request.company
        now = timezone.now()
        period_end = now + timedelta(days=30 if plan.price_monthly_inr > 0 else 3650)

        # Cancel any older active subscriptions before activating the new one
        company.subscriptions.filter(status__in=[Subscription.Status.ACTIVE, Subscription.Status.TRIALING]).update(
            status=Subscription.Status.CANCELLED,
            cancelled_at=now,
        )

        subscription = Subscription.objects.create(
            company=company,
            plan=plan,
            status=Subscription.Status.ACTIVE,
            provider=Subscription.Provider.MANUAL,
            provider_subscription_id=utr_number or f'free_{company.slug}',
            current_period_start=now,
            current_period_end=period_end,
            metadata={'payment_method': 'upi', 'utr_number': utr_number, 'payer_upi_id': payer_upi_id},
        )

        if company.status != 'active':
            company.status = 'active'
            company.save(update_fields=['status'])

        invoice = Invoice.objects.create(
            company=company,
            subscription=subscription,
            provider=Subscription.Provider.MANUAL,
            provider_invoice_id=utr_number or f'INV-{now.strftime("%Y%m%d%H%M%S")}',
            status=Invoice.Status.PAID,
            amount_inr=plan.price_monthly_inr,
            amount_usd=plan.price_monthly_usd,
            currency='INR',
            period_start=now,
            period_end=period_end,
            paid_at=now,
            metadata={'payment_method': 'upi', 'utr_number': utr_number, 'payer_upi_id': payer_upi_id},
        )

        return Response({
            'message': f'Upgraded to {plan.name} plan successfully!',
            'subscription': SubscriptionSerializer(subscription).data,
            'plan': SubscriptionPlanSerializer(plan).data,
            'invoice': InvoiceSerializer(invoice).data,
        }, status=status.HTTP_201_CREATED)
