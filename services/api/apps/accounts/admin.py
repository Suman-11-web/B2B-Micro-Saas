"""
Django admin configuration for accounts app.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from apps.accounts.models import (
    Company, User, Membership, SubscriptionPlan, Subscription,
    ApiKey, AuditLog, UsageEvent
)
from django.contrib import admin


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'domain', 'status', 'member_count', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['name', 'slug', 'domain']
    ordering = ['-created_at']

    def member_count(self, obj):
        return obj.memberships.filter(status=Membership.Status.ACTIVE).count()
    member_count.short_description = "Members"


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['email', 'name', 'is_active', 'is_staff', 'last_login']
    list_filter = ['is_active', 'is_staff', 'is_superuser', 'date_joined']
    search_fields = ['email', 'name']
    ordering = ['-date_joined']

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('name', 'avatar_url', 'timezone', 'language')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'name', 'password1', 'password2'),
        }),
    )
    search_fields = ['email', 'name']
    ordering = ['email']


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ['company', 'user', 'role', 'status', 'invited_at', 'joined_at']
    list_filter = ['role', 'status', 'invited_at']
    search_fields = ['user__email', 'company__name']
    ordering = ['-invited_at']


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'key', 'price_monthly_inr', 'price_monthly_usd', 'user_limit', 'is_active', 'sort_order']
    list_filter = ['is_active', 'sort_order']
    search_fields = ['name', 'key']
    ordering = ['sort_order']


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ['company', 'plan', 'status', 'provider', 'current_period_end', 'cancel_at_period_end']
    list_filter = ['status', 'provider', 'cancel_at_period_end']
    search_fields = ['company__name', 'provider_subscription_id']
    ordering = ['-created_at']


@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    list_display = ['name', 'company', 'key_prefix', 'scopes', 'is_active', 'expires_at', 'last_used_at']
    list_filter = ['is_active', 'expires_at', 'created_at']
    search_fields = ['name', 'key_prefix', 'company__name']
    ordering = ['-created_at']


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['company', 'user', 'action', 'resource_type', 'resource_id', 'created_at']
    list_filter = ['action', 'resource_type', 'created_at']
    search_fields = ['company__name', 'user__email', 'resource_id']
    ordering = ['-created_at']

    readonly_fields = [f.name for f in AuditLog._meta.fields]


@admin.register(UsageEvent)
class UsageEventAdmin(admin.ModelAdmin):
    list_display = ['company', 'user', 'event_type', 'quantity', 'created_at']
    list_filter = ['event_type', 'created_at']
    search_fields = ['company__name', 'user__email']
    ordering = ['-created_at']