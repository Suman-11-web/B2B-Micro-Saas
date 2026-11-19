"""
Celery tasks for billing and usage aggregation.
"""
from celery import shared_task
from django.utils import timezone
from django.db.models import Sum, Count
from datetime import timedelta
import structlog

logger = structlog.get_logger()


@shared_task
def aggregate_daily_usage():
    """Aggregate daily usage for all active subscriptions."""
    from apps.billing.models import UsageSummary, Subscription
    from apps.accounts.models import UsageEvent

    yesterday = timezone.now().date() - timedelta(days=1)
    period_start = timezone.make_aware(timezone.datetime.combine(yesterday, timezone.datetime.min.time()))
    period_end = timezone.make_aware(timezone.datetime.combine(yesterday, timezone.datetime.max.time()))

    active_subscriptions = Subscription.objects.filter(
        status__in=[Subscription.Status.ACTIVE, Subscription.Status.TRIALING]
    ).select_related('company', 'plan')

    for sub in active_subscriptions:
        events = UsageEvent.objects.filter(
            company=sub.company,
            created_at__gte=period_start,
            created_at__lte=period_end
        )

        summary, created = UsageSummary.objects.get_or_create(
            subscription=sub,
            period_type=UsageSummary.PeriodType.DAILY,
            period_start=period_start,
            defaults={
                'company': sub.company,
                'period_end': period_end,
            }
        )

        # Aggregate by event type
        for event_type in UsageEvent.EventType.values:
            count = events.filter(event_type=event_type).aggregate(
                total=Sum('quantity')
            )['total'] or 0

            field_map = {
                UsageEvent.EventType.QUERY: 'queries_count',
                UsageEvent.EventType.EMBEDDING: 'embeddings_count',
                UsageEvent.EventType.STORAGE: 'storage_bytes',
                UsageEvent.EventType.ANALYTICS: 'analytics_count',
                UsageEvent.EventType.API_CALL: 'api_calls_count',
            }

            if event_type in field_map:
                setattr(summary, field_map[event_type], count)

        summary.save()

    logger.info("Daily usage aggregation completed", date=yesterday)


@shared_task
def generate_weekly_report():
    """Generate weekly usage reports."""
    from apps.billing.models import UsageSummary, Subscription
    from apps.accounts.models import UsageEvent

    week_ago = timezone.now().date() - timedelta(weeks=1)
    period_start = timezone.make_aware(timezone.datetime.combine(week_ago, timezone.datetime.min.time()))
    period_end = timezone.now()

    active_subscriptions = Subscription.objects.filter(
        status__in=[Subscription.Status.ACTIVE, Subscription.Status.TRIALING]
    ).select_related('company', 'plan')

    for sub in active_subscriptions:
        events = UsageEvent.objects.filter(
            company=sub.company,
            created_at__gte=period_start,
            created_at__lte=period_end
        )

        summary, created = UsageSummary.objects.get_or_create(
            subscription=sub,
            period_type=UsageSummary.PeriodType.MONTHLY,
            period_start=period_start,
            defaults={
                'company': sub.company,
                'period_end': period_end,
            }
        )

        for event_type in UsageEvent.EventType.values:
            count = events.filter(event_type=event_type).aggregate(
                total=Sum('quantity')
            )['total'] or 0

            field_map = {
                UsageEvent.EventType.QUERY: 'queries_count',
                UsageEvent.EventType.EMBEDDING: 'embeddings_count',
                UsageEvent.EventType.STORAGE: 'storage_bytes',
                UsageEvent.EventType.ANALYTICS: 'analytics_count',
                UsageEvent.EventType.API_CALL: 'api_calls_count',
            }

            if event_type in field_map:
                setattr(summary, field_map[event_type], count)

        summary.save()

    logger.info("Weekly usage report generated", week_start=week_ago)


@shared_task
def check_subscription_status():
    """Check subscription status and enforce quotas."""
    from apps.billing.models import QuotaCheck, Subscription
    from apps.accounts.models import UsageEvent
    from apps.documents.models import Document
    from apps.accounts.models import Membership

    active_subscriptions = Subscription.objects.filter(
        status__in=[Subscription.Status.ACTIVE, Subscription.Status.TRIALING]
    ).select_related('company', 'plan')

    for sub in active_subscriptions:
        plan = sub.plan

        # Check queries quota (monthly)
        month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        queries_used = UsageEvent.objects.filter(
            company=sub.company,
            event_type=UsageEvent.EventType.QUERY,
            created_at__gte=month_start
        ).aggregate(total=Sum('quantity'))['total'] or 0

        query_limit = plan.query_limit_monthly
        query_status = QuotaCheck.Status.OK
        if queries_used >= query_limit:
            query_status = QuotaCheck.Status.EXCEEDED
        elif queries_used >= query_limit * 0.8:
            query_status = QuotaCheck.Status.WARNING

        QuotaCheck.objects.create(
            company=sub.company,
            resource=QuotaCheck.Resource.QUERIES,
            current_usage=queries_used,
            limit=query_limit,
            status=query_status,
        )

        # Check storage quota
        storage_used = Document.objects.filter(
            company=sub.company
        ).exclude(status=Document.Status.DELETED).aggregate(
            total=Sum('file_size')
        )['total'] or 0

        storage_limit = plan.storage_limit_bytes
        storage_status = QuotaCheck.Status.OK
        if storage_used >= storage_limit:
            storage_status = QuotaCheck.Status.EXCEEDED
        elif storage_used >= storage_limit * 0.8:
            storage_status = QuotaCheck.Status.WARNING

        QuotaCheck.objects.create(
            company=sub.company,
            resource=QuotaCheck.Resource.STORAGE,
            current_usage=storage_used,
            limit=storage_limit,
            status=storage_status,
        )

        # Check users quota
        user_count = Membership.objects.filter(
            company=sub.company,
            status=Membership.Status.ACTIVE
        ).count()

        user_limit = plan.user_limit
        if user_limit > 0:
            user_status = QuotaCheck.Status.OK
            if user_count >= user_limit:
                user_status = QuotaCheck.Status.EXCEEDED
            elif user_count >= user_limit * 0.8:
                user_status = QuotaCheck.Status.WARNING

            QuotaCheck.objects.create(
                company=sub.company,
                resource=QuotaCheck.Resource.USERS,
                current_usage=user_count,
                limit=user_limit,
                status=user_status,
            )

    logger.info("Subscription quota check completed")


