"""
Django settings for B2B Micro-SaaS API.
Production-ready configuration with multi-tenancy support.
"""
import os
from pathlib import Path
import environ

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent

# Environment
env = environ.Env(
    DEBUG=(bool, False),
    SECRET_KEY=(str, ''),
    ALLOWED_HOSTS=(list, ['localhost', '127.0.0.1']),
    DATABASE_URL=(str, 'postgresql://b2b:b2bpassword@localhost:5432/b2b'),
    REDIS_URL=(str, 'redis://localhost:6379/0'),
    JWT_SECRET_KEY=(str, ''),
    JWT_ALGORITHM=(str, 'HS256'),
    JWT_ACCESS_TOKEN_LIFETIME=(int, 15),
    JWT_REFRESH_TOKEN_LIFETIME=(int, 7),
    AWS_REGION=(str, 'us-east-1'),
    AWS_ACCESS_KEY_ID=(str, ''),
    AWS_SECRET_ACCESS_KEY=(str, ''),
    AWS_ENDPOINT_URL=(str, ''),
    S3_BUCKET=(str, ''),
    S3_ENDPOINT=(str, ''),
    KMS_KEY_ID=(str, ''),
    USE_LOCAL_STORAGE=(bool, False),
    OPENAI_API_KEY=(str, ''),
    OPENAI_ORG_ID=(str, ''),
    OPENAI_BASE_URL=(str, 'https://api.openai.com/v1'),
    EMBEDDING_MODEL=(str, 'text-embedding-3-small'),
    CHAT_MODEL=(str, 'gpt-4o'),
    CHAT_MODEL_FALLBACK=(str, 'gpt-4o-mini'),
    LLM_FAST_MODEL=(str, ''),
    LLM_PRO_MODEL=(str, ''),
    CELERY_BROKER_URL=(str, 'redis://localhost:6379/1'),
    CELERY_RESULT_BACKEND=(str, 'django-db'),
    STRIPE_SECRET_KEY=(str, ''),
    STRIPE_PUBLISHABLE_KEY=(str, ''),
    STRIPE_WEBHOOK_SECRET=(str, ''),
    RAZORPAY_KEY_ID=(str, ''),
    RAZORPAY_KEY_SECRET=(str, ''),
    RAZORPAY_WEBHOOK_SECRET=(str, ''),
    R_SERVICE_URL=(str, 'http://localhost:8001'),
    R_SERVICE_TIMEOUT=(int, 60),
    EMAIL_HOST=(str, 'localhost'),
    EMAIL_PORT=(int, 1025),
    EMAIL_USER=(str, ''),
    EMAIL_PASSWORD=(str, ''),
    EMAIL_FROM=(str, 'B2B Micro-SaaS <noreply@localhost>'),
    SENTRY_DSN=(str, ''),
    SENTRY_ENVIRONMENT=(str, 'development'),
    CORS_ALLOWED_ORIGINS=(list, ['http://localhost:3000']),
    CSRF_TRUSTED_ORIGINS=(list, ['http://localhost:3000']),
)

# Read .env file
environ.Env.read_env(BASE_DIR / '.env')

# Security
SECRET_KEY = env('SECRET_KEY') or env('JWT_SECRET_KEY')
DEBUG = env('DEBUG')
ALLOWED_HOSTS = env('ALLOWED_HOSTS')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third party
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'django_filters',
    'drf_spectacular',
    'django_celery_results',
    'django_celery_beat',
    'django_prometheus',
    'health_check',
    'health_check.db',
    'health_check.cache',
    'health_check.storage',
    'health_check.contrib.migrations',
    'health_check.contrib.celery',
    'health_check.contrib.celery_ping',
    'health_check.contrib.redis',
    # Local apps
    'apps.accounts',
    'apps.documents',
    'apps.queries',
    'apps.analytics',
    'apps.billing',
    'apps.dataconnect',
    'apps.audit',
    'apps.health',
]

