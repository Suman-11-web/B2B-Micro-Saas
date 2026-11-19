# Documentation

This directory contains comprehensive documentation for the B2B Micro-SaaS platform.

## Documentation Structure

### Architecture
- `architecture/README.md` - System overview and component diagram
- `architecture/data-flow.md` - Request/response flows
- `architecture/security.md` - E2E encryption implementation
- `architecture/multi-tenancy.md` - Tenant isolation strategy

### API
- `api/openapi.yaml` - OpenAPI 3.0 specification (auto-generated from Django)
- `api/authentication.md` - JWT auth flow
- `api/endpoints.md` - Endpoint reference

### Runbooks
- `runbooks/backup-recovery.md` - Data recovery procedures
- `runbooks/incident-response.md` - Incident handling checklist
- `runbooks/disaster-recovery.md` - Region failover procedures
- `runbooks/on-call.md` - On-call rotation and escalation

### Operations
- `operations/database.md` - Database maintenance
- `operations/monitoring.md` - CloudWatch dashboards and alerts
- `operations/deploying.md` - Deployment procedures

### Development
- `development/setup.md` - Local development setup
- `development/testing.md` - Testing strategy

## Auto-generated Content

The following files are auto-generated during deployment:
- `api/openapi.yaml` - Run `poetry run python manage.py spectacular --file docs/api/openapi.yaml`
- OpenAPI clients can be generated with: `npx openapi-typescript-generator -s docs/api/openapi.yaml -o apps/web/src/lib/api-client.ts`