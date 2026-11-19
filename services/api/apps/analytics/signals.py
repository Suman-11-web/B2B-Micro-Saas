"""
Signals for analytics app.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.analytics.models import AnalyticsJob


@receiver(post_save, sender=AnalyticsJob)
def analytics_job_changed(sender, instance, created, **kwargs):
    """Log analytics job creation and completion."""
    pass