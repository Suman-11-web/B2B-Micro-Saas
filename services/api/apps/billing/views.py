"""
Views for billing app - invoices, usage, quotas, HMAC-verified webhooks, and UPI plan upgrades.
"""
from datetime import timedelta
import hashlib
import hmac
import json
import time

from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Company, Subscription, SubscriptionPlan
from apps.accounts.permissions import BelongsToTenant, HasPermission, IsOwnerOrAdmin
from apps.accounts.serializers import SubscriptionPlanSerializer, SubscriptionSerializer
from apps.billing.models import Invoice, QuotaCheck, UsageSummary, WebhookEvent
from apps.billing.serializers import (
    InvoiceSerializer,
    QuotaCheckSerializer,
    UsageSummarySerializer,
    WebhookEventSerializer,
)


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
        from apps.accounts.models import Membership, UsageEvent
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
    """Platform-admin-only webhook audit viewing (prevents cross-tenant webhook payload leaks)."""
    queryset = WebhookEvent.objects.all()
    serializer_class = WebhookEventSerializer
    permission_classes = [permissions.IsAdminUser]
    filterset_fields = ['provider', 'processed', 'event_type']
    ordering = ['-created_at']


class StripeWebhookView(APIView):
    """Stripe webhook receiver with HMAC-SHA256 signature verification and 5-minute replay protection."""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', '') or ''
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')
        if not secret or not sig_header:
            return Response({'error': 'invalid_signature', 'message': 'Missing Stripe webhook signature.'}, status=400)

        parts = {}
        for item in sig_header.split(','):
            if '=' in item:
                k, v = item.split('=', 1)
                parts[k.strip()] = v.strip()

        timestamp = parts.get('t')
        sig_v1 = parts.get('v1')
        if not timestamp or not sig_v1:
            return Response({'error': 'invalid_signature', 'message': 'Malformed Stripe-Signature header.'}, status=400)

        try:
            if abs(time.time() - int(timestamp)) > 300:
                return Response({'error': 'replay_detected', 'message': 'Webhook timestamp outside tolerance window.'}, status=400)
        except ValueError:
            return Response({'error': 'invalid_signature', 'message': 'Invalid timestamp.'}, status=400)

        signed_payload = f"{timestamp}.".encode('utf-8') + request.body
        expected = hmac.new(secret.encode('utf-8'), signed_payload, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig_v1):
            return Response({'error': 'invalid_signature', 'message': 'Stripe signature verification failed.'}, status=400)

        try:
            payload = json.loads(request.body.decode('utf-8'))
        except Exception:
            return Response({'error': 'invalid_payload', 'message': 'Invalid JSON payload.'}, status=400)

        event_id = payload.get('id', '')
        event_type = payload.get('type', '')
        if not event_id:
            return Response({'error': 'invalid_payload', 'message': 'Missing event id.'}, status=400)

        if WebhookEvent.objects.filter(provider='stripe', event_id=event_id).exists():
            return Response({'status': 'duplicate_ignored'}, status=200)

        from apps.billing.tasks import process_stripe_webhook
        if settings.DEBUG:
            process_stripe_webhook(event_id, event_type, payload)
        else:
            process_stripe_webhook.delay(event_id, event_type, payload)
        return Response({'status': 'accepted'}, status=200)


class RazorpayWebhookView(APIView):
    """Razorpay webhook receiver with constant-time HMAC-SHA256 verification and idempotency."""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        secret = getattr(settings, 'RAZORPAY_WEBHOOK_SECRET', '') or ''
        signature = request.META.get('HTTP_X_RAZORPAY_SIGNATURE', '')
        if not secret or not signature:
            return Response({'error': 'invalid_signature', 'message': 'Missing Razorpay webhook signature.'}, status=400)

        expected = hmac.new(secret.encode('utf-8'), request.body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            return Response({'error': 'invalid_signature', 'message': 'Razorpay signature verification failed.'}, status=400)

        try:
            payload = json.loads(request.body.decode('utf-8'))
        except Exception:
            return Response({'error': 'invalid_payload', 'message': 'Invalid JSON payload.'}, status=400)

        event_id = request.META.get('HTTP_X_RAZORPAY_EVENT_ID') or payload.get('event_id') or hashlib.sha256(request.body).hexdigest()
        event_type = payload.get('event', '')

        if WebhookEvent.objects.filter(provider='razorpay', event_id=event_id).exists():
            return Response({'status': 'duplicate_ignored'}, status=200)

        from apps.billing.tasks import process_razorpay_webhook
        if settings.DEBUG:
            process_razorpay_webhook(event_id, event_type, payload)
        else:
            process_razorpay_webhook.delay(event_id, event_type, payload)
        return Response({'status': 'accepted'}, status=200)


class BillingViewSet(viewsets.GenericViewSet):
    """Billing overview and UPI plan upgrade endpoints."""
    permission_classes = [BelongsToTenant, IsOwnerOrAdmin]

    @action(detail=False, methods=['get'])
    def overview(self, request):
        """Get complete billing overview with live usage and invoices."""
        from apps.accounts.models import Membership, UsageEvent
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
        """Record a UPI payment (UTR / Reference ID) atomically with replay protection."""
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

        with transaction.atomic():
            company = Company.objects.select_for_update().get(id=request.company.id)
            if plan.price_monthly_inr > 0 and Invoice.objects.filter(provider_invoice_id=utr_number).exists():
                return Response(
                    {'error': 'duplicate_utr', 'message': 'This UPI Transaction ID / UTR has already been used.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            now = timezone.now()
            period_end = now + timedelta(days=30 if plan.price_monthly_inr > 0 else 3650)

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
