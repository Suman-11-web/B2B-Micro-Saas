"""
Serializers for accounts app - authentication, users, companies, memberships.
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model
from apps.accounts.models import (
    Company, User, Membership, SubscriptionPlan, Subscription,
    ApiKey, AuditLog, UsageEvent
)
import secrets


User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model."""
    companies = serializers.SerializerMethodField()
    current_company = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'email', 'name', 'is_active', 'is_staff',
            'date_joined', 'last_login', 'avatar_url',
            'timezone', 'language', 'metadata',
            'companies', 'current_company',
        ]
        read_only_fields = ['id', 'date_joined', 'last_login', 'is_staff']

    def get_companies(self, obj):
        companies = obj.get_companies()
        return CompanyMinimalSerializer(companies, many=True).data

    def get_current_company(self, obj):
        request = self.context.get('request')
        if request and hasattr(request, 'company') and request.company:
            return CompanyMinimalSerializer(request.company).data
        return None


class UserCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating users."""
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ['email', 'name', 'password', 'timezone', 'language']

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User.objects.create_user(**validated_data, password=password)
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user profile."""

    class Meta:
        model = User
        fields = ['name', 'avatar_url', 'timezone', 'language', 'metadata']


class CompanyMinimalSerializer(serializers.ModelSerializer):
    """Minimal company serializer for nested use."""

    class Meta:
        model = Company
        fields = ['id', 'name', 'slug', 'domain', 'status']
        read_only_fields = fields


class CompanySerializer(serializers.ModelSerializer):
    """Serializer for Company model."""
    member_count = serializers.IntegerField(read_only=True)
    plan = serializers.SerializerMethodField()
    subscription_status = serializers.SerializerMethodField()

    class Meta:
        model = Company
        fields = [
            'id', 'name', 'slug', 'domain', 'status',
            'settings', 'member_count', 'plan', 'subscription_status',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'member_count']

    def get_plan(self, obj):
        plan = obj.plan
        if plan:
            return SubscriptionPlanMinimalSerializer(plan).data
        return None

    def get_subscription_status(self, obj):
        sub = obj.active_subscription
        if sub:
            return {
                'status': sub.status,
                'current_period_end': sub.current_period_end,
                'days_remaining': sub.days_remaining,
            }
        return None


class CompanyCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a company."""

    class Meta:
        model = Company
        fields = ['name', 'slug', 'domain']

    def validate_slug(self, value):
        if Company.objects.filter(slug=value).exists():
            raise serializers.ValidationError('This slug is already taken.')
        return value.lower()

    def create(self, validated_data):
        user = self.context['request'].user
        return Company.objects.create_company(
            name=validated_data['name'],
            slug=validated_data['slug'],
            domain=validated_data.get('domain'),
            owner=user
        )


class MembershipSerializer(serializers.ModelSerializer):
    """Serializer for Membership model."""
    user = UserSerializer(read_only=True)
    user_email = serializers.EmailField(write_only=True, required=False)
    invited_by = UserSerializer(read_only=True)
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = Membership
        fields = [
            'id', 'user', 'user_email', 'role', 'status',
            'invited_by', 'invited_at', 'joined_at',
            'metadata', 'permissions',
        ]
        read_only_fields = ['id', 'invited_by', 'invited_at', 'joined_at', 'user']

    def get_permissions(self, obj):
        # Return list of permissions for this role
        role_permissions = {
            Membership.Role.OWNER: ['*'],
            Membership.Role.ADMIN: [
                'manage_users', 'manage_billing', 'manage_integrations',
                'manage_documents', 'manage_queries', 'view_analytics',
                'manage_api_keys', 'view_audit_logs',
            ],
            Membership.Role.MEMBER: [
                'manage_documents', 'manage_queries', 'view_analytics',
            ],
            Membership.Role.VIEWER: [
                'view_documents', 'view_queries', 'view_analytics',
            ],
        }
        return role_permissions.get(obj.role, [])


class InviteMemberSerializer(serializers.Serializer):
    """Serializer for inviting a member."""
    user_email = serializers.EmailField()
    role = serializers.ChoiceField(choices=Membership.Role.choices, default=Membership.Role.MEMBER)

    def validate_user_email(self, value):
        request = self.context['request']
        company = request.company

        # Check if already a member
        if Membership.objects.filter(company=company, user__email=value).exists():
            raise serializers.ValidationError('This user is already a member.')

        return value


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    """Serializer for SubscriptionPlan model."""

    class Meta:
        model = SubscriptionPlan
        fields = [
            'id', 'key', 'name', 'description',
            'price_monthly_inr', 'price_monthly_usd',
            'storage_limit_bytes', 'query_limit_monthly', 'user_limit',
            'features', 'is_active', 'sort_order',
        ]
        read_only_fields = ['id']


class SubscriptionPlanMinimalSerializer(serializers.ModelSerializer):
    """Minimal plan serializer."""

    class Meta:
        model = SubscriptionPlan
        fields = ['id', 'key', 'name', 'price_monthly_inr', 'price_monthly_usd', 'features']


class SubscriptionSerializer(serializers.ModelSerializer):
    """Serializer for Subscription model."""
    plan = SubscriptionPlanMinimalSerializer(read_only=True)

    class Meta:
        model = Subscription
        fields = [
            'id', 'plan', 'status', 'provider',
            'current_period_start', 'current_period_end',
            'cancel_at_period_end', 'cancelled_at', 'trial_end',
            'days_remaining', 'is_active',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields


class ApiKeySerializer(serializers.ModelSerializer):
    """Serializer for API keys (without the actual key)."""
    scopes_display = serializers.SerializerMethodField()
    is_expired = serializers.SerializerMethodField()

    class Meta:
        model = ApiKey
        fields = [
            'id', 'name', 'key_prefix', 'scopes', 'scopes_display',
            'expires_at', 'last_used_at', 'is_active', 'is_expired',
            'created_by', 'created_at',
        ]
        read_only_fields = ['id', 'key_prefix', 'last_used_at', 'created_by', 'created_at']

    def get_scopes_display(self, obj):
        return [s.value if hasattr(s, 'value') else s for s in obj.scopes]

    def get_is_expired(self, obj):
        if obj.expires_at:
            from django.utils import timezone
            return obj.expires_at < timezone.now()
        return False


class ApiKeyCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating API keys - returns the raw key once."""
    raw_key = serializers.CharField(read_only=True)
    scopes = serializers.ListField(
        child=serializers.ChoiceField(choices=ApiKey.Scope.choices),
        default=list
    )
    expires_in_days = serializers.IntegerField(write_only=True, required=False, min_value=1, max_value=3650)

    class Meta:
        model = ApiKey
        fields = ['name', 'scopes', 'expires_in_days', 'raw_key']
        read_only_fields = ['raw_key']

    def create(self, validated_data):
        request = self.context['request']
        expires_in_days = validated_data.pop('expires_in_days', None)

        raw_key = ApiKey.generate_key()
        key_hash = ApiKey.hash_key(raw_key)
        key_prefix = raw_key[:12]  # e.g., "b2b_abc123def"

        from django.utils import timezone
        from datetime import timedelta

        expires_at = None
        if expires_in_days:
            expires_at = timezone.now() + timedelta(days=expires_in_days)

        api_key = ApiKey.objects.create(
            company=request.company,
            name=validated_data['name'],
            key_hash=key_hash,
            key_prefix=key_prefix,
            scopes=validated_data.get('scopes', []),
            expires_at=expires_at,
            created_by=request.user,
        )

        # Attach raw key to instance for response
        api_key.raw_key = raw_key
        return api_key


class AuditLogSerializer(serializers.ModelSerializer):
    """Serializer for AuditLog model."""
    user_email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            'id', 'action', 'resource_type', 'resource_id',
            'user', 'user_email', 'ip_address', 'user_agent',
            'metadata', 'created_at',
        ]
        read_only_fields = fields


class UsageEventSerializer(serializers.ModelSerializer):
    """Serializer for UsageEvent model."""
    user_email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = UsageEvent
        fields = [
            'id', 'event_type', 'quantity', 'metadata',
            'user', 'user_email', 'created_at',
        ]
        read_only_fields = fields


# Auth Serializers
class RegisterSerializer(serializers.Serializer):
    """Serializer for user registration."""
    email = serializers.EmailField()
    name = serializers.CharField(max_length=255)
    password = serializers.CharField(min_length=8, write_only=True)
    company_name = serializers.CharField(max_length=255)
    company_slug = serializers.SlugField(max_length=100)

    def validate_company_slug(self, value):
        if Company.objects.filter(slug=value.lower()).exists():
            raise serializers.ValidationError('This company slug is already taken.')
        return value.lower()

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('A user with this email already exists.')
        return value


class LoginSerializer(serializers.Serializer):
    """Serializer for user login."""
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    remember_me = serializers.BooleanField(default=False)


class PasswordResetRequestSerializer(serializers.Serializer):
    """Serializer for password reset request."""
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Serializer for password reset confirmation."""
    token = serializers.CharField()
    password = serializers.CharField(min_length=8, write_only=True)


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for changing password (authenticated)."""
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(min_length=8, write_only=True)


class TokenRefreshSerializer(serializers.Serializer):
    """Serializer for token refresh."""
    refresh = serializers.CharField()