MIDDLEWARE = [
    'django_prometheus.middleware.PrometheusBeforeMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.accounts.middleware.TenantMiddleware',
    'apps.accounts.middleware.AuditMiddleware',
    'django_prometheus.middleware.PrometheusAfterMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# Database
DATABASES = {
    'default': env.db('DATABASE_URL'),
}
DATABASES['default']['CONN_MAX_AGE'] = 60
DATABASES['default']['OPTIONS'] = {
    'connect_timeout': 10,
    'options': '-c statement_timeout=30000',
}

# Redis
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': env('REDIS_URL'),
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom user model
AUTH_USER_MODEL = 'accounts.User'

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'apps.accounts.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
        'apps.accounts.permissions.BelongsToTenant',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.OrderingFilter',
        'rest_framework.filters.SearchFilter',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'EXCEPTION_HANDLER': 'apps.accounts.exceptions.custom_exception_handler',
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.UserRateThrottle',
        'rest_framework.throttling.AnonRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'user': '1000/hour',
        'anon': '100/hour',
        'login': '5/minute',
        'register': '3/hour',
        'query': '100/hour',
        'upload': '50/hour',
    },
}

# JWT / SimpleJWT
from datetime import timedelta

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=env('JWT_ACCESS_TOKEN_LIFETIME')),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=env('JWT_REFRESH_TOKEN_LIFETIME')),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': env('JWT_ALGORITHM'),
    'SIGNING_KEY': env('JWT_SECRET_KEY'),
    'VERIFYING_KEY': None,
    'AUDIENCE': None,
    'ISSUER': None,
    'JWK_URL': None,
    'LEEWAY': 0,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'USER_AUTHENTICATION_RULE': 'rest_framework_simplejwt.authentication.default_user_authentication_rule',
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
    'TOKEN_USER_CLASS': 'rest_framework_simplejwt.models.TokenUser',
    'JTI_CLAIM': 'jti',
    'SLIDING_TOKEN_REFRESH_EXP_CLAIM': 'refresh_exp',
    'SLIDING_TOKEN_LIFETIME': timedelta(minutes=5),
    'SLIDING_TOKEN_REFRESH_LIFETIME': timedelta(days=1),
}

# CORS
CORS_ALLOWED_ORIGINS = env('CORS_ALLOWED_ORIGINS')
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
    'x-tenant-id',
    'x-idempotency-key',
]

CSRF_TRUSTED_ORIGINS = env('CSRF_TRUSTED_ORIGINS')

# DRF Spectacular (OpenAPI)
SPECTACULAR_SETTINGS = {
    'TITLE': 'B2B Micro-SaaS API',
    'DESCRIPTION': 'Private AI Document & Data Analyst API',
    'VERSION': '0.1.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'SCHEMA_PATH_PREFIX': '/api/v1',
    'TAGS': [
        {'name': 'Authentication', 'description': 'Auth endpoints'},
        {'name': 'Companies', 'description': 'Multi-tenant company management'},
        {'name': 'Users', 'description': 'User management within companies'},
        {'name': 'Documents', 'description': 'Document upload and processing'},
        {'name': 'Queries', 'description': 'Question answering and retrieval'},
        {'name': 'Analytics', 'description': 'Statistical analysis and charts'},
        {'name': 'Billing', 'description': 'Subscriptions and usage'},
        {'name': 'Data Connectors', 'description': 'Read-only database connections'},
        {'name': 'Audit', 'description': 'Audit logs'},
        {'name': 'Health', 'description': 'Health checks'},
    ],
    'SECURITY': [{'BearerAuth': []}],
    'COMPONENTS': {
        'securitySchemes': {
            'BearerAuth': {
                'type': 'http',
                'scheme': 'bearer',
                'bearerFormat': 'JWT',
            }
        }
    },
}

# Celery
CELERY_BROKER_URL = env('CELERY_BROKER_URL')
CELERY_RESULT_BACKEND = env('CELERY_RESULT_BACKEND')
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_WORKER_MAX_TASKS_PER_CHILD = 100
CELERY_RESULT_EXTENDED = True
CELERY_RESULT_EXPIRES = 86400
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
CELERY_TASK_ROUTES = {
    'apps.documents.tasks.parse_document': {'queue': 'parsing'},
    'apps.documents.tasks.chunk_document': {'queue': 'processing'},
    'apps.documents.tasks.embed_chunks': {'queue': 'embedding'},
    'apps.queries.tasks.process_query': {'queue': 'queries'},
    'apps.analytics.tasks.run_analytics': {'queue': 'analytics'},
    'apps.billing.tasks.aggregate_usage': {'queue': 'billing'},
    'apps.audit.tasks.archive_audit_logs': {'queue': 'maintenance'},
}

