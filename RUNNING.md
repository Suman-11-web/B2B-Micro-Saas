# Running Instructions

## 🚀 Quick Run (Development Mode)

### Terminal 1: Start Frontend
```bash
cd /Users/suman/B2B\ Micro-Saas/apps/web
pnpm dev
```

### Terminal 2: Start Django API
```bash
cd /Users/suman/B2B\ Micro-Saas/services/api
python3 manage.py runserver 8000
```

### Terminal 3: Start Celery Worker (for background processing)
```bash
cd /Users/suman/B2B\ Micro-SaaS/services/api
celery -A config worker --loglevel=info
```

## 📦 Prerequisites

- **Docker** (for local dev stack): `docker compose up -d postgres redis minio localstack`
- **Python 3.12+**
- **Node.js 20.x**
- **pnpm 9.x**

If Docker is not installed, you'll need to:
1. Install PostgreSQL locally
2. Install Redis locally
3. Set up an S3-compatible service (MinIO)

## ⚙️ Environment Setup

### Backend (.env)
```bash
# Copy example
cp services/api/.env.example services/api/.env

# Required variables:
export DJANGO_SETTINGS_MODULE=config.settings
export DATABASE_URL="postgresql://b2b:b2bpassword@localhost:5432/b2b"
export REDIS_URL="redis://localhost:6379/0"
export JWT_SECRET_KEY="your-256-bit-secret-key-here"
export OPENAI_API_KEY="sk-your-openai-key"
```

### Frontend (.env.local)
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_APP_URL=http://localhost:3000
```

## 🌐 Access URLs

After starting all services:
- **Frontend**: http://localhost:3000
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/api/schema/swagger/
- **Admin**: http://localhost:8000/admin/
- **Health Check**: http://localhost:8000/health/

## 🛠️ Useful Commands

```bash
# Run migrations
cd services/api && python3 manage.py migrate

# Seed test data
python3 manage.py seed

# Create superuser
python3 manage.py createsuperuser

# Run API tests
python3 -m pytest -v --cov=.

# Run frontend tests
cd apps/web && pnpm test

# Lint and format
cd apps/web && pnpm lint && pnpm format
```

## 📊 Subscription Plans Included in Seed Data

- **Free**: $0/₹0 (1GB, 50 queries)
- **Starter**: $49/₹3,000 (5GB, 500 queries)
- **Growth**: $99/₹7,000 (20GB, 2,500 queries)
- **Business**: $199/₹15,000 (100GB, 10,000 queries)