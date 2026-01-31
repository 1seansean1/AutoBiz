"""P1-H09: Hygiene test for local development stack.

Verifies that `make dev` brings up all services with healthy status.
This is a P0 hygiene test that must pass before any other tests run.
"""

import os
import subprocess

import pytest


@pytest.mark.unit
@pytest.mark.P0
@pytest.mark.deterministic
@pytest.mark.oracle_state_change
def test_h09_dev_stack_healthchecks() -> None:
    """P1-H09: Verify dev stack services are healthy.

    Test ID: P1-H09
    Requirements: P1-ENTRY-01
    Acceptance: All services (PostgreSQL, Redis, Langfuse) report healthy
    Oracle: Docker healthcheck status + direct connection tests
    """
    # Check if running in CI - skip if not in local dev
    if os.getenv("CI") == "true":
        pytest.skip("Dev stack test only runs locally, not in CI")

    # Verify docker compose is running
    result = subprocess.run(
        ["docker", "compose", "ps", "--format", "json"],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        pytest.fail("Docker Compose is not running. Run 'make dev' first.")

    # Parse service status
    import json
    services = [json.loads(line) for line in result.stdout.strip().split("\n") if line]

    required_services = {"autobiz_postgres_test", "autobiz_redis_test", "autobiz_langfuse_test"}
    running_services = {svc["Name"] for svc in services if svc.get("State") == "running"}

    missing = required_services - running_services
    if missing:
        pytest.fail(f"Required services not running: {missing}. Run 'make dev'")

    # Verify PostgreSQL health
    pg_result = subprocess.run(
        ["docker", "exec", "autobiz_postgres_test", "pg_isready", "-U", "autobiz_test", "-d", "autobiz_test"],
        capture_output=True,
        check=False,
    )
    assert pg_result.returncode == 0, "PostgreSQL health check failed"

    # Verify Redis health
    redis_result = subprocess.run(
        ["docker", "exec", "autobiz_redis_test", "redis-cli", "ping"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert redis_result.returncode == 0, "Redis health check failed"
    assert "PONG" in redis_result.stdout, "Redis did not respond with PONG"

    # Verify Langfuse health (allow some startup time)
    langfuse_result = subprocess.run(
        ["docker", "exec", "autobiz_langfuse_test", "curl", "-f", "http://localhost:3000/api/health"],
        capture_output=True,
        check=False,
        timeout=10,
    )
    assert langfuse_result.returncode == 0, "Langfuse health check failed"


@pytest.mark.unit
@pytest.mark.P0
@pytest.mark.deterministic
def test_h09_env_file_exists() -> None:
    """P1-H09: Verify .env file exists for local dev."""
    if os.getenv("CI") == "true":
        pytest.skip("Local dev environment check only")

    assert os.path.exists(".env"), (
        ".env file missing. Copy .env.example to .env and configure"
    )


@pytest.mark.unit
@pytest.mark.P0
@pytest.mark.deterministic
def test_h09_database_name_contains_test() -> None:
    """P1-H09: Verify DATABASE_URL contains '_test' for safety.

    Test ID: P1-H09
    Requirements: P1-RH01 (Test Environment Safety)
    Acceptance: DATABASE_URL must contain '_test' substring
    Oracle: String matching on environment variable
    """
    db_url = os.getenv("DATABASE_URL", "")

    if not db_url:
        pytest.skip("DATABASE_URL not set - run 'make dev' first")

    assert "_test" in db_url, (
        f"DATABASE_URL must contain '_test' for safety. Got: {db_url}"
    )
