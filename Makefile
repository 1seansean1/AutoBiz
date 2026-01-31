.PHONY: install lint format typecheck test test-unit test-all clean

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
