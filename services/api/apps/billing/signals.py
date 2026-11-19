"""
Signals for billing app.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.billing.models import Invoice, UsageSummary, QuotaCheck


@receiver(post_save, sender=Invoice)
def invoice_created(sender, instance, created, **kwargs):
    pass


@receiver(post_save, sender=UsageSummary)
def usage_summary_changed(sender, instance, created, **kwargs):
    pass


@receiver(post_save, sender=QuotaCheck)
def quota_check_changed(sender, instance, created, **kwargs):
    pass