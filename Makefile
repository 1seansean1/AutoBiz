.PHONY: install lint format typecheck test test-unit test-all clean dev dev-up dev-down dev-logs dev-health

install:
	pip install -e ".[dev]"

lint:
	ruff check autobiz tests
	black --check autobiz tests

format:
	black autobiz tests
	ruff check --fix autobiz tests

typecheck:
	mypy autobiz

test:
	pytest tests/unit -v

test-unit:
	pytest tests/unit -v -m unit

test-all:
	pytest tests -v

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache .ruff_cache

# Development environment
dev: dev-up dev-health
	@echo "✓ Development stack is ready!"
	@echo "  PostgreSQL: localhost:5433"
	@echo "  Redis: localhost:6380"
	@echo "  Langfuse: http://localhost:3000"

dev-up:
	@echo "Starting development stack..."
	@if [ ! -f .env ]; then cp .env.example .env && echo "Created .env from .env.example"; fi
	docker compose up -d
	@echo "Waiting for services to be healthy..."

dev-down:
	docker compose down

dev-logs:
	docker compose logs -f

dev-health:
	@echo "Checking service health..."
	@docker compose ps
	@echo ""
	@echo "PostgreSQL health:"
	@docker exec autobiz_postgres_test pg_isready -U autobiz_test -d autobiz_test || (echo "❌ PostgreSQL not ready" && exit 1)
	@echo "✓ PostgreSQL ready"
	@echo ""
	@echo "Redis health:"
	@docker exec autobiz_redis_test redis-cli ping || (echo "❌ Redis not ready" && exit 1)
	@echo "✓ Redis ready"
	@echo ""
	@echo "Langfuse health (may take up to 30s on first start):"
	@timeout 60 sh -c 'until docker exec autobiz_langfuse_test curl -f http://localhost:3000/api/health 2>/dev/null; do sleep 2; done' && echo "✓ Langfuse ready" || (echo "❌ Langfuse not ready" && exit 1)