@shared_task
def process_stripe_webhook(event_id, event_type, payload):
    """Process Stripe webhook event."""
    from apps.billing.models import WebhookEvent, Invoice
    from apps.accounts.models import Subscription

    # Idempotency check
    if WebhookEvent.objects.filter(provider='stripe', event_id=event_id).exists():
        return

    webhook = WebhookEvent.objects.create(
        provider='stripe',
        event_id=event_id,
        event_type=event_type,
        payload=payload,
    )

    try:
        if event_type == 'invoice.payment_succeeded':
            handle_stripe_invoice_paid(payload)
        elif event_type == 'customer.subscription.updated':
            handle_stripe_subscription_updated(payload)
        elif event_type == 'customer.subscription.deleted':
            handle_stripe_subscription_cancelled(payload)

        webhook.processed = True
        webhook.processed_at = timezone.now()
        webhook.save()

    except Exception as e:
        webhook.error = str(e)
        webhook.save()
        logger.error("Stripe webhook processing failed", event_id=event_id, error=str(e))
        raise


def handle_stripe_invoice_paid(payload):
    """Handle successful invoice payment."""
    from apps.billing.models import Invoice
    from apps.accounts.models import Subscription

    invoice_data = payload['data']['object']
    stripe_invoice_id = invoice_data['id']
    subscription_id = invoice_data.get('subscription')

    # Find our subscription
    try:
        sub = Subscription.objects.get(provider_subscription_id=subscription_id)
    except Subscription.DoesNotExist:
        return

    # Create invoice record
    Invoice.objects.create(
        company=sub.company,
        subscription=sub,
        provider=Subscription.Provider.STRIPE,
        provider_invoice_id=stripe_invoice_id,
        status=Invoice.Status.PAID,
        amount_usd=invoice_data['amount_paid'] // 100,  # Convert from cents
        amount_inr=int(invoice_data['amount_paid'] // 100 * 83),  # Approximate conversion
        currency='USD',
        period_start=timezone.datetime.fromtimestamp(invoice_data['period_start']),
        period_end=timezone.datetime.fromtimestamp(invoice_data['period_end']),
        paid_at=timezone.now(),
    )


def handle_stripe_subscription_updated(payload):
    """Handle subscription update."""
    from apps.accounts.models import Subscription

    sub_data = payload['data']['object']
    stripe_sub_id = sub_data['id']

    try:
        sub = Subscription.objects.get(provider_subscription_id=stripe_sub_id)
    except Subscription.DoesNotExist:
        return

    status_map = {
        'active': Subscription.Status.ACTIVE,
        'trialing': Subscription.Status.TRIALING,
        'past_due': Subscription.Status.PAST_DUE,
        'canceled': Subscription.Status.CANCELLED,
        'incomplete': Subscription.Status.INCOMPLETE,
    }

    sub.status = status_map.get(sub_data['status'], Subscription.Status.ACTIVE)
    sub.current_period_start = timezone.datetime.fromtimestamp(sub_data['current_period_start'])
    sub.current_period_end = timezone.datetime.fromtimestamp(sub_data['current_period_end'])
    sub.cancel_at_period_end = sub_data.get('cancel_at_period_end', False)
    sub.save()


def handle_stripe_subscription_cancelled(payload):
    """Handle subscription cancellation."""
    from apps.accounts.models import Subscription

    sub_data = payload['data']['object']
    stripe_sub_id = sub_data['id']

    try:
        sub = Subscription.objects.get(provider_subscription_id=stripe_sub_id)
        sub.status = Subscription.Status.CANCELLED
        sub.cancelled_at = timezone.now()
        sub.save()
    except Subscription.DoesNotExist:
        pass


@shared_task
def process_razorpay_webhook(event_id, event_type, payload):
    """Process Razorpay webhook event."""
    from apps.billing.models import WebhookEvent

    if WebhookEvent.objects.filter(provider='razorpay', event_id=event_id).exists():
        return

    webhook = WebhookEvent.objects.create(
        provider='razorpay',
        event_id=event_id,
        event_type=event_type,
        payload=payload,
    )

    try:
        # Similar to Stripe but for Razorpay events
        webhook.processed = True
        webhook.processed_at = timezone.now()
        webhook.save()
    except Exception as e:
        webhook.error = str(e)
        webhook.save()
        raise