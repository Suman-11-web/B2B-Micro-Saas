"""
Signals for queries app.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.queries.models import Query, QueryResult


@receiver(post_save, sender=Query)
def query_created(sender, instance, created, **kwargs):
    pass


@receiver(post_save, sender=QueryResult)
def query_result_created(sender, instance, created, **kwargs):
    pass