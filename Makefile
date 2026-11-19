# B2B Micro-SaaS Makefile
# Usage: make <target>

.PHONY: help dev up down logs ps shell-api shell-web test lint format typecheck migrate seed smoke clean

# Default target
help:
	@echo "B2B Micro-SaaS - Available targets:"
	@echo ""
	@echo "  dev          Start full development stack (docker + frontend)"
	@echo "  up           Start docker services only"
	@echo "  down         Stop docker services"
	@echo "  logs         Follow docker logs"
	@echo "  ps           Show running containers"
	@echo "  shell-api    Open shell in API container"
	@echo "  shell-web    Open shell in Web container"
	@echo "  test         Run all tests"
	@echo "  lint         Run linters"
	@echo "  format       Format code"
	@echo "  typecheck    Run type checkers"
	@echo "  migrate      Run database migrations"
	@echo "  seed         Seed database with test data"
	@echo "  smoke        Run smoke tests"
	@echo "  clean        Clean up docker volumes and build artifacts"
	@echo ""

# Development
dev:
	docker compose up -d
	@echo "Waiting for services to be ready..."
	@sleep 5
	cd apps/web && pnpm dev

up:
	docker compose up -d

down:
	docker compose down

down-v:
	docker compose down -v

logs:
	docker compose logs -f

ps:
	docker compose ps

shell-api:
	docker compose exec api bash

shell-web:
	docker compose exec web bash

shell-db:
	docker compose exec postgres psql -U b2b -d b2b

shell-redis:
	docker compose exec redis redis-cli

# Code Quality
lint:
	cd apps/web && pnpm lint
	cd services/api && python -m ruff check .
	cd services/api && python -m black --check .
	cd services/api && python -m mypy .

format:
	cd apps/web && pnpm format
	cd services/api && python -m ruff check --fix .
	cd services/api && python -m black .

typecheck:
	cd apps/web && pnpm typecheck
	cd services/api && python -m mypy .

# Testing
test:
	cd apps/web && pnpm test
	cd services/api && python -m pytest -v

test-api:
	cd services/api && python -m pytest -v

test-web:
	cd apps/web && pnpm test

test-e2e:
	cd tests && pnpm test

# Database
migrate:
	cd services/api && python manage.py migrate

makemigrations:
	cd services/api && python manage.py makemigrations

seed:
	cd services/api && python manage.py seed

reset-db:
	docker compose down -v postgres
	docker compose up -d postgres
	@sleep 5
	make migrate
	make seed

# Workers
worker:
	cd services/api && python manage.py celery -A config worker --loglevel=info

worker-beat:
	cd services/api && python manage.py celery -A config beat --loglevel=info

flower:
	cd services/api && python -m celery -A config flower

# Smoke Tests
smoke:
	bash scripts/smoke.sh

# Cleanup
clean:
	docker compose down -v
	rm -rf apps/web/.next apps/web/node_modules
	rm -rf services/api/.pytest_cache services/api/__pycache__
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "node_modules" -exec rm -rf {} + 2>/dev/null || true

# Install dependencies
install:
	pnpm install
	cd services/api && pip install -e .

# Build
build:
	cd apps/web && pnpm build
	docker compose build

# Security
security:
	cd services/api && python -m bandit -r . -f json -o bandit-report.json || true
	cd services/api && python -m pip-audit || true
	cd apps/web && pnpm audit || true
	cd infra/terraform && checkov -d . || true
	cd infra/terraform && tfsec . || true

# Documentation
docs:
	cd apps/docs && pnpm build

# Deploy (requires proper AWS config)
deploy-dev:
	cd infra/terraform && terraform workspace select dev && terraform apply -var-file=envs/dev.tfvars

deploy-staging:
	cd infra/terraform && terraform workspace select staging && terraform apply -var-file=envs/staging.tfvars

deploy-prod:
	cd infra/terraform && terraform workspace select prod && terraform apply -var-file=envs/prod.tfvars

# Terraform
tf-init:
	cd infra/terraform && terraform init

tf-plan:
	cd infra/terraform && terraform plan

tf-fmt:
	cd infra/terraform && terraform fmt -recursive

tf-validate:
	cd infra/terraform && terraform validate