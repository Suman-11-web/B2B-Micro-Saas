"""
Custom JWT authentication for multi-tenant API.
"""
from rest_framework_simplejwt.authentication import JWTAuthentication as BaseJWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework import exceptions
from apps.accounts.models import Membership


class JWTAuthentication(BaseJWTAuthentication):
    """
    Extended JWT authentication that validates tenant membership.
    """

    def authenticate(self, request):
        # First, do standard JWT authentication
        result = super().authenticate(request)
        if result is None:
            return None

        user, validated_token = result

        # Check if user is active
        if not user.is_active:
            raise exceptions.AuthenticationFailed('User account is disabled.', code='user_inactive')

        # Get tenant from request (set by TenantMiddleware)
        company = getattr(request, 'company', None)

        # If no company resolved yet, try to get from token
        if not company:
            company_id = validated_token.get('company_id')
            if company_id:
                from apps.accounts.models import Company
                try:
                    company = Company.objects.get(id=company_id, status__in=['active', 'trial'])
                    request.company = company
                except Company.DoesNotExist:
                    pass

        # If still no company, check if user has only one company
        if not company:
            companies = user.get_companies()
            if companies.count() == 1:
                company = companies.first()
                request.company = company

        # If company is resolved, verify membership
        if company:
            membership = Membership.objects.filter(
                company=company,
                user=user,
                status=Membership.Status.ACTIVE
            ).first()

            if not membership:
                raise exceptions.AuthenticationFailed(
                    'You are not a member of this company.',
                    code='not_member'
                )

            # Attach membership to request for easy access
            request.membership = membership

        return user, validated_token

    def get_user(self, validated_token):
        """Override to use UUID user model."""
        from apps.accounts.models import User
        try:
            user_id = validated_token['user_id']
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise InvalidToken('User not found.')
        except KeyError:
            raise InvalidToken('Token missing user_id.')

        if not user.is_active:
            raise InvalidToken('User is inactive.')

        return user