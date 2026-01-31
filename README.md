# AutoBiz: Kernel-First Agentic Business Platform

Phase 1 kernel-first agentic platform with high-reliability DTC business workflows.

## Quick Start

### Prerequisites

- Python 3.10+
- Docker Desktop with WSL2 integration enabled
- Git

### Setup (< 5 minutes)

```bash
# 1. Clone and install
git clone https://github.com/1seansean1/AutoBiz.git
cd AutoBiz
pip install -e ".[dev]"

# 2. Start development stack
make dev

# 3. Run tests
make test
```

## Development Environment

The local development stack includes:

- **PostgreSQL 16** (port 5433): Main data store
- **Redis 7** (port 6380): Hot cache for idempotency keys
- **Langfuse** (port 3000): Trace backend for observability

### Docker Desktop Setup (WSL2)

If you see "docker command not found":

1. Install [Docker Desktop for Windows](https://docs.docker.com/desktop/install/windows-install/)
2. Enable WSL2 integration:
   - Open Docker Desktop Settings
   - Go to Resources → WSL Integration
   - Enable integration for your WSL2 distro
3. Restart WSL2: `wsl --shutdown` (in PowerShell), then reopen terminal

### Environment Configuration

1. Copy `.env.example` to `.env` (done automatically by `make dev`)
2. Configure test-mode API keys in `.env`:
   - Stripe: Use `sk_test_*` keys only
   - Shopify: Development store credentials
   - Printful: Sandbox API key
   - SendGrid: Test mode key

**CRITICAL**: Never use production credentials in `.env`. All keys must be test-mode only.

## Project Structure

```
autobiz/
├── kernel/           # Reusable agent orchestration (Phase 1)
│   ├── orchestrator/
│   ├── executor/
│   ├── state/
│   ├── trace/
│   ├── hitl/
│   └── eval/
├── businesses/
│   └── dtc_tshirt/  # Phase 1 DTC T-shirt business
└── tests/
    ├── unit/
    ├── integration_internal/
    └── integration_external/
```

## Make Targets

```bash
make install      # Install package in dev mode
make dev          # Start dev stack + healthchecks
make dev-down     # Stop dev stack
make dev-logs     # Follow dev stack logs
make dev-health   # Check service health

make lint         # Run linters (black, ruff)
make format       # Auto-format code
make typecheck    # Run mypy
make test         # Run unit tests
make test-all     # Run all tests

make clean        # Remove build artifacts
```

## Testing

Tests are organized by execution environment:

- `@pytest.mark.unit`: Isolated, all deps mocked
- `@pytest.mark.integration_internal`: Real DB, mocked APIs
- `@pytest.mark.integration_external`: Real test-mode APIs

Priority levels:
- `@pytest.mark.P0`: Critical path (100% required)
- `@pytest.mark.P1`: Core functionality (≥95% LCB)
- `@pytest.mark.P2`: Enhancements (≥80% LCB)

## Architecture

AutoBiz follows a **kernel-first** design:

1. **Agent Module (Kernel)**: Reusable orchestration, enforcement, state, tracing
2. **Business Module**: Swappable business logic, tools, workflows

### System Invariants (INV-01 through INV-08)

All enforced **below the LLM**:

- Schema validation
- Permission enforcement
- Bounds (steps, time, tokens, tool calls)
- Tracing + cost attribution
- Idempotency (24h lookback)
- State versioning + replay
- HITL approvals for high-risk ops
- Deploy gates (golden suite threshold)

## Phase 1 Goals

- ✓ Kernel + 1 DTC business
- Target: ≥95% success rate on critical workflows
- Exit: 7-day production soak test

## Documentation

- `AUTOBIZ_ECOSYSTEM_PLAN_v4.6.md`: Complete specification
- `AUTOBIZ_P1_TASK_TABLE_MERGED.md`: 32-task execution plan
- `PROJECT_STATE.md`: Current implementation status

## License

Proprietary
