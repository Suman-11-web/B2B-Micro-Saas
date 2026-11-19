"""
Celery application for B2B Micro-SaaS.
"""
import os
from celery import Celery
from celery.schedules import crontab

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('b2b_api')

# Load config from Django settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks
app.autodiscover_tasks([
    'apps.documents.tasks',
    'apps.queries.tasks',
    'apps.analytics.tasks',
    'apps.billing.tasks',
    'apps.audit.tasks',
])

# Celery Beat schedule
app.conf.beat_schedule = {
    # Daily usage aggregation at 1 AM UTC
    'aggregate-daily-usage': {
        'task': 'apps.billing.tasks.aggregate_daily_usage',
        'schedule': crontab(hour=1, minute=0),
    },
    # Weekly usage report on Mondays at 2 AM UTC
    'weekly-usage-report': {
        'task': 'apps.billing.tasks.generate_weekly_report',
        'schedule': crontab(hour=2, minute=0, day_of_week=1),
    },
    # Archive old audit logs daily at 3 AM UTC
    'archive-audit-logs': {
        'task': 'apps.audit.tasks.archive_old_audit_logs',
        'schedule': crontab(hour=3, minute=0),
    },
    # Check subscription status every hour
    'check-subscriptions': {
        'task': 'apps.billing.tasks.check_subscription_status',
        'schedule': crontab(minute=0),
    },
    # Clean up expired API keys daily at 4 AM UTC
    'cleanup-expired-api-keys': {
        'task': 'apps.accounts.tasks.cleanup_expired_api_keys',
        'schedule': crontab(hour=4, minute=0),
    },
}

# Task routing
app.conf.task_routes = {
    'apps.documents.tasks.parse_document': {'queue': 'parsing'},
    'apps.documents.tasks.chunk_document': {'queue': 'processing'},
    'apps.documents.tasks.embed_chunks': {'queue': 'embedding'},
    'apps.queries.tasks.process_query': {'queue': 'queries'},
    'apps.analytics.tasks.run_analytics': {'queue': 'analytics'},
    'apps.billing.tasks.aggregate_daily_usage': {'queue': 'billing'},
    'apps.billing.tasks.generate_weekly_report': {'queue': 'billing'},
    'apps.billing.tasks.check_subscription_status': {'queue': 'billing'},
    'apps.audit.tasks.archive_old_audit_logs': {'queue': 'maintenance'},
    'apps.accounts.tasks.cleanup_expired_api_keys': {'queue': 'maintenance'},
}

# Worker configuration
app.conf.update(
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    result_expires=86400,
    result_extended=True,
    timezone='UTC',
    enable_utc=True,
)


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')