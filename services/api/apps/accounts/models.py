"""
Core models for multi-tenancy, authentication, and authorization.
This is the foundation of the B2B SaaS architecture.
"""
import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.conf import settings


class TenantModel(models.Model):
    """
    Abstract base model for all tenant-scoped models.
    Automatically sets the company from the current request context.
    """
    company = models.ForeignKey(
        'accounts.Company',
        on_delete=models.CASCADE,
        related_name='%(class)s_set',
        help_text='The company (tenant) this record belongs to.'
    )

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        # Auto-set company from thread-local request if not explicitly set
        if not self.company_id:
            from apps.accounts.middleware import get_current_company
            company = get_current_company()
            if company:
                self.company = company
        super().save(*args, **kwargs)


class CompanyManager(models.Manager):
    def create_company(self, name, slug, domain=None, owner=None):
        company = self.create(name=name, slug=slug, domain=domain)
        if owner:
            Membership.objects.create(
                company=company,
                user=owner,
                role=Membership.Role.OWNER,
                status=Membership.Status.ACTIVE
            )
        return company


class Company(models.Model):
    """Multi-tenant company/organization."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=100, unique=True, db_index=True)
    domain = models.CharField(max_length=255, unique=True, null=True, blank=True, help_text='Custom domain for white-label')
    status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Active'),
            ('suspended', 'Suspended'),
            ('trial', 'Trial'),
            ('cancelled', 'Cancelled'),
        ],
        default='trial'
    )
    settings = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CompanyManager()

    class Meta:
        db_table = 'companies'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.name} ({self.slug})"

    @property
    def active_subscription(self):
        return self.subscriptions.filter(status='active').first()

    @property
    def plan(self):
        sub = self.active_subscription
        return sub.plan if sub else None

    @property
    def member_count(self):
        return self.memberships.filter(status=Membership.Status.ACTIVE).count()


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Custom user model with email as username."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(_('email address'), unique=True, db_index=True)
    name = models.CharField(_('full name'), max_length=255)
    is_active = models.BooleanField(_('active'), default=True)
    is_staff = models.BooleanField(_('staff status'), default=False)
    is_superuser = models.BooleanField(_('superuser status'), default=False)
    date_joined = models.DateTimeField(_('date joined'), auto_now_add=True)
    last_login = models.DateTimeField(_('last login'), null=True, blank=True)
    avatar_url = models.URLField(blank=True, null=True)
    timezone = models.CharField(max_length=50, default='UTC')
    language = models.CharField(max_length=10, default='en')
    metadata = models.JSONField(default=dict, blank=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name']

    class Meta:
        db_table = 'users'
        ordering = ['-date_joined']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return self.email

    def get_full_name(self):
        return self.name

    def get_short_name(self):
        return self.name.split()[0] if self.name else ''

    def get_companies(self):
        """Get all companies this user is a member of."""
        return Company.objects.filter(memberships__user=self, memberships__status=Membership.Status.ACTIVE)


class Membership(models.Model):
    """User's membership in a company with role-based access."""
    class Role(models.TextChoices):
        OWNER = 'owner', _('Owner')
        ADMIN = 'admin', _('Admin')
        MEMBER = 'member', _('Member')
        VIEWER = 'viewer', _('Viewer')

    class Status(models.TextChoices):
        ACTIVE = 'active', _('Active')
        INVITED = 'invited', _('Invited')
        SUSPENDED = 'suspended', _('Suspended')
        REMOVED = 'removed', _('Removed')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='memberships')
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MEMBER)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.INVITED)
    invited_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='sent_invitations')
    invited_at = models.DateTimeField(auto_now_add=True)
    joined_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'memberships'
        unique_together = ['company', 'user']
        ordering = ['-joined_at', '-invited_at']
        indexes = [
            models.Index(fields=['company', 'status']),
            models.Index(fields=['user', 'status']),
        ]

    def __str__(self):
        return f"{self.user.email} @ {self.company.slug} ({self.role})"

    def activate(self):
        self.status = self.Status.ACTIVE
        self.joined_at = timezone.now()
        self.save(update_fields=['status', 'joined_at'])

    def has_permission(self, permission):
        """Check if role has a specific permission."""
        role_permissions = {
            self.Role.OWNER: ['*'],
            self.Role.ADMIN: [
                'manage_users', 'manage_billing', 'manage_integrations',
                'manage_documents', 'manage_queries', 'view_analytics',
                'manage_api_keys', 'view_audit_logs',
            ],
            self.Role.MEMBER: [
                'manage_documents', 'manage_queries', 'view_analytics',
            ],
            self.Role.VIEWER: [
                'view_documents', 'view_queries', 'view_analytics',
            ],
        }
        perms = role_permissions.get(self.role, [])
        return '*' in perms or permission in perms


