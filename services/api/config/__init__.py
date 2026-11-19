# B2B Micro-SaaS API Configuration
# Celery app will be loaded when needed

try:
    from celery_app import app as celery_app
    __all__ = ('celery_app',)
except ImportError:
    __all__ = ()