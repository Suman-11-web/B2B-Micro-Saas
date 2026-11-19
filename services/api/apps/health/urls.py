from django.urls import path
from apps.health.views import HealthView, ReadyView, LiveView

urlpatterns = [
    path('', HealthView.as_view(), name='health'),
    path('ready/', ReadyView.as_view(), name='ready'),
    path('live/', LiveView.as_view(), name='live'),
]