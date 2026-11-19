# B2B Micro-SaaS - Private AI Document & Data Analyst

A production-grade multi-tenant SaaS platform for businesses to analyze documents and data using AI.

## 🚀 Overview

Businesses have massive amounts of data trapped in PDFs, Excel sheets, and SQL databases. This platform provides a secure environment for uploading company documents, connecting read-only databases, and asking questions in plain English - receiving accurate answers, charts, and summaries.

**Key Features:**
- 📄 **Document Processing**: PDF, Excel, CSV upload with intelligent chunking
- 🗄️ **Database Connectors**: Read-only PostgreSQL, MySQL integration
- 💬 **AI Q&A**: Natural language questions with grounded answers
- 📊 **Statistical Analysis**: R-powered charts and insights
- 🔒 **Enterprise Security**: End-to-end encryption, audit logs, compliance-ready

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Front-End (Next.js)                      │
│                    (Tailwind CSS, TypeScript)                   │
└───────────────────────────────┬─────────────────────────────────┘
                              │
┌──────────────────────────────▼─────────────────────────────────┐
│                          API Gateway                           │
│                      (Fastly/Cloudflare)                       │
└───────────────────────────────┬─────────────────────────────────┘
                              │
┌──────────────────────────────▼─────────────────────────────────┐
│                     Django REST Framework                      │
│                       (Python 3.12)                            │
├────────────────────────────────────────────────────────────────┤
│  Authentication | Documents | Queries | Analytics | Billing  │
└───────────────────────────────┬─────────────────────────────────┘
                              │
        ┌───────────────┬───────┼───────┬───────────────┐
        ▼               ▼       ▼       ▼               ▼
    ┌─────────┐  ┌─────────┐┌───────┐┌─────────┐  ┌─────────┐
    │  S3     │  │  R      ││Celery ││ Stripe  ││Database │
    │ (Files) │  │(Stats)  ││Workers││(Billing)││(Connect)│
    └─────────┘  └─────────┘└───────┘└─────────┘  └─────────┘
```

## 💰 Pricing Tiers

| Tier | Price (USD) | Price (INR) | Storage | Queries | Features |
|------|-------------|-------------|---------|---------|----------|
| Free | $0 | ₹0 | 1 GB | 50 | Basic QA, CSV upload |
| Starter | $49 | ₹3,000 | 5 GB | 500 | PDF, Excel, charts |
| Growth | $99 | ₹7,000 | 20 GB | 2,500 | DB connect, API |
| Business | $199 | ₹15,000 | 100 GB | 10,000 | SSO, Audit logs |

## 🛠️ Tech Stack

- **Frontend**: Next.js 14, TypeScript, Tailwind CSS, shadcn/ui
- **Backend**: Django 5, DRF, Celery
- **Database**: PostgreSQL 16 with pgvector
- **Storage**: AWS S3 (SSE-KMS)
- **Infra**: AWS ECS Fargate, RDS, ElastiCache
- **Auth**: JWT (SimpleJWT), Refresh tokens
- **Billing**: Stripe (USD), Razorpay (INR)

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.12
- Node.js 20.x
- pnpm 9.x

### Development Setup

```bash
# Clone and enter directory
cd /Users/suman/B2B\ Micro-Saas

# Install dependencies
make install:all

# Start local services
docker compose up -d postgres redis localstack minio

# Wait for services to be ready
sleep 5

# Run database migrations
make migrate

# Seed test data
make seed

# Start development servers
make dev
```

The API will be available at http://localhost:8000
The frontend will be available at http://localhost:3000

## 📁 Project Structure

```
b2b-microsaas/
├── apps/
│   ├── web/                    # Next.js frontend
│   └── docs/                   # Documentation site
├── services/
│   ├── api/                    # Django REST Framework API
│   ├── worker/                 # Celery workers
│   ├── rservice/               # R Plumber REST service
│   └── llmproxy/               # Optional vLLM proxy
├── infra/
│   └── terraform/              # Infrastructure as Code
├── docs/
│   ├── architecture/            # System architecture
│   ├── runbooks/                # Operations runbooks
│   └── api/                     # OpenAPI spec
├── scripts/
└── tests/
```

## 🧪 Testing

```bash
# Unit tests
make test-api    # Django tests

# Frontend tests
make test-web    # Jest tests

# End-to-end tests
make test-e2e    # Playwright tests

# Security scan
make security
```

## 🛡️ Security

- TLS 1.3 + mTLS between services
- S3 SSE-KMS encryption for files
- Per-tenant envelope encryption
- JWT with short-lived access tokens
- CSRF/XSS protection
- Rate limiting
- Immutable audit logs (S3 Object Lock)

## 📊 Monitoring

- **Logs**: structlog JSON → CloudWatch
- **Metrics**: OpenTelemetry → CloudWatch EMF
- **Tracing**: W3C traceparent propagation
- **Alerting**: CloudWatch Alarms → SNS/Slack

## 🔄 CI/CD

GitHub Actions pipeline:
1. Lint & typecheck
2. Unit tests
3. Security scan (Trivy, Bandit, npm audit, gitleaks, checkov)
4. Build Docker images
5. Blue/green deploy to ECS

## 📚 Documentation

- [API Schema](./docs/api/openapi.yaml)
- [Architecture](./docs/architecture/README.md)
- [Runbooks](./docs/runbooks/)
- [Deployment](./docs/deployment.md)

## 🚀 Deployment

```bash
# Deploy to dev
make deploy-dev

# Deploy to staging
make deploy-staging

# Deploy to production (requires approval)
make deploy-prod
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linters
5. Submit a pull request

## 📄 License

Proprietary - All rights reserved by B2B Micro-Saas.

## 🤖 Generated with [Claude Code](https://claude.com/claude-code)