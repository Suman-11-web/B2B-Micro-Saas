"""
Signals for accounts app - auto-create audit logs, subscriptions, etc.
"""
from django.db.models.signals import post_save, pre_delete, m2m_changed
from django.dispatch import receiver
from django.utils import timezone
from django.contrib.auth import get_user_model
from apps.accounts.models import (
    Company, User, Membership, Subscription, SubscriptionPlan,
    ApiKey, AuditLog, UsageEvent
)

import structlog

logger = structlog.get_logger()

User = get_user_model()


@receiver(post_save, sender=Company)
def company_created(sender, instance, created, **kwargs):
    if created:
        AuditLog.objects.create(
            company=instance,
            action=AuditLog.Action.CREATE,
            resource_type='company',
            resource_id=str(instance.id),
            metadata={'name': instance.name, 'slug': instance.slug}
        )

        # Create default free subscription
        try:
            free_plan = SubscriptionPlan.objects.get(key='free')
            now = timezone.now()

            # 10-year default period for free tier
            Subscription.objects.create(
                company=instance,
                plan=free_plan,
                status=Subscription.Status.TRIALING,
                provider=Subscription.Provider.MANUAL,
                current_period_start=now,
                current_period_end=now + timezone.timedelta(days=3650),
            )

            logger.info("Company created with free subscription", company_id=instance.id)
        except SubscriptionPlan.DoesNotExist:
            logger.warning("Free subscription plan not found", company_id=instance.id)


@receiver(post_save, sender=User)
def user_created(sender, instance, created, **kwargs):
    if created:
        # User creation is global, not tenant-scoped
        pass


@receiver(post_save, sender=Membership)
def membership_changed(sender, instance, created, **kwargs):
    if created:
        AuditLog.objects.create(
            company=instance.company,
            user=instance.invited_by,
            action=AuditLog.Action.INVITE,
            resource_type='membership',
            resource_id=str(instance.id),
            metadata={
                'user_email': instance.user.email,
                'role': instance.role,
            }
        )
    elif instance.status == Membership.Status.ACTIVE and instance.joined_at:
        # Member accepted invitation
        AuditLog.objects.create(
            company=instance.company,
            user=instance.user,
            action=AuditLog.Action.CREATE,
            resource_type='membership',
            resource_id=str(instance.id),
            metadata={'role': instance.role}
        )


@receiver(pre_delete, sender=Membership)
def membership_removed(sender, instance, **kwargs):
    AuditLog.objects.create(
        company=instance.company,
        action=AuditLog.Action.REVOKE,
        resource_type='membership',
        resource_id=str(instance.id),
        metadata={
            'user_email': instance.user.email,
            'role': instance.role,
        }
    )


@receiver(post_save, sender=Subscription)
def subscription_changed(sender, instance, created, **kwargs):
    action = AuditLog.Action.CREATE if created else AuditLog.Action.UPDATE
    if instance.status == Subscription.Status.CANCELLED:
        action = AuditLog.Action.DOWNGRADE
    elif instance.status == Subscription.Status.ACTIVE and not created:
        action = AuditLog.Action.UPGRADE

    AuditLog.objects.create(
        company=instance.company,
        action=action,
        resource_type='subscription',
        resource_id=str(instance.id),
        metadata={
            'plan': instance.plan.key,
            'status': instance.status,
            'provider': instance.provider,
        }
    )


@receiver(post_save, sender=ApiKey)
def api_key_created(sender, instance, created, **kwargs):
    if created:
        AuditLog.objects.create(
            company=instance.company,
            user=instance.created_by,
            action=AuditLog.Action.CREATE,
            resource_type='api_key',
            resource_id=str(instance.id),
            metadata={
                'name': instance.name,
                'scopes': instance.scopes,
            }
        )