# AWS / S3
AWS_REGION = env('AWS_REGION')
AWS_ACCESS_KEY_ID = env('AWS_ACCESS_KEY_ID') or None
AWS_SECRET_ACCESS_KEY = env('AWS_SECRET_ACCESS_KEY') or None
AWS_ENDPOINT_URL = env('AWS_ENDPOINT_URL') or None
AWS_S3_BUCKET = env('S3_BUCKET')
AWS_S3_ENDPOINT = env('S3_ENDPOINT')
AWS_KMS_KEY_ID = env('KMS_KEY_ID')
AWS_S3_VERIFY = not bool(AWS_ENDPOINT_URL)
USE_LOCAL_STORAGE = env('USE_LOCAL_STORAGE')

# S3 Presigned URL settings
PRESIGNED_URL_EXPIRY = 3600  # 1 hour
MAX_UPLOAD_SIZE = 100 * 1024 * 1024  # 100MB
ALLOWED_MIME_TYPES = [
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-excel',
    'text/csv',
    'application/csv',
]

# OpenAI / LLM
OPENAI_API_KEY = env('OPENAI_API_KEY')
OPENAI_ORG_ID = env('OPENAI_ORG_ID') or None
OPENAI_BASE_URL = env('OPENAI_BASE_URL')
EMBEDDING_MODEL = env('EMBEDDING_MODEL')
CHAT_MODEL = env('CHAT_MODEL')
CHAT_MODEL_FALLBACK = env('CHAT_MODEL_FALLBACK')
LLM_FAST_MODEL = env('LLM_FAST_MODEL') or CHAT_MODEL_FALLBACK
LLM_PRO_MODEL = env('LLM_PRO_MODEL') or CHAT_MODEL

# Embedding settings
EMBEDDING_DIMENSIONS = 1536  # text-embedding-3-small
CHUNK_SIZE = 512
CHUNK_OVERLAP = 50
MAX_CHUNKS_PER_DOCUMENT = 10000

# Retrieval settings
RETRIEVAL_TOP_K = 40
RETRIEVAL_BM25_TOP_K = 40
RETRIEVAL_FINAL_TOP_K = 8
RERANK_ENABLED = True
RERANK_MODEL = 'cross-encoder/ms-marco-MiniLM-L-6-v2'

# R Service
R_SERVICE_URL = env('R_SERVICE_URL')
R_SERVICE_TIMEOUT = env('R_SERVICE_TIMEOUT')

# Billing
STRIPE_SECRET_KEY = env('STRIPE_SECRET_KEY')
STRIPE_PUBLISHABLE_KEY = env('STRIPE_PUBLISHABLE_KEY')
STRIPE_WEBHOOK_SECRET = env('STRIPE_WEBHOOK_SECRET')
RAZORPAY_KEY_ID = env('RAZORPAY_KEY_ID')
RAZORPAY_KEY_SECRET = env('RAZORPAY_KEY_SECRET')
RAZORPAY_WEBHOOK_SECRET = env('RAZORPAY_WEBHOOK_SECRET')

