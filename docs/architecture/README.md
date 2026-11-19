# Architecture Overview

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Client Applications                           │
├─────────────────────────────────────────────────────────────────────┤
│  Web Browser (Next.js)  │  Mobile App (React Native)  │  API Clients  │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    API Gateway / Load Balancer                        │
│                   (AWS ALB / Nginx / Cloudflare)                    │
│           - TLS termination                                              │
│           - WAF rules                                                   │
│           - Rate limiting                                               │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ HTTPS (mutual TLS for workers)
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         Django API                                  │
│                    (ECS Fargate Service)                            │
│  - Authentication (JWT)                                               │
│  - Tenant resolution                                                  │
│  - ORM with tenant scoping                                            │
│  - OpenAPI schema generation                                            │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
       ┌────────────────────────┼────────────────────────┐
       │                        │                        │
       ▼                        ▼                        ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   Documents     │  │  Queries        │  │ Billing         │
│   Service       │  │   Service       │  │   Service       │
│  (ECS Fargate)  │  │  (ECS Fargate)  │  │  (ECS Fargate)  │
└────────┬────────┘  └────────┬────────┘  └────────┬────────┘
         │                      │                      │
         │ S3 Events           │ Redis (CELERY)      │ Stripe/Razorpay
         ▼                      ▼                      ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   Celery        │  │  OpenAI LLM     │  │  Webhook Queue  │
│   Workers       │  │  API            │  │                 │
│  - Parse/PDF    │  │  - Embeddings   │  │                 │
│  - Embed/Vect.  │  │  - Chat         │  │                 │
│  - Process Qs   │  │                 │  │                 │
└────────┬────────┘  └─────────────────┘  └─────────────────┘
         │
         ▼
┌─────────────────┐
│  R Service      │
│  (Plumber)      │
│  - Statistical   │
│  - Charts       │
└─────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                         Data Layer                                  │
├─────────────────────────────────────────────────────────────────────┤
│  PostgreSQL (RDS)  │  Redis (ElastiCache)  │  S3 (MinIO/LocalStack)│
│  - pgvector        │  - Celery broker      │  - SSE-KMS            │
│  - Multi-AZ        │  - Cache              │  - Versioning         │
└─────────────────────────────────────────────────────────────────────┘
```

## Multi-Tenant Isolation Strategy

### 1. Database Level (Row-Level Security)
- Every tenant-scoped model has a `company` foreign key
- Middleware resolves company from subdomain or header
- QuerySets filter by `company=request.company`
- Automated tests verify cross-tenant 404

### 2. Application Level
- JWT includes `company_id` claim
- Middleware enforces tenant resolution early
- All operations require tenant context

### 3. Storage Level
- S3 buckets organized by company: `{company_id}/{document_id}/`
- IAM policies restrict access to company-prefixed paths
- KMS CMKs for envelope encryption

## Data Flow: Upload

```
1. User POST /documents/initiate-upload/
   ↓
2. API generates presigned S3 URL + document record (status=queued)
   ↓
3. Browser uploads directly to S3 with presigned URL
   ↓
4. User POST /documents/{id}/confirm-upload/
   ↓
5. Celery "parse" task: download → validate → extract
   ↓
6. Celery "chunk" task: split into 512-token chunks
   ↓
7. Celery "embed" task: generate embeddings, store in pgvector
   ↓
8. Document status = READY
```

## Data Flow: Query

```
1. User POST /queries/
   ↓
2. API creates Query (status=pending)
   ↓
3. Celery "process_query" task:
   a. Embed question text
   b. Vector search (pgvector HNSW) + BM25 hybrid
   c. Assemble top-8 chunks as context
   d. Call OpenAI with function calling
   e. Verify grounding (citations map to retrieved chunks)
   ↓
4. Create QueryResult with answer + citations + chart_spec
   ↓
5. Stream response to client via SSE
```

## Security Implementation

### Encryption
- **In Transit**: TLS 1.3, HSTS, mTLS for inter-service
- **At Rest**: S3 SSE-KMS, RDS encryption, EBS encryption
- **Data Keys**: Per-tenant Data Encryption Keys (DEK) wrapped by KMS

### Secrets Management
- AWS Secrets Manager for DB creds
- IAM roles for task execution (no static credentials)
- Env vars contain only ARNs, not actual secrets

### File Handling
- Magic-number validation (not just extension)
- Max file size: 100MB
- Virus scanning hook for ClamAV
- Files deleted immediately after processing

## Scaling Strategy

### Horizontal Scaling
- ECS Fargate services auto-scale based on CPU/memory
- Celery workers scale based on queue depth
- Database read replicas for analytics queries

### Vertical Scaling
- pgvector index tuning
- Redis LRU eviction policies
- Object size limits for embeddings

### Cost Optimization
- S3 lifecycle: 90 days standard → Glacier
- Fargate spot instances for batch jobs
- Redis cache for hot queries