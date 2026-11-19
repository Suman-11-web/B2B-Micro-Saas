"""
Health check endpoints for monitoring and load balancers.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import connection
from django.core.cache import cache
import redis


class HealthView(APIView):
    """Basic health check - returns 200 if service is running."""
    permission_classes = []
    authentication_classes = []

    def get(self, request):
        return Response({'status': 'healthy', 'service': 'b2b-api'})


class ReadyView(APIView):
    """Readiness check - returns 200 if service can handle requests."""
    permission_classes = []
    authentication_classes = []

    def get(self, request):
        checks = {}

        # Database check
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
            checks['database'] = 'ok'
        except Exception as e:
            checks['database'] = f'error: {str(e)}'

        # Redis check
        try:
            cache.set('health_check', 'ok', 10)
            if cache.get('health_check') == 'ok':
                checks['redis'] = 'ok'
            else:
                checks['redis'] = 'error: cache miss'
        except Exception as e:
            checks['redis'] = f'error: {str(e)}'

        # Overall status
        all_ok = all(v == 'ok' for v in checks.values())
        http_status = status.HTTP_200_OK if all_ok else status.HTTP_503_SERVICE_UNAVAILABLE

        return Response({
            'status': 'ready' if all_ok else 'not_ready',
            'checks': checks,
        }, status=http_status)


class LiveView(APIView):
    """Liveness check - returns 200 if process is alive."""
    permission_classes = []
    authentication_classes = []

    def get(self, request):
        return Response({'status': 'alive'})