# Subscription Plans (billing catalog)
SUBSCRIPTION_PLANS = {
    'free': {
        'name': 'Free',
        'price_monthly_inr': 0,
        'price_monthly_usd': 0,
        'storage_limit_bytes': 1 * 1024 * 1024 * 1024,  # 1 GB
        'query_limit_monthly': 12,
        'user_limit': 2,
        'features': ['basic_qa', 'csv_upload'],
        'stripe_price_id': '',
        'razorpay_plan_id': '',
    },
    'starter': {
        'name': 'Starter',
        'price_monthly_inr': 3000,
        'price_monthly_usd': 49,
        'storage_limit_bytes': 5 * 1024 * 1024 * 1024,  # 5 GB
        'query_limit_monthly': 500,
        'user_limit': 5,
        'features': ['basic_qa', 'csv_upload', 'pdf_upload', 'excel_upload', 'charts'],
        'stripe_price_id': 'price_starter_monthly',
        'razorpay_plan_id': 'plan_starter_monthly',
    },
    'growth': {
        'name': 'Growth',
        'price_monthly_inr': 7000,
        'price_monthly_usd': 99,
        'storage_limit_bytes': 20 * 1024 * 1024 * 1024,  # 20 GB
        'query_limit_monthly': 2500,
        'user_limit': 15,
        'features': ['basic_qa', 'csv_upload', 'pdf_upload', 'excel_upload', 'charts', 'db_connect', 'api_access'],
        'stripe_price_id': 'price_growth_monthly',
        'razorpay_plan_id': 'plan_growth_monthly',
    },
    'business': {
        'name': 'Business',
        'price_monthly_inr': 15000,
        'price_monthly_usd': 199,
        'storage_limit_bytes': 100 * 1024 * 1024 * 1024,  # 100 GB
        'query_limit_monthly': 10000,
        'user_limit': -1,  # unlimited
        'features': ['basic_qa', 'csv_upload', 'pdf_upload', 'excel_upload', 'charts', 'db_connect', 'api_access', 'sso', 'audit_logs', 'priority_support'],
        'stripe_price_id': 'price_business_monthly',
        'razorpay_plan_id': 'plan_business_monthly',
    },
}

# Email
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = env('EMAIL_HOST')
EMAIL_PORT = env('EMAIL_PORT')
EMAIL_USE_TLS = True
EMAIL_HOST_USER = env('EMAIL_USER')
EMAIL_HOST_PASSWORD = env('EMAIL_PASSWORD')
DEFAULT_FROM_EMAIL = env('EMAIL_FROM')

# Sentry
SENTRY_DSN = env('SENTRY_DSN')
SENTRY_ENVIRONMENT = env('SENTRY_ENVIRONMENT')

if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.redis import RedisIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=SENTRY_ENVIRONMENT,
        integrations=[
            DjangoIntegration(),
            CeleryIntegration(),
            RedisIntegration(),
        ],
        traces_sample_rate=0.1,
        profiles_sample_rate=0.1,
        send_default_pii=False,
    )

# Structured Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'format': '%(asctime)s %(name)s %(levelname)s %(message)s',
        },
        'console': {
            'format': '%(asctime)s %(name)s %(levelname)s %(message)s',
        },
    },
    'filters': {
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'console',
            'filters': ['require_debug_true'],
        },
        'json': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'json',
            'filters': ['require_debug_false'],
        },
    },
    'root': {
        'level': 'INFO',
        'handlers': ['console', 'json'],
    },
    'loggers': {
        'django': {'level': 'INFO', 'handlers': ['console', 'json'], 'propagate': False},
        'django.request': {'level': 'WARNING', 'handlers': ['console', 'json'], 'propagate': False},
        'apps': {'level': 'INFO', 'handlers': ['console', 'json'], 'propagate': False},
        'celery': {'level': 'INFO', 'handlers': ['console', 'json'], 'propagate': False},
        'httpx': {'level': 'WARNING', 'handlers': ['console', 'json'], 'propagate': False},
        'openai': {'level': 'WARNING', 'handlers': ['console', 'json'], 'propagate': False},
    },
}

# Structlog configuration
import structlog

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt='iso'),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

# Security headers (production)
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

# Feature flags
FEATURE_FLAGS = {
    'billing_enabled': bool(STRIPE_SECRET_KEY or RAZORPAY_KEY_ID),
    'r_analytics_enabled': bool(R_SERVICE_URL),
    'db_connectors_enabled': True,
    'api_keys_enabled': True,
    'sso_enabled': False,
    'enclave_mode': False,
}

# File upload limits
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

# Health checks
HEALTH_CHECK = {
    'DISK_USAGE_MAX': 90,
    'MEMORY_MIN': 100,
}