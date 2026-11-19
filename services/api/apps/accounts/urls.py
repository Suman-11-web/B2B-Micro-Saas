from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.accounts.views import (
    AuthViewSet, CompanyViewSet, MembershipViewSet,
    SubscriptionPlanViewSet, SubscriptionViewSet,
    ApiKeyViewSet, AuditLogViewSet, UsageEventViewSet
)

router = DefaultRouter()
router.register(r'auth', AuthViewSet, basename='auth')
router.register(r'companies', CompanyViewSet, basename='company')
router.register(r'memberships', MembershipViewSet, basename='membership')
router.register(r'plans', SubscriptionPlanViewSet, basename='plan')
router.register(r'subscription', SubscriptionViewSet, basename='subscription')
router.register(r'api-keys', ApiKeyViewSet, basename='apikey')
router.register(r'audit-logs', AuditLogViewSet, basename='auditlog')
router.register(r'usage-events', UsageEventViewSet, basename='usageevent')

urlpatterns = [
    path('', include(router.urls)),
]