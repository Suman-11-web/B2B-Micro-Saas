# B2B Micro-SaaS API

Django REST Framework API for document analysis and data querying.

## Local Development

```bash
# Install dependencies
pip install poetry
poetry install

# Set up environment
cp .env.example .env
# Edit .env with your values

# Start database
docker compose up -d postgres redis

# Run migrations
poetry run python manage.py migrate

# Seed test data
poetry run python manage.py seed

# Start development server
poetry run python manage.py runserver
```

## API Endpoints

All endpoints are under `/api/v1/`:

- **Auth**: `/auth/` - Login, register, password reset
- **Companies**: `/companies/` - Company management
- **Memberships**: `/memberships/` - Team members
- **Documents**: `/documents/` - Upload, parse, store
- **Queries**: `/queries/` - Ask questions, get answers
- **Analytics**: `/analytics-jobs/` - R-powered statistics
- **Billing**: `/invoices/`, `/billing/` - Subscriptions
- **Health**: `/health/` - Health checks

## Models

- `Company` - Tenant organization
- `User` - Multi-tenant user
- `Membership` - User's role in company
- `Subscription` / `SubscriptionPlan` - Billing
- `Document` / `Chunk` - File storage with embeddings
- `Query` / `QueryResult` - Q&A
- `AnalyticsJob` - R analysis output
- `Invoice` / `UsageSummary` - Billing records

## Testing

```bash
# Unit tests
poetry run pytest

# Coverage
poetry run pytest --cov=. --cov-report=html
```

## Security

- JWT authentication with refresh tokens
- Tenant isolation enforced at database level
- All mutations logged to `AuditLog`
- Rate limiting on all endpoints
- CORS/CSRF protection enabled