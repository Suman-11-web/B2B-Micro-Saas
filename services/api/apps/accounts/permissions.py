"""
Custom permissions for multi-tenant access control.
"""
from rest_framework import permissions
from apps.accounts.models import Membership


class BelongsToTenant(permissions.BasePermission):
    """
    Permission class that ensures the user belongs to the tenant (company)
    associated with the request. This is the core multi-tenancy enforcement.
    """

    message = 'You do not have access to this company\'s resources.'

    def has_permission(self, request, view):
        # Must be authenticated
        if not request.user or not request.user.is_authenticated:
            return False

        # Must have a company resolved
        if not hasattr(request, 'company') or not request.company:
            return False

        # Check user is an active member of this company
        return Membership.objects.filter(
            company=request.company,
            user=request.user,
            status=Membership.Status.ACTIVE
        ).exists()

    def has_object_permission(self, request, view, obj):
        # For object-level permissions, ensure the object belongs to the same company
        if hasattr(obj, 'company'):
            return obj.company_id == request.company.id
        # For User objects, check membership
        if hasattr(obj, 'memberships'):
            return obj.memberships.filter(
                company=request.company,
                status=Membership.Status.ACTIVE
            ).exists()
        return False


class IsOwnerOrAdmin(permissions.BasePermission):
    """Permission for actions requiring owner or admin role."""

    message = 'Only owners and admins can perform this action.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if not hasattr(request, 'company') or not request.company:
            return False

        membership = Membership.objects.filter(
            company=request.company,
            user=request.user,
            status=Membership.Status.ACTIVE
        ).first()

        return membership and membership.role in [Membership.Role.OWNER, Membership.Role.ADMIN]


class IsOwner(permissions.BasePermission):
    """Permission for actions requiring owner role."""

    message = 'Only owners can perform this action.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if not hasattr(request, 'company') or not request.company:
            return False

        membership = Membership.objects.filter(
            company=request.company,
            user=request.user,
            status=Membership.Status.ACTIVE
        ).first()

        return membership and membership.role == Membership.Role.OWNER


def HasPermission(required_permission):
    """
    Factory returning a BasePermission subclass that checks for a specific permission.
    Usage: permission_classes = [HasPermission('manage_billing')]
    """
    class _HasPermission(permissions.BasePermission):
        def has_permission(self, request, view):
            if not request.user or not request.user.is_authenticated:
                return False
            if not hasattr(request, 'company') or not request.company:
                return False

            membership = Membership.objects.filter(
                company=request.company,
                user=request.user,
                status=Membership.Status.ACTIVE
            ).first()

            return bool(membership and membership.has_permission(required_permission))

    _HasPermission.__name__ = f'HasPermission_{required_permission}'
    return _HasPermission


class IsApiKeyAuthenticated(permissions.BasePermission):
    """Permission for API key authentication."""

    def has_permission(self, request, view):
        # Check for API key in header
        api_key = request.META.get('HTTP_X_API_KEY')
        if not api_key:
            return False

        from apps.accounts.models import ApiKey
        try:
            # Extract prefix (first 12 chars, matching ApiKeyCreateSerializer)
            key_prefix = api_key[:12]
            api_key_obj = ApiKey.objects.select_related('company').get(
                key_prefix=key_prefix,
                is_active=True
            )
        except ApiKey.DoesNotExist:
            return False

        # Verify the full key
        if not ApiKey.verify_key(api_key, api_key_obj.key_hash):
            return False

        # Check expiration
        if api_key_obj.expires_at and api_key_obj.expires_at < timezone.now():
            return False

        # Update last used
        api_key_obj.last_used_at = timezone.now()
        api_key_obj.save(update_fields=['last_used_at'])

        # Set company and user on request
        request.company = api_key_obj.company
        request.api_key = api_key_obj
        request.user = api_key_obj.created_by  # May be None

        return True


class ReadOnly(permissions.BasePermission):
    """Allow only safe methods (GET, HEAD, OPTIONS)."""

    def has_permission(self, request, view):
        return request.method in permissions.SAFE_METHODS


# Import timezone for ApiKey permission
from django.utils import timezone