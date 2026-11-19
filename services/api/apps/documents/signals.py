"""
Signals for documents app.
"""
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from apps.documents.models import Document


@receiver(post_save, sender=Document)
def document_changed(sender, instance, created, **kwargs):
    """Log document creation and status changes."""
    pass