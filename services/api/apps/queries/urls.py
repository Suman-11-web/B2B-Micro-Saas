from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.queries.views import QueryViewSet, QueryResultViewSet

router = DefaultRouter()
router.register(r'queries', QueryViewSet, basename='query')
router.register(r'query-results', QueryResultViewSet, basename='queryresult')

urlpatterns = [
    path('', include(router.urls)),
]