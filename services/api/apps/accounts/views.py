"""
Views for accounts app - authentication, users, companies, memberships, billing.
"""
from rest_framework import viewsets, status, generics, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone
from apps.accounts.models import (
    Company, User, Membership, SubscriptionPlan, Subscription,
    ApiKey, AuditLog, UsageEvent
)
from apps.accounts.serializers import (
    UserSerializer, UserCreateSerializer, UserUpdateSerializer,
    CompanySerializer, CompanyCreateSerializer, CompanyMinimalSerializer,
    MembershipSerializer, InviteMemberSerializer,
    SubscriptionPlanSerializer, SubscriptionSerializer,
    ApiKeySerializer, ApiKeyCreateSerializer,
    AuditLogSerializer, UsageEventSerializer,
    RegisterSerializer, LoginSerializer,
    PasswordResetRequestSerializer, PasswordResetConfirmSerializer,
    ChangePasswordSerializer,
)
from apps.accounts.permissions import (
    BelongsToTenant, IsOwnerOrAdmin, IsOwner, HasPermission
)

User = get_user_model()


class AuthViewSet(viewsets.GenericViewSet):
    """Authentication endpoints."""
    permission_classes = [permissions.AllowAny]

    @action(detail=False, methods=['post'])
    def register(self, request):
        """Register a new user and company."""
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        # Create user
        user = User.objects.create_user(
            email=data['email'],
            name=data['name'],
            password=data['password'],
        )

        # Create company
        company = Company.objects.create_company(
            name=data['company_name'],
            slug=data['company_slug'],
            owner=user
        )

        # Create free subscription
        free_plan = SubscriptionPlan.objects.filter(key='free').first()
        if free_plan:
            Subscription.objects.create(
                company=company,
                plan=free_plan,
                status=Subscription.Status.ACTIVE,
                provider=Subscription.Provider.MANUAL,
                current_period_start=timezone.now(),
                current_period_end=timezone.now() + timezone.timedelta(days=3650),
            )

        # Generate tokens
        refresh = RefreshToken.for_user(user)
        refresh['company_id'] = str(company.id)

        return Response({
            'user': UserSerializer(user, context={'request': request}).data,
            'company': CompanySerializer(company, context={'request': request}).data,
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'])
    def login(self, request):
        """Login with email/password."""
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        password = serializer.validated_data['password']

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {'error': 'invalid_credentials', 'message': 'Invalid email or password.'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        if not user.check_password(password):
            return Response(
                {'error': 'invalid_credentials', 'message': 'Invalid email or password.'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        if not user.is_active:
            return Response(
                {'error': 'account_disabled', 'message': 'Account is disabled.'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Get user's companies
        companies = user.get_companies()

        # If user has multiple companies, require company selection
        company_id = request.data.get('company_id')
        if companies.count() > 1 and not company_id:
            return Response({
                'error': 'company_required',
                'message': 'Please select a company.',
                'companies': CompanyMinimalSerializer(companies, many=True).data,
            }, status=status.HTTP_400_BAD_REQUEST)

        if company_id:
            try:
                company = companies.get(id=company_id)
            except Company.DoesNotExist:
                return Response(
                    {'error': 'invalid_company', 'message': 'Invalid company selection.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            company = companies.first()

        # Generate tokens with company
        refresh = RefreshToken.for_user(user)
        refresh['company_id'] = str(company.id)

        # Update last login
        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])

        return Response({
            'user': UserSerializer(user, context={'request': request}).data,
            'company': CompanySerializer(company, context={'request': request}).data,
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        })

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def logout(self, request):
        """Logout - blacklist refresh token."""
        refresh_token = request.data.get('refresh')
        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
            except Exception:
                pass
        return Response({'message': 'Logged out successfully.'})

    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def refresh(self, request):
        """Refresh access token."""
        serializer = TokenRefreshView.as_view()(request._request)
        return serializer

    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def password_reset_request(self, request):
        """Request password reset email."""
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # In production, send email with reset token
        return Response({'message': 'If the email exists, a reset link has been sent.'})

    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def password_reset_confirm(self, request):
        """Confirm password reset with token."""
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # In production, validate token and reset password
        return Response({'message': 'Password has been reset.'})

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def change_password(self, request):
        """Change password for authenticated user."""
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        if not user.check_password(serializer.validated_data['current_password']):
            return Response(
                {'error': 'invalid_password', 'message': 'Current password is incorrect.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.set_password(serializer.validated_data['new_password'])
        user.save()

        return Response({'message': 'Password changed successfully.'})

    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def me(self, request):
        """Get current user info."""
        return Response(UserSerializer(request.user, context={'request': request}).data)

    @action(detail=False, methods=['patch'], permission_classes=[permissions.IsAuthenticated])
    def update_me(self, request):
        """Update current user profile."""
        serializer = UserUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserSerializer(request.user, context={'request': request}).data)


class CompanyViewSet(viewsets.ModelViewSet):
    """Company management."""
    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    permission_classes = [permissions.IsAuthenticated, BelongsToTenant]
    lookup_field = 'id'

    def get_queryset(self):
        # Users can only see their own company
        return Company.objects.filter(id=self.request.company.id) if self.request.company else Company.objects.none()

    def get_serializer_class(self):
        if self.action == 'create':
            return CompanyCreateSerializer
        return CompanySerializer

    @action(detail=False, methods=['get'])
    def current(self, request):
        """Get current company."""
        if not request.company:
            return Response({'error': 'no_company', 'message': 'No company selected.'}, status=400)
        serializer = self.get_serializer(request.company)
        return Response(serializer.data)

    @action(detail=False, methods=['patch'])
    def update_current(self, request):
        """Update current company settings."""
        if not request.company:
            return Response({'error': 'no_company', 'message': 'No company selected.'}, status=400)
        serializer = self.get_serializer(request.company, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class MembershipViewSet(viewsets.ModelViewSet):
    """Membership management."""
    queryset = Membership.objects.select_related('user', 'invited_by')
    serializer_class = MembershipSerializer
    permission_classes = [permissions.IsAuthenticated, BelongsToTenant, IsOwnerOrAdmin]
    lookup_field = 'id'

    def get_queryset(self):
        return Membership.objects.filter(company=self.request.company).select_related('user', 'invited_by')

    def get_serializer_class(self):
        if self.action == 'create':
            return InviteMemberSerializer
        return MembershipSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['user_email']
        role = serializer.validated_data['role']

        # Get or create user
        user, created = User.objects.get_or_create(
            email=email,
            defaults={'name': email.split('@')[0], 'is_active': False}
        )

        # Create membership
        membership = Membership.objects.create(
            company=request.company,
            user=user,
            role=role,
            status=Membership.Status.INVITED,
            invited_by=request.user,
        )

        # TODO: Send invitation email

        return Response(
            MembershipSerializer(membership, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['post'])
    def resend_invite(self, request, id=None):
        """Resend invitation email."""
        membership = self.get_object()
        if membership.status != Membership.Status.INVITED:
            return Response(
                {'error': 'not_invited', 'message': 'This member is not in invited status.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        # TODO: Send invitation email
        return Response({'message': 'Invitation resent.'})

    @action(detail=True, methods=['post'])
    def remove(self, request, id=None):
        """Remove a member."""
        membership = self.get_object()
        if membership.role == Membership.Role.OWNER:
            return Response(
                {'error': 'cannot_remove_owner', 'message': 'Cannot remove the owner.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        membership.status = Membership.Status.REMOVED
        membership.save()
        return Response({'message': 'Member removed.'})

    @action(detail=True, methods=['patch'])
    def change_role(self, request, id=None):
        """Change member role."""
        membership = self.get_object()
        new_role = request.data.get('role')
        if new_role not in Membership.Role.values:
            return Response(
                {'error': 'invalid_role', 'message': 'Invalid role.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if membership.role == Membership.Role.OWNER and new_role != Membership.Role.OWNER:
            return Response(
                {'error': 'cannot_change_owner', 'message': 'Cannot change owner role.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        membership.role = new_role
        membership.save()
        return Response(MembershipSerializer(membership, context={'request': request}).data)


class SubscriptionPlanViewSet(viewsets.ReadOnlyModelViewSet):
    """Available subscription plans."""
    queryset = SubscriptionPlan.objects.filter(is_active=True)
    serializer_class = SubscriptionPlanSerializer
    permission_classes = [permissions.AllowAny]


class SubscriptionViewSet(viewsets.GenericViewSet):
    """Subscription management for current company."""
    serializer_class = SubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated, BelongsToTenant, IsOwnerOrAdmin]

    def get_queryset(self):
        return Subscription.objects.filter(company=self.request.company).select_related('plan')

    def get_object(self):
        return self.request.company.active_subscription

    def retrieve(self, request, *args, **kwargs):
        """Get current subscription."""
        subscription = self.get_object()
        if not subscription:
            return Response(
                {'error': 'no_subscription', 'message': 'No active subscription.'},
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = self.get_serializer(subscription)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def create_checkout(self, request):
        """Create checkout session for plan upgrade."""
        plan_key = request.data.get('plan')
        provider = request.data.get('provider', 'stripe')

        try:
            plan = SubscriptionPlan.objects.get(key=plan_key, is_active=True)
        except SubscriptionPlan.DoesNotExist:
            return Response(
                {'error': 'invalid_plan', 'message': 'Invalid plan.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # TODO: Create Stripe/Razorpay checkout session
        # Return checkout URL

        return Response({
            'checkout_url': f'https://checkout.example.com/{plan_key}',
            'plan': SubscriptionPlanSerializer(plan).data,
        })

    @action(detail=False, methods=['post'])
    def cancel(self, request):
        """Cancel subscription at period end."""
        subscription = self.get_object()
        if not subscription:
            return Response(
                {'error': 'no_subscription', 'message': 'No active subscription.'},
                status=status.HTTP_404_NOT_FOUND
            )

        subscription.cancel_at_period_end = True
        subscription.save()

        return Response({'message': 'Subscription will be cancelled at period end.'})


class ApiKeyViewSet(viewsets.ModelViewSet):
    """API key management."""
    queryset = ApiKey.objects.all()
    serializer_class = ApiKeySerializer
    permission_classes = [permissions.IsAuthenticated, BelongsToTenant, HasPermission('manage_api_keys')]
    lookup_field = 'id'

    def get_queryset(self):
        return ApiKey.objects.filter(company=self.request.company)

    def get_serializer_class(self):
        if self.action == 'create':
            return ApiKeyCreateSerializer
        return ApiKeySerializer

    def create(self, request, *args, **kwargs):
        # Enforce Free-tier API key cap (strictly below 2 -> max 1 active key)
        sub = request.company.active_subscription or request.company.subscriptions.order_by('-created_at').first()
        plan_key = sub.plan.key if sub and sub.plan else 'free'
        active_keys = ApiKey.objects.filter(company=request.company, is_active=True).count()
        if plan_key == 'free' and active_keys >= 1:
            return Response(
                {
                    'error': 'api_key_limit_exceeded',
                    'message': 'Free plan is limited to 1 active API key. Upgrade to Starter or higher for more keys.',
                },
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        # The raw key is returned in the serializer response
        serializer.save()

    @action(detail=True, methods=['post'])
    def revoke(self, request, id=None):
        """Revoke an API key."""
        api_key = self.get_object()
        api_key.is_active = False
        api_key.save()
        return Response({'message': 'API key revoked.'})


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Audit log viewing (Business tier)."""
    queryset = AuditLog.objects.select_related('user')
    serializer_class = AuditLogSerializer
    permission_classes = [permissions.IsAuthenticated, BelongsToTenant, HasPermission('view_audit_logs')]
    filterset_fields = ['action', 'resource_type', 'user', 'created_at']
    search_fields = ['resource_id', 'user__email']
    ordering = ['-created_at']

    def get_queryset(self):
        return AuditLog.objects.filter(company=self.request.company).select_related('user')


class UsageEventViewSet(viewsets.ReadOnlyModelViewSet):
    """Usage event viewing."""
    queryset = UsageEvent.objects.select_related('user')
    serializer_class = UsageEventSerializer
    permission_classes = [permissions.IsAuthenticated, BelongsToTenant, IsOwnerOrAdmin]
    filterset_fields = ['event_type', 'created_at']
    ordering = ['-created_at']

    def get_queryset(self):
        return UsageEvent.objects.filter(company=self.request.company).select_related('user')