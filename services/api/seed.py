#!/usr/bin/env python
"""
Seed script to create initial data: plans, superuser, etc.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.core.management.base import BaseCommand
from django.conf import settings


def create_subscription_plans():
    from apps.accounts.models import SubscriptionPlan

    plans = [
        {
            'key': 'free',
            'name': 'Free',
            'description': 'Starter plan for individual use',
            'price_monthly_inr': 0,
            'price_monthly_usd': 0,
            'storage_limit_bytes': 1 * 1024 * 1024 * 1024,  # 1 GB
            'query_limit_monthly': 50,
            'user_limit': 2,
            'features': ['basic_qa', 'csv_upload'],
            'sort_order': 0,
        },
        {
            'key': 'starter',
            'name': 'Starter',
            'description': 'Perfect for small teams',
            'price_monthly_inr': 3000,
            'price_monthly_usd': 49,
            'storage_limit_bytes': 5 * 1024 * 1024 * 1024,  # 5 GB
            'query_limit_monthly': 500,
            'user_limit': 5,
            'features': ['basic_qa', 'csv_upload', 'pdf_upload', 'excel_upload', 'charts'],
            'sort_order': 1,
        },
        {
            'key': 'growth',
            'name': 'Growth',
            'description': 'For growing businesses',
            'price_monthly_inr': 7000,
            'price_monthly_usd': 99,
            'storage_limit_bytes': 20 * 1024 * 1024 * 1024,  # 20 GB
            'query_limit_monthly': 2500,
            'user_limit': 15,
            'features': ['basic_qa', 'csv_upload', 'pdf_upload', 'excel_upload', 'charts', 'db_connect', 'api_access'],
            'sort_order': 2,
        },
        {
            'key': 'business',
            'name': 'Business',
            'description': 'Enterprise-ready',
            'price_monthly_inr': 15000,
            'price_monthly_usd': 199,
            'storage_limit_bytes': 100 * 1024 * 1024 * 1024,  # 100 GB
            'query_limit_monthly': 10000,
            'user_limit': -1,  # unlimited
            'features': ['basic_qa', 'csv_upload', 'pdf_upload', 'excel_upload', 'charts', 'db_connect', 'api_access', 'sso', 'audit_logs', 'priority_support'],
            'sort_order': 3,
        },
    ]

    for plan_data in plans:
        plan, created = SubscriptionPlan.objects.get_or_create(
            key=plan_data['key'],
            defaults=plan_data
        )
        if created:
            print(f'Created plan: {plan.name}')
        else:
            print(f'Plan already exists: {plan.name}')


def create_admin_user():
    from apps.accounts.models import User

    admin_email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@example.com')
    admin_password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'change-me-immediately')

    try:
        user = User.objects.get(email=admin_email)
        if input('Admin user already exists. Reset password? (y/n): ').lower() == 'y':
            user.set_password(admin_password)
            user.save()
            print(f'Admin password reset for {admin_email}')
        else:
            print(f'Admin user exists: {admin_email}')
    except User.DoesNotExist:
        user = User.objects.create_superuser(
            email=admin_email,
            password=admin_password,
            name='Admin User',
            is_active=True,
            is_staff=True,
            is_superuser=True,
        )
        print(f'Created admin user: {admin_email}')


def main():
    print('Seeding B2B Micro-SaaS database...')

    # Create subscription plans
    print('\nCreating subscription plans...')
    create_subscription_plans()

    # Create admin user
    print('\nSetting up admin user...')
    create_admin_user()

    print('\nSeeding complete!')


if __name__ == '__main__':
    main()