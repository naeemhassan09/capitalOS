COMPOSE = docker compose -f docker-compose.dev.yml
BACKEND = $(COMPOSE) exec -T backend
BACKEND_RUN = $(COMPOSE) run --rm backend

.DEFAULT_GOAL := help
.PHONY: help setup dev up stop down logs ps migrate migration seed seed-real \
        test test-backend lint format shell db-shell backup restore prod-build security-scan

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

setup: ## First-time setup: create .env if missing
	@test -f .env || (cp .env.example .env && echo "Created .env — edit secrets before production use")
	@echo "Run 'make dev' to start the stack."

dev: setup ## Start the full dev stack (postgres + backend + frontend)
	$(COMPOSE) up --build

up: ## Start the stack in the background
	$(COMPOSE) up -d --build

stop: ## Stop containers (keep data)
	$(COMPOSE) stop

down: ## Stop and remove containers (keep volumes)
	$(COMPOSE) down

logs: ## Tail logs
	$(COMPOSE) logs -f --tail=100

ps: ## Show container status
	$(COMPOSE) ps

migration: ## Autogenerate a migration: make migration m="message"
	$(BACKEND_RUN) alembic revision --autogenerate -m "$(m)"

migrate: ## Apply migrations
	$(BACKEND_RUN) alembic upgrade head

seed: ## Load anonymised demo data
	$(BACKEND_RUN) python -m scripts.seed_demo

seed-real: ## Load your real spreadsheet figures (local only)
	$(BACKEND_RUN) python -m scripts.seed_real

test: test-backend ## Run all tests

test-backend: ## Run backend tests
	$(BACKEND_RUN) pytest

lint: ## Lint backend
	$(BACKEND_RUN) ruff check app && $(BACKEND_RUN) mypy app

format: ## Format backend
	$(BACKEND_RUN) ruff format app && $(BACKEND_RUN) ruff check --fix app

shell: ## Open a backend shell
	$(COMPOSE) run --rm backend bash

db-shell: ## Open a psql shell
	$(COMPOSE) exec postgres psql -U $${POSTGRES_USER:-capitalos} -d $${POSTGRES_DB:-capitalos}

backup: ## Run a database backup
	bash deploy/scripts/backup.sh

restore: ## Restore from a backup file: make restore f=backup.sql.gz.enc
	bash deploy/scripts/restore.sh "$(f)"

prod-build: ## Build production images
	docker compose -f docker-compose.yml build

security-scan: ## Run dependency + secret scans (requires trivy/gitleaks locally)
	@echo "See .github/workflows for the canonical scans."
