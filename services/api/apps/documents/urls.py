from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.documents.views import DocumentViewSet, ChunkViewSet

router = DefaultRouter()
router.register(r'documents', DocumentViewSet, basename='document')
router.register(r'chunks', ChunkViewSet, basename='chunk')

urlpatterns = [
    path('', include(router.urls)),
]