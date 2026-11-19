# B2B Micro-SaaS - Complete Project

## ✅ Project Status: COMPLETE

This is a production-grade multi-tenant SaaS platform ready for deployment.

## 📁 Project Structure

```
b2b-microsaas/
├── apps/
│   ├── web/                    # Next.js 14 Frontend (TypeScript, Tailwind)
│   └── docs/                   # Documentation site
├── services/
│   ├── api/                    # Django 5 + DRF API
│   ├── worker/                 # Celery Workers
│   ├── rservice/               # R Plumber REST Service
│   └── llmproxy/               # Optional vLLM Proxy
├── infra/
│   └── terraform/              # Infrastructure as Code
├── docs/
│   ├── architecture/            # System architecture
│   ├── runbooks/                # Operations runbooks
│   └── api/                     # OpenAPI spec
├── scripts/
└── tests/
```

## 🚀 Quick Start (Local Development)

### Prerequisites
- Docker & Docker Compose
- Python 3.12
- Node.js 20.x
- pnpm 9.x

### 1. Install Dependencies

```bash
cd /Users/suman/B2B\ Micro-Saas

# Frontend
cd apps/web
pnpm install
cd ../..

# Backend
cd services/api
pip install -r requirements.txt
cd ../..
```

### 2. Start Infrastructure

```bash
# Start local services (PostgreSQL, Redis, MinIO)
docker compose up -d postgres redis minio localstack

# Wait for services to be ready (~10 seconds)
```

### 3. Run Migrations

```bash
cd services/api

# Set environment
export DJANGO_SETTINGS_MODULE=config.settings
export DATABASE_URL="postgresql://b2b:b2bpassword@localhost:5432/b2b"
export REDIS_URL="redis://localhost:6379/0"
export JWT_SECRET_KEY="dev-secret-key-for-local-dev-only"
export OPENAI_API_KEY="sk-your-key-here"
export S3_ENDPOINT="http://localhost:9000"
export AWS_ACCESS_KEY_ID="minioadmin"
export AWS_SECRET_ACCESS_KEY="minioadmin"
export S3_BUCKET="b2b-test"

# Apply migrations
python manage.py migrate

# Seed initial data
python seed.py
```

### 4. Create Superuser

```bash
export DJANGO_SUPERUSER_EMAIL="admin@example.com"
export DJANGO_SUPERUSER_PASSWORD="your-secure-password"
python manage.py createsuperuser --no-input
```

### 5. Start Servers

```bash
# Terminal 1: Django API
cd services/api
python manage.py runserver 8000

# Terminal 2: Celery Worker
python manage.py celery -A config worker --loglevel=info

# Terminal 3: Frontend
cd apps/web
pnpm dev
```

### 6. Access the Application

- **Frontend**: http://localhost:3000
- **API**: http://localhost:8000
- **Admin**: http://localhost:8000/admin/
- **Health Check**: http://localhost:8000/health/

## 🛠️ Available Tasks

```bash
make dev          # Start full stack
make test         # Run all tests
make lint         # Run linters
make migrate      # Run migrations
make seed         # Seed database
make db:reset     # Reset database
```

## 🔐 Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection | postgresql://b2b:b2bpassword@localhost:5432/b2b |
| `REDIS_URL` | Redis connection | redis://localhost:6379/0 |
| `JWT_SECRET_KEY` | JWT signing key | (required) |
| `OPENAI_API_KEY` | OpenAI API key | (required) |
| `S3_ENDPOINT` | S3/MinIO endpoint | http://localhost:9000 |
| `AWS_ACCESS_KEY_ID` | S3 access key | minioadmin |
| `AWS_SECRET_ACCESS_KEY` | S3 secret key | minioadmin |
| `S3_BUCKET` | Document bucket | b2b-test |

## 🏗️ Architecture

The platform uses:
- **Multi-tenancy**: Per-company isolation with tenant middleware
- **Security**: Defense-in-depth encryption (TLS, SSE-KMS, envelope encryption)
- **Vector Search**: pgvector with HNSW indexes
- **Hybrid Retrieval**: Vector similarity + BM25
- **LLM Orchestration**: OpenAI with function calling and grounding
- **Statistics**: R Plumber service for analysis
- **Billing**: Stripe (USD) + Razorpay (INR)

## 📊 Subscription Plans

| Tier | Price (USD) | Price (INR) | Storage | Queries |
|------|-------------|-------------|---------|---------|
| Free | $0 | ₹0 | 1 GB | 50 |
| Starter | $49 | ₹3,000 | 5 GB | 500 |
| Growth | $99 | ₹7,000 | 20 GB | 2,500 |
| Business | $199 | ₹15,000 | 100 GB | 10,000 |

## 🧪 Testing

```bash
# API tests
cd services/api
python -m pytest -v --cov=.

# Frontend tests
cd apps/web
pnpm test
```

## 🚀 Production Deployment

```bash
# 1. Set production secrets in AWS Secrets Manager
# 2. Run Terraform
cd infra/terraform
terraform init
terraform workspace select prod
terraform apply -var-file=envs/prod.tfvars

# 3. Deploy via GitHub Actions
# Push to main branch triggers automatic deployment
```

## 📚 Documentation

- [README.md](./README.md) - Project overview
- [docs/architecture/README.md](./docs/architecture/README.md) - Architecture
- [docs/runbooks/backup-recovery.md](./docs/runbooks/backup-recovery.md) - DR procedures
- [docs/api/openapi.yaml](./docs/api/openapi.yaml) - API spec (generated)

## 🆘 Support

For issues or questions, refer to:
- GitHub Issues
- Runbooks in `docs/runbooks/`
- Admin interface at `/admin/`

---

🤖 Generated with [Claude Code](https://claude.com/claude-code)