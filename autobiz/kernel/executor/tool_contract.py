"""ToolContract: Tool specification with schema and controls.

Part of P1-TASK-06: Tool Registry + Schema Validation
Requirements: INV-01, P1-R01, P1-R18
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ToolContract(BaseModel):
    """Tool specification with schema and controls.

    Canonical definition per AUTOBIZ_ECOSYSTEM_PLAN_v4.6.md §4.3.
    Enforces INV-01 (schema validation) before tool execution.
    """

    model_config = ConfigDict(frozen=False)  # Allow modification for registry updates

    name: str
    version: str  # SemVer string
    input_schema: dict[str, Any]  # JSON Schema
    output_schema: dict[str, Any]  # JSON Schema
    side_effect_level: Literal["READ", "SOFT_WRITE", "HARD_WRITE", "FINANCIAL"]
    timeout_seconds: int

    # Optional fields
    idempotency_key_template: str | None = None
    rate_limit_rpm: int | None = None

    # Redaction controls (§2 Trace Redaction Policy)
    sensitive_input_fields: list[str] = Field(default_factory=list)  # JSONPath expressions
    sensitive_output_fields: list[str] = Field(default_factory=list)  # JSONPath expressions
    trace_allowlist_input: list[str] | None = None  # If set, ONLY these fields traced
    trace_allowlist_output: list[str] | None = None  # If set, ONLY these fields traced

    # External idempotency (for FINANCIAL tools - §2 External Idempotency)
    external_idempotency_header: str | None = None  # e.g., "Idempotency-Key" for Stripe
    external_idempotency_template: str | None = None  # Template for external key
