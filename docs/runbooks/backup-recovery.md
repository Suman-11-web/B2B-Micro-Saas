# Backup & Recovery Runbook

## Overview

This runbook describes procedures for backing up and recovering the B2B Micro-SaaS platform.

## Recovery Point Objectives (RPO)

| Component | RPO | Backup Frequency |
|-----------|-----|------------------|
| PostgreSQL (RDS) | 15 minutes | Automated snapshots + continuous logs |
| Redis | 60 minutes | RDB snapshots |
| S3 (Documents) | 24 hours | Cross-region replication |
| Audit Logs | 0 minutes | S3 Object Lock immutability |

## Recovery Time Objectives (RTO)

| Scenario | RTO |
|----------|-----|
| Single AZ failure | 30 minutes |
| Multi-AZ DB failure | 1 hour |
| Region failure | 4 hours |
| Data corruption | 2 hours |

## Backup Procedures

### PostgreSQL (Automated)

RDS provides automated backups:
- **Snapshots**: Daily automated snapshots (1 snapshot/day)
- **Transaction logs**: Continuous WAL logs (15-min retention)
- **Point-in-time recovery**: Up to 35 days of recovery window
- **Cross-region backup**: Enabled via backup retention

**Manual Snapshot (for major releases):**
```bash
aws rds create-db-snapshot \
  --db-instance-identifier b2b-prod-postgres \
  --db-snapshot-identifier b2b-prod-postgres-$(date +%Y%m%d-%H%M%S)
```

### S3 Backups

Documents bucket has:
- Cross-region replication enabled
- Versioning enabled
- MFA delete enabled (requires physical key)
- Lifecycle: 30 days in STANDARD, 90 days in GLACIER

**Cross-region copy:**
```bash
aws s3 sync s3://b2b-prod-documents s3://b2b-prod-documents-backup \
  --source-region us-east-1 \
  --region us-west-2
```

### Redis Backups

ElastiCache provides:
- Daily snapshots (15-min point-in-time recovery)
- Backup retention: 7-35 days

## Recovery Procedures

### Scenario 1: Database Restore from Snapshot

```bash
# 1. Create new DB instance from snapshot
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier b2b-recovered-postgres \
  --db-snapshot-identifier b2b-prod-postgres-20240101

# 2. Update DNS/Route53 to point to new instance
# 3. Verify connectivity
# 4. Run migrations if needed
poetry run python manage.py migrate --fake-initial

# 5. Update RDS endpoints in Secrets Manager
```

### Scenario 2: S3 Data Recovery

```bash
# 1. List available versions
aws s3api list-object-versions --bucket b2b-prod-documents

# 2. Restore specific version or from cross-region backup
aws s3 cp s3://b2b-prod-documents-backup/ s3://b2b-prod-documents/ --recursive

# 3. Verify file integrity
python -c "
import hashlib
for f in files:
    with open(f, 'rb') as fp:
        h = hashlib.sha256(fp.read()).hexdigest()
        print(f'{f}: {h}')
"
```

### Scenario 3: Region Failover

```bash
# 1. Promote read replica in DR region
aws rds promote-read-replica --db-instance-identifier b2b-dr-postgres

# 2. Update CloudFront origin to point to DR region
aws cloudfront update-distribution --id $DISTRIBUTION_ID ...

# 3. Update RDS endpoint in Secrets Manager
aws secretsmanager update-secret \
  --secret-id b2b-prod/rds-endpoint \
  --secret-string '{"host": "b2b-dr-postgres.cluster-xxx.us-west-2.rds.amazonaws.com"}'

# 4. Verify all services are operational
```

## DR Drill Checklist (Quarterly)

- [ ] Simulate primary region failure
- [ ] Execute DR procedures
- [ ] Verify data integrity
- [ ] Measure RTO/RPO
- [ ] Document lessons learned
- [ ] Update runbooks if needed

## Escalation

| Severity | Response Time | Contact |
|----------|---------------|---------|
| P1 - Data Loss | 15 min | Engineering Lead |
| P2 - Service Down | 30 min | On-call Engineer |
| P3 - Performance | 2 hours | Support Team |

## Post-Recovery Verification

1. **Database**: Run `SELECT COUNT(*) FROM documents;` compare with backup manifest
2. **Documents**: Verify checksums match
3. **API**: Test critical endpoints (login, upload, query)
4. **Billing**: Verify subscription status intact
5. **Audit**: Verify log integrity