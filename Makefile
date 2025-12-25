.PHONY: help setup start stop restart logs clean test config ingest read test-pipeline test-signals run-daily-eval test-mock

help: ## Show this help message
	@echo "Stock Analyzer - Development Commands"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

setup: ## Initial setup - start services and install dependencies
	@echo "🚀 Starting Docker services..."
	docker compose up -d
	@echo "⏳ Waiting for services to be ready..."
	sleep 5
	@echo "📦 Installing Python dependencies..."
	uv sync
	@echo "✅ Setup complete! Services running:"
	@make status

start: ## Start all Docker services
	@echo "🚀 Starting services..."
	docker compose up -d
	@make status

stop: ## Stop all Docker services (keeps data)
	@echo "🛑 Stopping services..."
	docker compose stop

restart: ## Restart all Docker services
	@echo "🔄 Restarting services..."
	docker compose restart
	@make status

status: ## Show status of all services
	@echo ""
	@docker compose ps
	@echo ""
	@echo "📊 Service URLs:"
	@echo "  Supabase Studio:  http://localhost:54323"
	@echo "  PostgREST API:    http://localhost:54321"
	@echo "  MinIO Console:    http://localhost:9001 (minioadmin/minioadmin)"
	@echo "  PostgreSQL:       localhost:5432 (postgres/postgres)"
	@echo ""

logs: ## Show logs from all services
	docker compose logs -f

logs-db: ## Show PostgreSQL logs
	docker compose logs -f postgres

logs-minio: ## Show MinIO logs
	docker compose logs -f minio

db: ## Open PostgreSQL shell
	docker compose exec postgres psql -U postgres

db-test: ## Test database connection
	@docker compose exec postgres psql -U postgres -c "SELECT 'Database is ready!' as status;"

clean: ## Stop services and remove all data (WARNING: deletes everything)
	@echo "⚠️  WARNING: This will delete all local data!"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		echo "🗑️  Removing all services and data..."; \
		docker compose down -v; \
		echo "✅ Clean complete"; \
	else \
		echo "❌ Cancelled"; \
	fi

reset: clean setup ## Clean everything and setup fresh

config: ## Test configuration loading
	python -m src.config

test: ## Run tests (when available)
	@echo "🧪 Running tests..."
	pytest

dev: ## Start development environment
	@echo "🔧 Starting development environment..."
	@make start
	@echo ""
	@echo "✅ Development environment ready!"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Check service status: make status"
	@echo "  2. View logs: make logs"
	@echo "  3. Test database: make db-test"
	@echo "  4. Open Supabase Studio: http://localhost:54323"
	@echo ""

install: ## Install Python dependencies
	uv sync

update-deps: ## Update Python dependencies
	uv lock --upgrade

# Data pipeline commands

test-mock: ## Run mock data pipeline test (no Docker/API required)
	@echo "🎭 Running mock pipeline test..."
	python scripts/test_mock_pipeline.py

test-pipeline: ## Run comprehensive pipeline test (config, R2, EODHD, ingest, read)
	@echo "🧪 Running pipeline test..."
	python scripts/test_ingest_and_read.py

ingest: ## Ingest price data for test tickers
	@echo "📥 Ingesting price data..."
	python -m src.ingest.ingest_prices

read: ## Read and display stored data
	@echo "📖 Reading stored data..."
	python -m src.reader

test-r2: ## Test R2/MinIO connection
	python -m src.storage.r2_client

test-eodhd: ## Test EODHD API connection
	python -m src.ingest.eodhd_client

# Signal computation and alerts

test-signals: ## Run signal computation and alert generation tests
	@echo "🔍 Running signal tests..."
	python scripts/test_signals.py

run-daily-eval: ## Run daily signal evaluation (main batch job)
	@echo "📊 Running daily evaluation..."
	python -m src.signals.pipeline