class SubscriptionPlan(models.Model):
    """Available subscription tiers."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.SlugField(max_length=50, unique=True)  # free, starter, growth, business
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    price_monthly_inr = models.PositiveIntegerField(default=0)
    price_monthly_usd = models.PositiveIntegerField(default=0)
    storage_limit_bytes = models.BigIntegerField(default=0)
    query_limit_monthly = models.PositiveIntegerField(default=0)
    user_limit = models.IntegerField(default=0)  # -1 = unlimited
    features = models.JSONField(default=list)
    stripe_price_id = models.CharField(max_length=100, blank=True)
    razorpay_plan_id = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'subscription_plans'
        ordering = ['sort_order']

    def __str__(self):
        return f"{self.name} (${self.price_monthly_usd}/₹{self.price_monthly_inr})"


class Subscription(models.Model):
    """Company's active subscription."""
    class Status(models.TextChoices):
        ACTIVE = 'active', _('Active')
        TRIALING = 'trialing', _('Trialing')
        PAST_DUE = 'past_due', _('Past Due')
        CANCELLED = 'cancelled', _('Cancelled')
        EXPIRED = 'expired', _('Expired')
        INCOMPLETE = 'incomplete', _('Incomplete')

    class Provider(models.TextChoices):
        STRIPE = 'stripe', _('Stripe')
        RAZORPAY = 'razorpay', _('Razorpay')
        MANUAL = 'manual', _('Manual')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='subscriptions')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name='subscriptions')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.TRIALING)
    provider = models.CharField(max_length=20, choices=Provider.choices, default=Provider.MANUAL)
    provider_subscription_id = models.CharField(max_length=255, blank=True)
    provider_customer_id = models.CharField(max_length=255, blank=True)
    current_period_start = models.DateTimeField()
    current_period_end = models.DateTimeField()
    cancel_at_period_end = models.BooleanField(default=False)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    trial_end = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'subscriptions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'status']),
            models.Index(fields=['provider', 'provider_subscription_id']),
        ]

    def __str__(self):
        return f"{self.company.slug} - {self.plan.name} ({self.status})"

    @property
    def is_active(self):
        return self.status in [self.Status.ACTIVE, self.Status.TRIALING]

    @property
    def days_remaining(self):
        if self.current_period_end:
            delta = self.current_period_end - timezone.now()
            return max(0, delta.days)
        return 0


class ApiKey(models.Model):
    """API keys for programmatic access."""
    class Scope(models.TextChoices):
        READ = 'read', _('Read')
        WRITE = 'write', _('Write')
        ADMIN = 'admin', _('Admin')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='api_keys')
    name = models.CharField(max_length=100)
    key_hash = models.CharField(max_length=255)  # bcrypt hash
    key_prefix = models.CharField(max_length=20)  # First 8 chars for identification
    scopes = models.JSONField(default=list)  # List of Scope values
    expires_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_api_keys')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'api_keys'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'is_active']),
            models.Index(fields=['key_prefix']),
        ]

    def __str__(self):
        return f"{self.name} ({self.key_prefix}...)"

    @classmethod
    def generate_key(cls):
        import secrets
        raw_key = f"b2b_{secrets.token_urlsafe(32)}"
        return raw_key

    @classmethod
    def hash_key(cls, raw_key):
        from django.contrib.auth.hashers import make_password
        return make_password(raw_key)

    @classmethod
    def verify_key(cls, raw_key, key_hash):
        from django.contrib.auth.hashers import check_password
        return check_password(raw_key, key_hash)


class AuditLog(models.Model):
    """Immutable audit trail for all tenant-scoped actions."""
    class Action(models.TextChoices):
        CREATE = 'create', _('Create')
        READ = 'read', _('Read')
        UPDATE = 'update', _('Update')
        DELETE = 'delete', _('Delete')
        LOGIN = 'login', _('Login')
        LOGOUT = 'logout', _('Logout')
        EXPORT = 'export', _('Export')
        IMPORT = 'import', _('Import')
        INVITE = 'invite', _('Invite')
        REVOKE = 'revoke', _('Revoke')
        UPGRADE = 'upgrade', _('Upgrade')
        DOWNGRADE = 'downgrade', _('Downgrade')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='audit_logs')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    action = models.CharField(max_length=20, choices=Action.choices)
    resource_type = models.CharField(max_length=100)
    resource_id = models.CharField(max_length=100, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'audit_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'created_at']),
            models.Index(fields=['company', 'resource_type', 'resource_id']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['action']),
        ]

    def __str__(self):
        return f"{self.action} {self.resource_type} by {self.user or 'system'}"


class UsageEvent(models.Model):
    """Metering events for billing and quota enforcement."""
    class EventType(models.TextChoices):
        QUERY = 'query', _('Query')
        EMBEDDING = 'embedding', _('Embedding')
        STORAGE = 'storage', _('Storage')
        ANALYTICS = 'analytics', _('Analytics')
        API_CALL = 'api_call', _('API Call')
        DOCUMENT_UPLOAD = 'document_upload', _('Document Upload')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='usage_events')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='usage_events')
    event_type = models.CharField(max_length=30, choices=EventType.choices)
    quantity = models.PositiveIntegerField(default=1)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'usage_events'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'event_type', 'created_at']),
            models.Index(fields=['company', 'created_at']),
        ]

    def __str__(self):
        return f"{self.company.slug} - {self.event_type}: {self.quantity}"