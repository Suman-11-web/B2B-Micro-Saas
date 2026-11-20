"""
Tenant resolution middleware for multi-tenancy support.
Resolves company from subdomain, header, or user context.
"""
import threading
from django.utils.deprecation import MiddlewareMixin
from django.http import Http404
from apps.accounts.models import Company


# Thread-local storage for current company
_current_company = threading.local()


def get_current_company():
    """Get the current company from thread-local storage."""
    return getattr(_current_company, 'company', None)


def set_current_company(company):
    """Set the current company in thread-local storage."""
    _current_company.company = company


def clear_current_company():
    """Clear the current company from thread-local storage."""
    if hasattr(_current_company, 'company'):
        del _current_company.company


class TenantMiddleware(MiddlewareMixin):
    """
    Resolves the tenant (company) from the request.
    Priority:
    1. X-Tenant-ID header (for API clients)
    2. Subdomain (for browser clients)
    3. User's default company (for authenticated users with single company)
    """

    def process_request(self, request):
        # Skip for health checks and static files
        if request.path.startswith('/health/') or request.path.startswith('/static/') or request.path.startswith('/media/'):
            return None

        company = None

        # 1. Check X-Tenant-ID header (API clients)
        tenant_id = request.META.get('HTTP_X_TENANT_ID')
        if tenant_id:
            try:
                company = Company.objects.get(id=tenant_id, status__in=['active', 'trial'])
            except Company.DoesNotExist:
                pass

        # 2. Check subdomain (browser clients)
        if not company:
            host = request.get_host().split(':')[0].lower()
            # Remove www. prefix
            if host.startswith('www.'):
                host = host[4:]

            # Check if it's a subdomain of our app domain
            # In production: app.yourdomain.com -> company slug = app
            # In development: localhost:3000 -> no subdomain
            parts = host.split('.')
            if len(parts) >= 2 and parts[0] not in ['www', 'api', 'app', 'admin', 'localhost', '127.0.0.1']:
                subdomain = parts[0]
                try:
                    company = Company.objects.get(slug=subdomain, status__in=['active', 'trial'])
                except Company.DoesNotExist:
                    pass

        # 3. Fallback: user's single company (for authenticated users)
        if not company and hasattr(request, 'user') and request.user.is_authenticated:
            companies = request.user.get_companies()
            if companies.count() == 1:
                company = companies.first()

        # Set company on request and thread-local
        request.company = company
        if company:
            set_current_company(company)

        return None

    def process_response(self, request, response):
        # Clear thread-local after request
        clear_current_company()
        return response


class AuditMiddleware(MiddlewareMixin):
    """Middleware to automatically log certain actions to audit trail."""

    AUDIT_METHODS = {'POST', 'PUT', 'PATCH', 'DELETE'}
    AUDIT_PATHS = [
        '/api/v1/companies/',
        '/api/v1/users/',
        '/api/v1/memberships/',
        '/api/v1/documents/',
        '/api/v1/queries/',
        '/api/v1/subscriptions/',
        '/api/v1/api-keys/',
        '/api/v1/data-sources/',
    ]

    def process_request(self, request):
        import uuid as _uuid
        request.trace_id = request.META.get('HTTP_X_REQUEST_ID') or str(_uuid.uuid4())
        # Store request info for audit logging in process_response
        request._audit_info = {
            'method': request.method,
            'path': request.path,
            'ip': self.get_client_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
        }
        return None

    def process_response(self, request, response):
        # Defense-in-depth security headers + correlation trace ID
        if hasattr(request, 'trace_id'):
            response['X-Request-ID'] = request.trace_id
        response.setdefault('X-Content-Type-Options', 'nosniff')
        response.setdefault('X-Frame-Options', 'DENY')
        response.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        response.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
        if request.path.startswith('/api/v1/auth/'):
            response['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
            response['Pragma'] = 'no-cache'

        # Log audit for mutating requests to audited paths
        if (hasattr(request, '_audit_info') and
            request._audit_info['method'] in self.AUDIT_METHODS and
            any(request._audit_info['path'].startswith(p) for p in self.AUDIT_PATHS) and
            hasattr(request, 'user') and request.user.is_authenticated):

            # Extract resource info from path
            resource_type, resource_id = self.extract_resource_info(request._audit_info['path'])

            # Determine action
            action_map = {
                'POST': 'create',
                'PUT': 'update',
                'PATCH': 'update',
                'DELETE': 'delete',
            }
            action = action_map.get(request._audit_info['method'], 'unknown')

            # Log asynchronously (in production, use Celery)
            if resource_type and getattr(request, 'company', None):
                from apps.accounts.models import AuditLog
                AuditLog.objects.create(
                    company=request.company,
                    user=request.user,
                    action=action,
                    resource_type=resource_type,
                    resource_id=str(resource_id) if resource_id else '',
                    ip_address=request._audit_info['ip'],
                    user_agent=request._audit_info['user_agent'],
                    metadata={
                        'path': request._audit_info['path'],
                        'status_code': response.status_code,
                    }
                )

        return response

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')

    def extract_resource_info(self, path):
        """Extract resource type and ID from API path."""
        # /api/v1/documents/uuid/ -> ('document', uuid)
        parts = path.strip('/').split('/')
        if len(parts) >= 4 and parts[0] == 'api' and parts[1] == 'v1':
            resource_type = parts[2].rstrip('s')  # documents -> document
            if len(parts) > 4 and parts[4]:
                return resource_type, parts[4]
            return resource_type, None
        return None, None