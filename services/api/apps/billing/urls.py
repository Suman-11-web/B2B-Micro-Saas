from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.billing.views import (
    InvoiceViewSet, UsageSummaryViewSet, QuotaCheckViewSet,
    WebhookEventViewSet, BillingViewSet
)

router = DefaultRouter()
router.register(r'invoices', InvoiceViewSet, basename='invoice')
router.register(r'usage-summaries', UsageSummaryViewSet, basename='usagesummary')
router.register(r'quota-checks', QuotaCheckViewSet, basename='quotacheck')
router.register(r'webhook-events', WebhookEventViewSet, basename='webhookevent')
router.register(r'billing', BillingViewSet, basename='billing')

urlpatterns = [
    path('', include(router.urls)),
]