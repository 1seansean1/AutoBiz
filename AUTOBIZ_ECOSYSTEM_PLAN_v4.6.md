# AutoBiz: Kernel-First Agentic Business Platform (v4.6)
---

# PART I: GLOBAL CONTEXT

---

## 1. Executive Summary

AutoBiz is a **kernel-first agentic platform** that separates:
- **Agent Module (Kernel)**: Reusable orchestration, enforcement, state, tracing
- **Business Module**: Swappable business logic, tools, workflows, scopes

Evolution proceeds in **three phases with objective gates**:
- **Phase 1**: Kernel + 1 DTC business, critical workflows ≥95% success
- **Phase 2**: Broad reliability + spawn new business module (also ≥95%), crystallization v0
- **Phase 3**: Learning loop in production, autonomous spawning, portfolio controls

---

## 2. System Invariants

These invariants hold for **every agent run**, enforced below the LLM. Non-negotiable across all phases.

| ID | Invariant | Enforcement | Evidence | Test Coverage |
|----|-----------|-------------|----------|---------------|
| INV-01 | **Schema-valid** | Tool calls validated against JSON Schema before execution | Invalid calls rejected + traced | P1-T01, P1-T02, P1-T01-NEG-* |
| INV-02 | **Permission-valid** | Allowlists + data caps enforced per tool | Forbidden ops blocked + traced | P1-T03, P1-T04, P1-T02-NEG-* |
| INV-03 | **Bounded** | Step/time/token/tool caps with hard termination | Violations logged | P1-T05, P1-T06, P1-T07, P1-T08 |
| INV-04 | **Traced** | Every run emits correlation ID, steps, tool calls, state diffs, cost | Transcript persisted | P1-T09, P1-T10, P1-T35 |
| INV-05 | **Idempotent** | Side effects deduplicated via idempotency keys with 24-hour lookback window | Receipts stored; key TTL enforced | P1-T11, P1-T12, P1-H07, P1-H08, P1-T05-NEG-* |
| INV-06 | **Durable** | State versioned + replayable from transcript | State patches persisted | P1-T14, P1-T15 |
| INV-07 | **HITL-gated** | High-risk ops require approval before execution | Approve/deny logged | P1-T16, P1-T17, P1-T07-NEG-* |
| INV-08 | **Eval-gated** | Deploys blocked if golden suite < threshold | CI gate enforced | P1-T18 |

**Guardrails are executor enforcement, not a peer component.** Policies are non-bypassable below the LLM.

### Idempotency Key Specification (INV-05)

| Attribute | Value | Rationale |
|-----------|-------|-----------|
| **Format** | `{tenant_id}:{tool_name}:{tool_version}:{principal_id}:{params_fingerprint}` | Deterministic; no temporal component in key |
| **Fingerprint algorithm** | SHA-256 of RFC 8785 canonicalized JSON params | Deterministic serialization for nested structures |
| **Lookback window** | 24 hours from `first_seen_at` | Balance between safety and storage |
| **Storage** | Redis (hot) + PostgreSQL (cold) | Fast lookup + durable audit |
| **TTL** | 25 hours in Redis; permanent in PostgreSQL | 1-hour buffer; cold storage for disputes |
| **Collision behavior** | Return cached result; log duplicate attempt | No re-execution within window |
| **Metadata stored** | `first_seen_at`, `result`, `execution_id`, `ttl_expires_at` | Enables debugging without polluting key |

**Canonicalization Rules:**

```python
import hashlib

def canonicalize_params_rfc8785(params: dict) -> bytes:
    """RFC 8785 JSON Canonicalization Scheme (JCS)."""
    # MUST use a proven RFC 8785 implementation; do not approximate with json.dumps().
    # Canonical form is UTF-8 bytes produced by the JCS algorithm (number formatting + unicode handling included).
    return JCS.canonicalize(params)  # placeholder: swap in a real RFC 8785/JCS library for your language

def compute_fingerprint(params: dict) -> str:
    """Deterministic fingerprint for idempotency key."""
    canonical_bytes = canonicalize_params_rfc8785(params)
    return hashlib.sha256(canonical_bytes).hexdigest()[:32]  # 128 bits
```

### External Idempotency Specification (FINANCIAL Tools)

For FINANCIAL tools calling external payment providers, both internal and external idempotency must be tracked.

| Attribute | Value | Rationale |
|-----------|-------|-----------|
| **Internal key** | Per INV-05 specification above | AutoBiz deduplication |
| **External key** | Provider-specific header (e.g., `Idempotency-Key` for Stripe) | Provider-side deduplication |
| **Key linkage** | Receipt stores both `internal_idempotency_key` and `external_idempotency_key` | Full audit trail |
| **External key format** | `autobiz:{internal_key_sha256}` | Fixed-length; avoids provider key length limits |


**External key derivation:** `internal_key_sha256 = sha256(internal_key).hexdigest()[:32]` (128-bit hex prefix). Store both the internal key and external key in the receipt for audit + replay.

```python
class ExternalIdempotencyConfig(BaseModel):
    """Configuration for external provider idempotency."""
    header_name: str                      # e.g., "Idempotency-Key"
    key_template: str = "autobiz:{internal_key_sha256}"

    # Derived
    hash_algo: Literal["SHA256"] = "SHA256"  # external key uses sha256(internal_key)
    
    # Provider-specific
    provider: Literal["STRIPE", "SQUARE", "PAYPAL", "OTHER"]
    max_key_length: int = 255             # Stripe limit
    key_reuse_window_hours: int = 24      # Must match provider's window


class FinancialReceipt(BaseModel):
    """Receipt for FINANCIAL tool execution with dual idempotency."""
    receipt_id: str
    tool_name: str
    
    # Internal tracking
    internal_idempotency_key: str
    execution_id: str
    
    # External tracking
    external_idempotency_key: str
    external_provider: str
    external_transaction_id: Optional[str]  # Provider's ID (e.g., Stripe charge ID)
    
    # Result
    status: Literal["PENDING", "COMPLETED", "FAILED", "REFUNDED"]
    amount_cents: int
    currency: str
    
    # Timestamps
    created_at: datetime
    completed_at: Optional[datetime]
```

### Trace Redaction Policy (INV-04)

**Architecture:** Schema-allowlist-first, scanners as defense-in-depth.

#### ToolContract Sensitive Field Annotations

```python
class ToolContract(BaseModel):
    """Tool specification with schema and controls.
    
    Note: Showing redaction-relevant fields only.
    See §4.3 ToolContract for canonical full definition.
    """
    name: str
    version: SemVer
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    side_effect_level: Literal["READ", "SOFT_WRITE", "HARD_WRITE", "FINANCIAL"]
    idempotency_key_template: Optional[str]
    timeout_seconds: int
    rate_limit_rpm: Optional[int]
    
    # Redaction controls (primary focus of this section)
    sensitive_input_fields: List[str] = []      # JSONPath expressions
    sensitive_output_fields: List[str] = []     # JSONPath expressions
    trace_allowlist_input: Optional[List[str]]  # If set, ONLY these fields traced
    trace_allowlist_output: Optional[List[str]] # If set, ONLY these fields traced
    
    # Additional fields in canonical definition (§4.3):
    # - external_idempotency_header
    # - external_idempotency_template
```

#### Redaction Pipeline (Revised)

```
Tool Input/Output
    ↓
1. Schema allowlist filter (keep only declared safe fields)
    ↓
2. Sensitive field redactor (mask fields marked sensitive)
    ↓
3. Secret scanner [defense-in-depth] (reject if found; alert)
    ↓
4. Credit card scanner [defense-in-depth] (reject if found; alert)
    ↓
5. PII scanner [defense-in-depth] (mask/hash; alert on detection)
    ↓
Persisted to trace store
```

#### Scanner Specifications (Defense-in-Depth Only)

| Data Type | Detection | Action | Alert |
|-----------|-----------|--------|-------|
| **API Secret** | Entropy analysis + prefix match (`sk_`, `api_`, `secret_`, `ghp_`, `xox`) | Reject trace write | P1 |
| **Credit Card** | Luhn-valid 13-19 digit sequences | Reject trace write | P1 |
| **PII - Email** | RFC 5322 compliant parser | Mask → `j***@***.com` | P2 |
| **PII - Phone** | E.164 format or `+` prefix with 10-15 digits | Mask → `***-***-1234` | P2 |
| **PII - SSN** | `\d{3}-\d{2}-\d{4}` pattern | Reject trace write | P1 |

**Note:** Scanner detections indicate allowlist misconfiguration; alert triggers review of ToolContract annotations.

#### Retention Policy

| Tier | Duration | Storage | Access |
|------|----------|---------|--------|
| **Hot** | 7 days | PostgreSQL | Ops + Dev |
| **Warm** | 90 days | S3 (compressed) | Ops only |
| **Cold** | 2 years | S3 Glacier (WORM) | Legal/Compliance only |
| **Delete** | After 2 years | — | Tombstone + integrity proof |

#### Access Controls

| Role | Can View | Can Export | Can Delete |
|------|----------|------------|------------|
| Developer | Hot (redacted) | No | No |
| Ops | Hot + Warm (redacted) | Yes (redacted) | No |
| Compliance | All tiers | Yes (full) | Tombstone only* |

*Deletion creates tombstone record with hash of deleted content; original content immutable in WORM storage.

#### Audit Log Integrity

| Mechanism | Implementation | Verification |
|-----------|----------------|--------------|
| **Hash chain** | Each log entry includes `prev_hash = SHA-256(prev_entry)` | Continuous on write |
| **WORM storage** | S3 Object Lock (Compliance mode) for Cold tier | Immutable by design |
| **Signed roots** | Daily Merkle root signed with HSM key | Verifiable externally |
| **Integrity check** | Nightly batch verification of chain continuity | Alert on break |
| **On-demand audit** | Full chain verification tool for compliance | Manual trigger |

---

## 3. Test Environment Safety

All test suites enforce strict isolation from production systems. **Hygiene tests are P0** and must pass before any other tests execute.

| Guard | Enforcement | Detection |
|-------|-------------|-----------|
| **API test mode** | Environment variable `ENV=test` required | Credential prefix check (`sk_test_*`, sandbox URLs) |
| **No real customer contact** | Email allowlist: `*@test.example.com` | Regex validation before send |
| **Database isolation** | Connection string must contain `_test` | Startup check; abort if missing |
| **Webhook signature validation** | All inbound webhooks cryptographically verified | Reject unsigned/invalid |
| **Namespace isolation** | All entities prefixed with `test_` namespace | Query filter enforced |

**CI Pipeline Order:**
1. Hygiene tests (P0-H*) — abort pipeline if any fail
2. Unit tests
3. Integration tests (P0, P1, P2)
4. Golden suite

---

## 4. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AGENT MODULE (KERNEL)                                │
│  Reusable across all businesses; owned by platform team                      │
│                                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │ Orchestrator│  │ Tool        │  │ State       │  │ Trace +     │        │
│  │ (LangGraph) │  │ Executor    │  │ Manager     │  │ Cost        │        │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │ Bounds +    │  │ Idempotency │  │ HITL        │  │ Eval        │        │
│  │ Loop Kill   │  │ + Receipts  │  │ Approvals   │  │ Gate        │        │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘        │
├─────────────────────────────────────────────────────────────────────────────┤
│                         BUSINESS MODULE (Swappable)                          │
│  One per business; defined by BusinessConfig                                 │
│                                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │ Storefront  │  │ Payments    │  │ Fulfillment │  │ Customer    │        │
│  │ (Shopify)   │  │ (Stripe)    │  │ (POD API)   │  │ Comms       │        │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Core Schema Definitions

### 5.1 BusinessConfig

```python
class BusinessConfig(BaseModel):
    """What 'spawn a business' produces."""
    id: str
    name: str
    version: SemVer
    workflows: List[WorkflowDef]
    tools: Dict[str, ToolContract]
    scopes: Dict[str, PermissionScope]
    bounds: BoundsConfig
    hitl_rules: Dict[str, HITLRule]
    eval_suite_ref: str
    state: Literal["DRAFT", "VALIDATING", "SHADOW", "ACTIVE", "PAUSED", "SUNSET"]
```

### 5.2 WorkflowDef (Expressive)

```python
class WorkflowDef(BaseModel):
    """Workflow definition supporting branching, sagas, and async waits."""
    id: str
    name: str
    trigger: TriggerDef
    steps: List[WorkflowStep]             # Ordered steps (not just tool names)
    pass_criteria: str
    allowed_failure_modes: List[str]
    timeout_seconds: int = 300
    
class ParallelCompensationStrategy(str, Enum):
    COMPENSATE_SUCCEEDED = "COMPENSATE_SUCCEEDED"  # Only compensate branches that succeeded
    REVERSE_ALL = "REVERSE_ALL"                    # Compensate all branches regardless
    MANUAL = "MANUAL"                              # Escalate to HITL for decision


class AsyncFailurePolicy(str, Enum):
    IGNORE = "IGNORE"                # Workflow continues; async failure logged only
    COMPENSATE_ALL = "COMPENSATE_ALL"  # Trigger full saga rollback
    COMPENSATE_FAILED = "COMPENSATE_FAILED"  # Compensate only the failed branch


class WorkflowStep(BaseModel):
    """Single step with branching, retry, and compensation support."""
    id: str
    type: Literal["TOOL", "BRANCH", "PARALLEL", "WAIT", "COMPENSATION"]
    
    # For TOOL type
    tool_name: Optional[str]
    tool_input_mapping: Optional[Dict[str, str]]  # JSONPath from state
    retry_policy: Optional[RetryPolicy]
    compensation: Optional[CompensationDef]       # Saga rollback
    
    # For BRANCH type
    condition: Optional[ConditionExpr]            # Typed DSL, not str
    if_true: Optional[str]                        # Step ID to jump to
    if_false: Optional[str]
    
    # For PARALLEL type
    parallel_steps: Optional[List[str]]           # Step IDs to run concurrently
    join_policy: Optional[Literal["ALL", "ANY", "N_OF_M"]]
    join_n: Optional[int]                         # For N_OF_M
    parallel_compensation_strategy: ParallelCompensationStrategy = ParallelCompensationStrategy.COMPENSATE_SUCCEEDED
    async_failure_policy: AsyncFailurePolicy = AsyncFailurePolicy.COMPENSATE_ALL
    
    # For WAIT type
    wait_for: Optional[WaitCondition]
    wait_timeout_seconds: Optional[int]
    on_timeout: Optional[str]                     # Step ID on timeout
    
    # HITL
    hitl_required: bool = False
    hitl_condition: Optional[ConditionExpr]       # Typed DSL
    
    # Next step
    next_step: Optional[str]                      # Step ID (None = terminal)


class RetryPolicy(BaseModel):
    """Retry configuration per step."""
    max_attempts: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 60.0
    backoff_multiplier: float = 2.0
    jitter: bool = True                           # Prevent thundering herd
    retryable_errors: List[str]                   # Error types to retry


class CompensationDef(BaseModel):
    """Saga compensation (rollback) definition."""
    tool_name: str
    tool_input_mapping: Dict[str, str]
    compensation_order: int                       # Reverse execution order
    idempotent: bool = True                       # Compensation must be idempotent
    max_attempts: int = 3                         # Retry compensation on failure
    on_compensation_failure: Literal["ALERT", "ESCALATE", "ABORT"] = "ESCALATE"


class WaitCondition(BaseModel):
    """Async wait for external signal."""
    type: Literal["WEBHOOK", "POLL", "TIMER", "MANUAL"]
    event_type: Optional[str]                     # For WEBHOOK
    poll_tool: Optional[str]                      # For POLL
    poll_interval_seconds: Optional[int]
    poll_condition: Optional[str]                 # Predicate to check
    duration_seconds: Optional[int]               # For TIMER
```

**Example: Parallel Fulfillment with Compensation**

```yaml
workflow:
  id: parallel_fulfill_workflow
  steps:
    - id: split_order
      type: TOOL
      tool_name: splitOrderByWarehouse
      next_step: parallel_fulfill
      
    - id: parallel_fulfill
      type: PARALLEL
      parallel_steps: [fulfill_west, fulfill_east]
      join_policy: ALL
      parallel_compensation_strategy: COMPENSATE_SUCCEEDED
      async_failure_policy: COMPENSATE_ALL
      next_step: merge_tracking
      
    - id: fulfill_west
      type: TOOL
      tool_name: createFulfillment
      tool_input_mapping: {"warehouse": "WEST", "items": "$.split.west_items"}
      compensation:
        tool_name: cancelFulfillment
        tool_input_mapping: {"fulfillment_id": "$.fulfill_west.id"}
        compensation_order: 1
        
    - id: fulfill_east
      type: TOOL
      tool_name: createFulfillment
      tool_input_mapping: {"warehouse": "EAST", "items": "$.split.east_items"}
      compensation:
        tool_name: cancelFulfillment
        tool_input_mapping: {"fulfillment_id": "$.fulfill_east.id"}
        compensation_order: 2
```

### 5.5 Condition Expression Language

Workflow conditions use a **custom restricted DSL** with infix notation that is **compiled to JSONLogic AST** for evaluation. This provides human-readable syntax with safe, deterministic execution.

#### Grammar

```
expr       := literal | path | comparison | logical | function
literal    := string | number | boolean | null
path       := "$." identifier ("." identifier | "[" index "]")*
comparison := expr ("==" | "!=" | "<" | "<=" | ">" | ">=") expr
logical    := expr ("AND" | "OR") expr | "NOT" expr
function   := func_name "(" expr ("," expr)* ")"
```

#### Allowed Functions

| Function | Signature | Description | Determinism |
|----------|-----------|-------------|-------------|
| `len` | `len(array) → int` | Array length | Pure |
| `contains` | `contains(array, value) → bool` | Array membership | Pure |
| `startswith` | `startswith(string, prefix) → bool` | String prefix | Pure |
| `endswith` | `endswith(string, suffix) → bool` | String suffix | Pure |
| `now` | `now() → datetime` | Current timestamp | Injected clock* |
| `duration_seconds` | `duration_seconds(dt1, dt2) → int` | Time difference | Pure |

*`now()` uses an **injected clock** for deterministic replay. The clock value is recorded in traces at workflow start and replayed during replay tests.

**Explicitly Forbidden:** `eval`, `exec`, `import`, regex operations, file I/O, network calls.

#### Schema Definition

```python
class ConditionExpr(BaseModel):
    """Validated condition expression - custom DSL compiled to JSONLogic AST."""
    raw: str                                      # Original infix expression
    parsed: Dict[str, Any]                        # Compiled JSONLogic AST
    referenced_paths: List[str]                   # State paths used
    clock_dependent: bool = False                 # True if uses now()
    
    @validator('raw')
    def validate_expression(cls, v):
        ast = parse_condition(v)  # Raises on invalid syntax
        validate_no_forbidden_functions(ast)
        return v
    
    @classmethod
    def compile(cls, raw: str, state_schema: Dict) -> 'ConditionExpr':
        """Compile with state schema validation."""
        parsed = parse_condition(raw)
        paths = extract_referenced_paths(parsed)
        clock_dependent = uses_now_function(parsed)
        
        for path in paths:
            if not path_exists_in_schema(path, state_schema):
                raise CompileError(f"Path '{path}' not found in state schema")
            
        return cls(raw=raw, parsed=parsed, referenced_paths=paths, clock_dependent=clock_dependent)
    
    def evaluate(self, state: Dict, clock: datetime) -> Any:
        """Evaluate with injected clock for deterministic replay."""
        context = {"state": state, "now": clock}
        return jsonlogic_evaluate(self.parsed, context)
```

#### Example Conditions

```python
# Simple comparison
ConditionExpr.compile("$.order.amount <= 500", order_schema)

# Logical combination
ConditionExpr.compile(
    "$.order.refund_eligible AND $.order.amount <= 500 AND NOT $.order.disputed",
    order_schema
)

# Function usage
ConditionExpr.compile(
    "duration_seconds($.order.created_at, now()) < 86400",
    order_schema
)
```

### 4.3 ToolContract

```python
class ToolContract(BaseModel):
    """Tool specification with schema and controls.
    
    Canonical definition - includes all fields.
    See §2 Trace Redaction Policy for redaction field usage.
    """
    name: str
    version: SemVer
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    side_effect_level: Literal["READ", "SOFT_WRITE", "HARD_WRITE", "FINANCIAL"]
    idempotency_key_template: Optional[str]
    timeout_seconds: int
    rate_limit_rpm: Optional[int]
    
    # Redaction controls (see §2 Trace Redaction Policy)
    sensitive_input_fields: List[str] = []      # JSONPath expressions
    sensitive_output_fields: List[str] = []     # JSONPath expressions
    trace_allowlist_input: Optional[List[str]]  # If set, ONLY these fields traced
    trace_allowlist_output: Optional[List[str]] # If set, ONLY these fields traced
    
    # External idempotency (for FINANCIAL tools - see §2 External Idempotency)
    external_idempotency_header: Optional[str]  # e.g., "Idempotency-Key" for Stripe
    external_idempotency_template: Optional[str] # Template for external key
```

### 4.4 Supporting Types

```python
class PermissionScope(BaseModel):
    tool_name: str
    allowed_operations: List[str]
    data_cap_bytes: Optional[int]
    network_allowlist: Optional[List[str]]

class BoundsConfig(BaseModel):
    max_steps_per_run: int = 50
    max_time_seconds: int = 300
    max_tokens_per_run: int = 50000
    max_tool_calls_per_run: int = 100
    max_tool_calls_per_type: Dict[str, int] = {}

class HITLRule(BaseModel):
    trigger: str
    condition: Optional[ConditionExpr]         # Typed DSL (validated JsonPath + ops)
    timeout_seconds: int = 3600
    timeout_action: Literal["FAIL", "ESCALATE"]  # AUTO_APPROVE removed from enum
    approval_channel: str
    required_approvers: int = 1
    escalation_chain: Optional[List[str]] = None  # For ESCALATE action


class HITLRulePermissive(HITLRule):
    """Extended rule for non-FINANCIAL tools only."""
    timeout_action: Literal["FAIL", "ESCALATE", "AUTO_APPROVE"]


def validate_business_config(config: BusinessConfig) -> List[str]:
    """Compile-time validation. Returns list of errors."""
    errors = []
    
    for tool_name, tool in config.tools.items():
        if tool.side_effect_level == "FINANCIAL":
            # FINANCIAL tools MUST have HITL rule
            if tool_name not in config.hitl_rules:
                errors.append(f"FINANCIAL tool '{tool_name}' requires explicit HITLRule")
                continue
            
            rule = config.hitl_rules[tool_name]
            
            # FINANCIAL tools CANNOT have AUTO_APPROVE
            if hasattr(rule, 'timeout_action') and rule.timeout_action == "AUTO_APPROVE":
                errors.append(f"FINANCIAL tool '{tool_name}' cannot have timeout_action=AUTO_APPROVE")
            
            # FINANCIAL tools MUST have escalation chain if ESCALATE configured
            if rule.timeout_action == "ESCALATE" and not rule.escalation_chain:
                errors.append(f"FINANCIAL tool '{tool_name}' with ESCALATE requires escalation_chain")
    
    return errors


# Compile check integration
class BusinessConfigValidator:
    """Static validator run at deploy time."""
    
    checks = [
        ("tool_closure", validate_tool_closure),
        ("bounds_present", validate_bounds_present),
        ("scopes_present", validate_scopes_present),
        ("financial_hitl", validate_business_config),  # Enforced
    ]
    
    @classmethod
    def validate(cls, config: BusinessConfig) -> tuple[bool, List[str]]:
        all_errors = []
        for name, check in cls.checks:
            errors = check(config)
            all_errors.extend([f"[{name}] {e}" for e in errors])
        return len(all_errors) == 0, all_errors
```

---

## 6. Orchestration Mode Selection

| Side Effect Level | Orchestration Mode | HITL Default |
|-------------------|-------------------|--------------|
| **READ** | Reactive (ReAct) | No |
| **SOFT_WRITE** | Reactive (ReAct) | No |
| **HARD_WRITE** | Plan→Execute | Configurable |
| **FINANCIAL** | Plan→Execute | Always |

### 6.1 Shadow Mode Specification

Shadow mode enables validation of new logic without production side effects.

```python
class ShadowExecutionStrategy(str, Enum):
    MOCK_EXTERNALS = "MOCK_EXTERNALS"    # External calls return mocked responses
    DRY_RUN = "DRY_RUN"                  # External calls logged but not executed
    CLONED_STATE = "CLONED_STATE"        # Full state clone; external calls to sandbox


class ShadowResultDisposition(str, Enum):
    DISCARD = "DISCARD"                  # Results discarded after comparison
    PERSIST_SHADOW = "PERSIST_SHADOW"    # Results stored in shadow namespace
    EMIT_TRACE = "EMIT_TRACE"            # Results emitted to separate trace stream


class ShadowModeSpec(BaseModel):
    """Configuration for shadow execution."""
    
    execution_strategy: ShadowExecutionStrategy
    result_disposition: ShadowResultDisposition = ShadowResultDisposition.EMIT_TRACE
    
    # Read handling
    read_passthrough: bool = True         # Allow real reads (for fresh data)
    read_cache_ttl_seconds: int = 300     # Cache reads to reduce load
    
    # Write handling
    write_interception: Literal["MOCK_SUCCESS", "MOCK_FROM_FIXTURE", "RECORD_ONLY"]
    write_fixture_path: Optional[str]     # For MOCK_FROM_FIXTURE
    
    # Cost/rate limit handling
    billing_mode: Literal["SHADOW_BUDGET", "PRODUCTION_BUDGET", "EXEMPT"]
    rate_limit_mode: Literal["SHARED", "SEPARATE", "EXEMPT"]
    shadow_rate_limit_rpm: Optional[int]  # For SEPARATE mode
    
    # Comparison
    compare_with_production: bool = True
    divergence_threshold: float = 0.1     # Alert if >10% of runs diverge
    divergence_alert_channel: str = "shadow-alerts"


class ShadowRunResult(BaseModel):
    """Result of a shadow execution."""
    shadow_run_id: str
    production_run_id: Optional[str]      # If comparison enabled
    
    shadow_outcome: WorkflowOutcome
    production_outcome: Optional[WorkflowOutcome]
    
    diverged: bool
    divergence_details: Optional[Dict[str, Any]]  # Field-level diff
    
    disposition: ShadowResultDisposition
    stored_at: Optional[str]              # Location if persisted
```

#### Shadow Mode by Phase

| Phase | Default Strategy | Disposition | Comparison |
|-------|------------------|-------------|------------|
| P2 | MOCK_EXTERNALS | EMIT_TRACE | Required before promotion |
| P3 | CLONED_STATE | PERSIST_SHADOW | Required + automated |

---

## 7. Sandbox Tiers

| Tier | Isolation | Use Case | Phase |
|------|-----------|----------|-------|
| **STANDARD** | Docker + resource limits | READ, SOFT_WRITE | 1+ |
| **HARDENED** | seccomp + AppArmor + RO FS | HARD_WRITE, FINANCIAL | 1+ |
| **VM** | Firecracker/gVisor | Untrusted external code | 3 |

---

## 8. Compile Checks

| Check ID | Check | Validates | Failure Action | Phase |
|----------|-------|-----------|----------------|-------|
| CC-01 | **Tool closure** | All workflow tools exist with valid schemas | Block deploy | 1+ |
| CC-02 | **Bounds present** | BoundsConfig has non-zero limits | Block deploy | 1+ |
| CC-03 | **Scopes present** | Every tool has PermissionScope entry | Block deploy | 1+ |
| CC-04 | **FINANCIAL HITL** | FINANCIAL tools have HITL rule, no AUTO_APPROVE | Block deploy | 1+ |

SMT proofs (deadlock freedom, termination) deferred to post-Phase 3.

---

## 9. Priority Definitions

| Priority | Meaning | Deploy Gate | Failure Tolerance |
|----------|---------|-------------|-------------------|
| **P0** | Critical path; system unusable without | Must pass 100% | Zero |
| **P1** | Core functionality; significant degradation | Must pass ≥95% | ≤5% |
| **P2** | Enhancement; minor impact if broken | Should pass ≥80% | ≤20% |

---

## 10. Metric Measurement Specification

**Problem:** "≥95% success" is meaningless without denominator, window, and failure taxonomy.

### 10.1 Measurement Definitions

| Term | Definition |
|------|------------|
| **Run** | Single workflow execution from trigger to terminal state |
| **Trigger** | Event that initiates a run (webhook, schedule, manual) |
| **SUCCESS** | Run reaches terminal success state matching `pass_criteria` |
| **EXPECTED_FAILURE** | Run terminates in a declared `allowed_failure_modes` state **with correct error code** and **no unsafe side effects** (correct-but-not-complete) |
| **UNEXPECTED_FAILURE** | Any other failure (bug, invariant break, missing compensation, wrong terminal state, unsafe side effects) |

### 10.2 Metrics

```
Completion Rate  = SUCCESS / Total Runs
Correctness Rate = (SUCCESS + EXPECTED_FAILURE) / Total Runs

Where:
- Total Runs = Runs that reached a terminal state within the measurement window
```

**Phase gates use Correctness Rate** (LCB in CI; rolling-window in production). **Completion Rate is tracked separately** to avoid hiding chronic non-completion behind “expected failures”.
### 10.3 Measurement Windows

| Context | Window | Rationale |
|---------|--------|-----------|
| **Eval suite (CI)** | Per suite execution | Deterministic; same inputs |
| **Phase gate** | Rolling 7-day production | Sufficient volume; smooths anomalies |
| **Alerting** | Rolling 1-hour | Fast detection |
| **SLO reporting** | Calendar month | Business alignment |

### 10.4 Allowed Failure Taxonomy

| Category | Example | Classified As | Counts Against **Correctness Rate** | Counts Against **Completion Rate** |
|----------|---------|---------------|-------------------------------------|------------------------------------|
| **External unavailable** | Stripe 503, Printful timeout | EXPECTED_FAILURE (if retries/compensation applied and terminal error code is correct) | No | Yes |
| **Invalid input** | Malformed webhook, missing required field | EXPECTED_FAILURE | No | Yes |
| **Business rule rejection** | Refund outside policy window | EXPECTED_FAILURE | No | Yes |
| **Rate limited** | Too many requests | EXPECTED_FAILURE (if correct backoff + terminal outcome) | No | Yes |
| **HITL timeout** | Approval not received in SLA | UNEXPECTED_FAILURE (unless explicitly allowed for that workflow) | Yes | Yes |
| **Invariant violation** | Bounds exceeded, loop detected | UNEXPECTED_FAILURE | Yes | Yes |
| **Unexpected exception** | Unhandled error, crash | UNEXPECTED_FAILURE | Yes | Yes |
| **Wrong outcome** | Incorrect tool called, bad output | UNEXPECTED_FAILURE | Yes | Yes |
### 10.5 Example Calculation

```
Phase 1 Gate Check (7-day window):
- Total runs: 1,000
- Successful: 920
- Expected failures (external unavailable, recovered): 50
- Expected failures (invalid input): 20
- Unexpected failures: 10

Success Rate = (920 + 50 + 20) / 1,000 = 99.0% ✓ Passes ≥95%
```

---

## 11. Event Processing Model

**Problem:** Idempotency keys alone don't handle out-of-order, delayed, or duplicate webhooks.

### 11.1 Event Challenges

| Challenge | Example | Impact |
|-----------|---------|--------|
| **Out-of-order** | `payment.failed` arrives before `payment.created` | State machine breaks |
| **Duplicates** | Webhook retried by provider | Double processing |
| **Delayed** | Fulfillment webhook arrives 30min late | Stale state decisions |
| **Missing** | Webhook lost in transit | State never updates |

### 11.2 Event Processing Pipeline

```
Webhook Received
    ↓
1. Signature Validation (reject unsigned)
    ↓
2. Deduplication (idempotency key check)
    ↓
3. Event Store (append to log with sequence number)
    ↓
4. Ordering Gate (hold if predecessor missing)
    ↓
5. State Machine (apply if preconditions met)
    ↓
6. Reconciliation Queue (if ordering timeout)
```



### 11.2a Event Store Specification (Phase 1 Minimum)

**Purpose:** Immutable, append-only record of inbound events (pre-state) used for ordering, replay, and reconciliation.

| Field | Type | Notes |
|------|------|------|
| `event_id` | UUID | Internal primary key |
| `tenant_id` | string | Tenant scope for all queries |
| `source` | enum | `STRIPE` / `SHOPIFY` / `PRINTFUL` / `INTERNAL` |
| `source_event_id` | string | Provider event ID (unique per source+tenant) |
| `event_type` | string | Provider type (`charge.refunded`, `order.updated`, …) |
| `received_at` | RFC3339 | Ingest timestamp |
| `seq` | string/int | Ordering key (provider seq if available; else derived logical clock) |
| `predecessor_source_event_id` | string? | Optional causal predecessor for ordering gate |
| `signature_valid` | bool | Set after signature validation |
| `payload_json` | jsonb | Raw payload (immutable) |
| `payload_sha256` | hex | Hash of canonical raw payload bytes |
| `processing_status` | enum | `RECEIVED` / `HELD_ORDERING` / `APPLIED` / `RECONCILE_QUEUED` / `REJECTED` |
| `run_id` | UUID? | Linked agent run (if applied) |
| `correlation_id` | string? | Linked trace correlation id |
| `applied_at` | RFC3339? | Timestamp when state machine applied event |

**Retention:** Store `payload_json` for audit/replay (default 90 days) and store `payload_sha256` + metadata for long-term dedup + provenance.

**Separation of concerns:** Event Store = inbound event ledger; Trace Store = per-run step/tool transcript; State Store = current state + version history.

**Indexing (recommended):** All queries are tenant-scoped; use composite indexes to keep ordering/dedup scans bounded.

```sql
CREATE INDEX idx_events_tenant_source
  ON event_store(tenant_id, source, source_event_id);

CREATE INDEX idx_events_tenant_status
  ON event_store(tenant_id, processing_status, received_at);
```



### 11.3 Ordering Guarantees

| Strategy | Implementation | Trade-off |
|----------|----------------|-----------|
| **Sequence numbers** | Provider-assigned (e.g., Stripe event ID) | Requires provider support |
| **Logical clock** | Lamport timestamp on state | Complexity |
| **Causal ordering** | Wait for predecessor events | Latency |
| **Eventual consistency** | Reconciliation job repairs | Temporary inconsistency |

**AutoBiz Default:** Causal ordering with 60-second timeout → reconciliation queue.

#### Post-Timeout Event Handling

When an event is held waiting for a predecessor and the 60-second timeout expires:

| Step | Action | Rationale |
|------|--------|-----------|
| 1 | **Mark event as "timeout_released"** | Track that ordering was incomplete |
| 2 | **Check state-machine preconditions** | Verify event is safe to apply |
| 3a | If preconditions met → **Apply with warning** | Event is valid despite missing predecessor |
| 3b | If preconditions violated → **Route to reconciliation** | Unsafe to apply; needs repair |
| 4 | **Alert on timeout** | Ops visibility into ordering failures |

```python
class TimeoutReleasedEvent(BaseModel):
    """Event released from ordering gate due to timeout."""
    event_id: str
    event_type: str
    held_for_seconds: int                 # How long in gate
    missing_predecessor: Optional[str]    # Expected predecessor ID
    
    # Resolution
    preconditions_checked: List[str]
    preconditions_passed: bool
    resolution: Literal["APPLIED_WITH_WARNING", "ROUTED_TO_RECONCILIATION", "MANUAL_REVIEW"]
    
    # For APPLIED_WITH_WARNING
    state_before: Optional[Dict[str, Any]]
    state_after: Optional[Dict[str, Any]]
    
    # For ROUTED_TO_RECONCILIATION
    reconciliation_job_id: Optional[str]
    expected_repair_by: Optional[datetime]


# State-machine precondition examples
PRECONDITIONS = {
    "order.fulfilled": lambda state: state.get("status") in ["paid", "processing"],
    "payment.refunded": lambda state: state.get("status") == "captured",
    "fulfillment.shipped": lambda state: state.get("status") == "created",
}
```

**Design Decision:** We do NOT apply events that violate state-machine preconditions, even after timeout. This prevents the "succeeded before created" problem from corrupting state. Instead, the reconciliation job repairs from the source of truth.

### 11.4 Reconciliation Jobs

| Job | Frequency | Action |
|-----|-----------|--------|
| **Order sync** | Every 5 min | Compare local orders vs Shopify; repair drift |
| **Payment sync** | Every 5 min | Compare local payments vs Stripe; repair drift |
| **Fulfillment sync** | Every 15 min | Compare local fulfillments vs Printful; repair drift |
| **Stuck event recovery** | Every 1 min | Process events held in ordering gate > 60s |

### 11.5 State Repair Protocol

```python
class StateRepair(BaseModel):
    """Repair action when drift detected."""
    entity_type: str                      # "order", "payment", "fulfillment"
    entity_id: str
    local_state: Dict[str, Any]
    remote_state: Dict[str, Any]
    drift_detected_at: datetime
    repair_action: Literal["UPDATE_LOCAL", "UPDATE_REMOTE", "MANUAL_REVIEW"]
    repair_applied_at: Optional[datetime]
    requires_hitl: bool                   # True if financial or irreversible
```

### 11.6 Backpressure and Circuit Breaker Configuration

#### Queue Bounds

```python
class QueueConfig(BaseModel):
    """Configuration for bounded queues with overflow handling."""
    
    max_depth: int
    overflow_strategy: Literal["DROP_OLDEST", "REJECT_NEW", "SPILL_TO_DISK"]
    
    # Alerting
    warning_threshold: float = 0.7        # Alert at 70% capacity
    critical_threshold: float = 0.9       # Page at 90% capacity
    
    # Spill configuration (for SPILL_TO_DISK)
    spill_path: Optional[str]
    spill_max_size_mb: Optional[int]


# Queue configurations by type
QUEUE_CONFIGS = {
    "event_ordering_gate": QueueConfig(
        max_depth=10000,
        overflow_strategy="REJECT_NEW",  # Backpressure to webhook source
        warning_threshold=0.7,
        critical_threshold=0.9
    ),
    "reconciliation_queue": QueueConfig(
        max_depth=5000,
        overflow_strategy="SPILL_TO_DISK",
        spill_path="/var/spool/autobiz/reconciliation",
        spill_max_size_mb=1000
    ),
    "hitl_pending_approvals": QueueConfig(
        max_depth=1000,
        overflow_strategy="REJECT_NEW",  # Force escalation
        warning_threshold=0.5,           # Earlier warning for human queue
        critical_threshold=0.8
    ),
}
```

#### Circuit Breaker Configuration

```python
class CircuitBreakerConfig(BaseModel):
    """Configuration for circuit breakers on external dependencies."""
    
    # Failure detection
    failure_threshold: int = 5            # Failures before opening
    failure_window_seconds: int = 60      # Window for counting failures
    
    # Circuit states
    open_duration_seconds: int = 30       # How long to stay open
    half_open_max_calls: int = 3          # Calls allowed in half-open
    
    # Recovery
    success_threshold: int = 2            # Successes to close from half-open
    
    # State persistence
    persist_state: bool = True            # Survive restarts
    state_ttl_seconds: int = 300          # Default to half-open after TTL


class DriftCircuitBreaker(BaseModel):
    """Circuit breaker for reconciliation drift detection."""
    
    # Drift rate thresholds
    drift_rate_threshold: float = 0.1     # Open if >10% of records drifted
    drift_window_seconds: int = 300       # Measurement window
    
    # Actions
    on_open: Literal["PAUSE_RECONCILIATION", "ALERT_ONLY", "REDUCE_FREQUENCY"]
    pause_duration_seconds: int = 600     # For PAUSE_RECONCILIATION
    reduced_frequency_multiplier: float = 0.1  # For REDUCE_FREQUENCY
    
    # Alerting
    alert_channel: str = "reconciliation-alerts"
    require_manual_reset: bool = False    # If true, needs human to close


# Circuit breaker configurations by dependency
CIRCUIT_BREAKERS = {
    "shopify": CircuitBreakerConfig(
        failure_threshold=5,
        failure_window_seconds=60,
        open_duration_seconds=30,
        persist_state=True
    ),
    "stripe": CircuitBreakerConfig(
        failure_threshold=3,              # Lower threshold for payments
        failure_window_seconds=30,
        open_duration_seconds=60,         # Longer open for payments
        persist_state=True
    ),
    "printful": CircuitBreakerConfig(
        failure_threshold=10,             # Higher tolerance for fulfillment
        failure_window_seconds=120,
        open_duration_seconds=120,
        persist_state=True
    ),
    "llm_primary": CircuitBreakerConfig(
        failure_threshold=3,
        failure_window_seconds=30,
        open_duration_seconds=10,         # Quick recovery for LLM
        persist_state=False               # Stateless OK for LLM
    ),
    "reconciliation_drift": DriftCircuitBreaker(
        drift_rate_threshold=0.1,
        drift_window_seconds=300,
        on_open="PAUSE_RECONCILIATION",
        pause_duration_seconds=600,
        alert_channel="reconciliation-alerts"
    ),
}
```

#### Circuit Breaker State Persistence

```python
class CircuitBreakerState(BaseModel):
    """Persisted circuit breaker state."""
    
    breaker_id: str
    state: Literal["CLOSED", "OPEN", "HALF_OPEN"]
    
    failure_count: int
    success_count: int                    # For half-open tracking
    last_failure_at: Optional[datetime]
    opened_at: Optional[datetime]
    
    # TTL for state recovery
    state_expires_at: datetime


class CircuitBreakerStore:
    """Redis-backed circuit breaker state store."""
    
    def __init__(self, redis: Redis):
        self.redis = redis
        self.key_prefix = "circuit_breaker:"
    
    async def get_state(self, breaker_id: str) -> Optional[CircuitBreakerState]:
        data = await self.redis.get(f"{self.key_prefix}{breaker_id}")
        if data is None:
            return None
        state = CircuitBreakerState.parse_raw(data)
        
        # Check TTL expiry → default to half-open
        if state.state_expires_at < datetime.utcnow():
            return CircuitBreakerState(
                breaker_id=breaker_id,
                state="HALF_OPEN",
                failure_count=0,
                success_count=0,
                last_failure_at=state.last_failure_at,
                opened_at=None,
                state_expires_at=datetime.utcnow() + timedelta(seconds=300)
            )
        return state
    
    async def set_state(self, state: CircuitBreakerState, ttl_seconds: int):
        await self.redis.setex(
            f"{self.key_prefix}{state.breaker_id}",
            ttl_seconds,
            state.json()
        )
```

---

## 12. Tenant Isolation Model

**Architecture:** Database-enforced isolation (Postgres RLS) as hard boundary; middleware as convenience layer.

### 12.1 Database-Level Isolation

```sql
-- Enable RLS on all tenant-scoped tables
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE fulfillments ENABLE ROW LEVEL SECURITY;
ALTER TABLE traces ENABLE ROW LEVEL SECURITY;

-- Create policy: users can only see their tenant's data
-- Use current_setting with missing_ok=true to avoid errors when unset
CREATE POLICY tenant_isolation_orders ON orders
    USING (tenant_id = current_setting('app.current_tenant_id', true)::text);

CREATE POLICY tenant_isolation_payments ON payments
    USING (tenant_id = current_setting('app.current_tenant_id', true)::text);

-- Function to set tenant context (called at start of every transaction)
CREATE OR REPLACE FUNCTION set_tenant_context(p_tenant_id text)
RETURNS void AS $$
BEGIN
    -- true = LOCAL means transaction-scoped (resets at transaction end)
    -- This is intentional: context must be set per-transaction for safety
    PERFORM set_config('app.current_tenant_id', p_tenant_id, true);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Verify tenant context is set (use in critical paths)
CREATE OR REPLACE FUNCTION require_tenant_context()
RETURNS text AS $$
DECLARE
    tid text;
BEGIN
    tid := current_setting('app.current_tenant_id', true);
    IF tid IS NULL OR tid = '' THEN
        RAISE EXCEPTION 'Tenant context not set';
    END IF;
    RETURN tid;
END;
$$ LANGUAGE plpgsql;
```

### 12.2 Connection Pool Configuration

```python
class TenantConnectionConfig(BaseModel):
    """Tenant-aware connection pooling."""
    
    # Strategy
    isolation_strategy: Literal["RLS", "SCHEMA_PER_TENANT", "DATABASE_PER_TENANT"]
    
    # For RLS strategy with transaction-scoped context
    # Context MUST be set at start of every transaction
    pool_mode: Literal["SESSION", "TRANSACTION"]  # TRANSACTION mode OK with per-txn context
    context_setter: str = "SELECT set_tenant_context(%s)"
    
    # Pool settings
    min_connections_per_tenant: int = 1
    max_connections_per_tenant: int = 10
    connection_timeout_seconds: int = 30
    
    # For high-isolation tenants
    dedicated_pool_tenants: List[str] = []  # Tenants with dedicated pools


# Connection wrapper
class TenantConnection:
    """Tenant-scoped database connection with per-transaction context."""
    
    def __init__(self, tenant_id: str, pool: ConnectionPool):
        self.tenant_id = tenant_id
        self.pool = pool
        self._conn = None
    
    async def __aenter__(self):
        self._conn = await self.pool.acquire()
        # Set tenant context - MUST be done at start of every transaction
        # Context is transaction-scoped and auto-resets at commit/rollback
        await self._conn.execute(
            "SELECT set_tenant_context($1)",
            self.tenant_id
        )
        return self._conn
    
    async def __aexit__(self, *args):
        # Context auto-clears at transaction end, but explicit reset for safety
        await self._conn.execute("RESET app.current_tenant_id")
        await self.pool.release(self._conn)
```

**Important:** Tenant context is **transaction-scoped** (not session-scoped). This means:
1. Context MUST be set at the start of every transaction via `set_tenant_context()`
2. Context auto-resets when transaction commits or rolls back
3. PgBouncer can use either `session` or `transaction` pool mode
4. Tests P1-T33/P1-T34 verify context isolation per transaction

### 12.3 Middleware Layer (Convenience + Defense-in-Depth)

```python
class TenantContext(BaseModel):
    """Injected into every request; enforced by kernel."""
    tenant_id: str
    namespace_prefix: str                 # e.g., "shop_abc_"
    credential_scope: str                 # Reference to tenant's secrets
    data_region: str                      # For data residency compliance
    
class TenantEnforcer:
    """Middleware that provides tenant context + validates at application layer."""
    
    def validate_entity_id(self, entity_id: str, ctx: TenantContext) -> bool:
        """Defense-in-depth: verify entity belongs to tenant."""
        # Even though RLS enforces this, validate at app layer too
        return entity_id.startswith(ctx.namespace_prefix)
    
    def get_credentials(self, service: str, ctx: TenantContext) -> Dict:
        """Return tenant-scoped credentials only."""
        return credential_store.get(f"{ctx.credential_scope}:{service}")
    
    def audit_cross_tenant_attempt(self, ctx: TenantContext, target_tenant: str):
        """Log attempted cross-tenant access for security monitoring."""
        audit_log.write({
            "event": "CROSS_TENANT_ATTEMPT",
            "source_tenant": ctx.tenant_id,
            "target_tenant": target_tenant,
            "timestamp": datetime.utcnow(),
            "severity": "HIGH"
        })
```

### 12.4 Credential Rotation Policy

```python
class RotationTrigger(str, Enum):
    SCHEDULED = "SCHEDULED"               # Regular interval
    ON_COMPROMISE = "ON_COMPROMISE"       # Detected or suspected breach
    ON_PERSONNEL_CHANGE = "ON_PERSONNEL_CHANGE"  # Team member departure
    MANUAL = "MANUAL"                     # Operator-initiated


class CredentialRotationConfig(BaseModel):
    """Configuration for credential rotation."""
    
    # Rotation schedule
    rotation_interval_days: int = 90      # Regular rotation interval
    warning_before_expiry_days: int = 14  # Alert before scheduled rotation
    
    # Zero-downtime rotation
    overlap_period_hours: int = 24        # Both old and new valid
    
    # Automation
    auto_rotate: bool = True              # Automated scheduled rotation
    rotation_mechanism: Literal["VAULT", "AWS_SECRETS_MANAGER", "MANUAL_WITH_NOTIFICATION"]
    
    # Compromise handling
    compromise_rotation_immediate: bool = True
    compromise_overlap_hours: int = 0     # No overlap on compromise (immediate revoke)
    
    # Audit
    rotation_audit_log: bool = True
    notify_channels: List[str] = ["security-alerts"]


# Rotation configurations by credential type
ROTATION_CONFIGS = {
    "stripe_api_key": CredentialRotationConfig(
        rotation_interval_days=90,
        overlap_period_hours=24,
        auto_rotate=True,
        rotation_mechanism="VAULT"
    ),
    "shopify_api_key": CredentialRotationConfig(
        rotation_interval_days=90,
        overlap_period_hours=24,
        auto_rotate=True,
        rotation_mechanism="VAULT"
    ),
    "llm_api_key": CredentialRotationConfig(
        rotation_interval_days=30,        # Shorter for high-value
        overlap_period_hours=4,
        auto_rotate=True,
        rotation_mechanism="VAULT"
    ),
}
```

### 12.5 Isolation Requirements by Phase

| Phase | Requirement | Enforcement | Test Coverage |
|-------|-------------|-------------|---------------|
| **1** | RLS enabled on all tables | Database policy | P1-T31 |
| **1** | Namespace prefix on all entities | Entity ID validation | P1-T31 |
| **1** | Per-tenant credentials | Credential scope lookup | P1-T32 |
| **1** | Cross-tenant access logging | Audit trail | P1-T34 |
| **2** | Connection pool isolation | Config per tenant | P2-T-ISO-01 |
| **2** | Dedicated pools for high-value tenants | Pool configuration | P2-T-ISO-02 |
| **3** | Formal non-interference proof | Static analysis | P3-T11 |
| **3** | Tenant data export/delete | GDPR compliance | P3-T11 |

---

## 13. Technology Stack

| Component | Phase 1 | Phase 2 | Phase 3 |
|-----------|---------|---------|---------|
| Orchestrator | LangGraph | LangGraph | LangGraph |
| LLM | Claude Sonnet / GPT-4o | + model routing | + A/B testing |
| State | PostgreSQL | PostgreSQL | PostgreSQL |
| Cache | Redis | Redis | Redis |
| Tracing | Langfuse | Langfuse + OTel | + distributed tracing |
| HITL | Slack | Slack | Slack + escalation |
| SLOs | Counters only | Prometheus + Grafana | + burn-rate alerts |
| Storefront | Shopify | Shopify | Multi-platform |
| Payments | Stripe | Stripe | Stripe |
| Fulfillment | Printful/Gooten | + multi-vendor | + routing |
| Email | SendGrid | SendGrid | SendGrid |
| Analytics | — | Event store + KPI tables | + dashboards |
| Vector DB | — | — | pgvector (if needed) |

---

## 14. File Structure

```
autobiz/
├── kernel/                          # Agent Module
│   ├── orchestrator/
│   ├── executor/
│   ├── state/
│   ├── trace/
│   ├── hitl/
│   ├── eval/
│   ├── compile/
│   └── config/
├── skills/                          # Phase 2+
├── learning/                        # Phase 3
├── portfolio/                       # Phase 3
├── businesses/
│   └── dtc_tshirt/                  # Phase 1 business
│       ├── config.py
│       ├── tools/
│       ├── workflows/
│       └── eval/
└── tests/
```

---

## 15. Testing Architecture

### 15.1 Gate Mathematics

All percentage-based gates (≥95%, ≥80%, 100%) require statistical rigor.

**Use Lower Confidence Bound (LCB)** at 95% confidence, not raw pass rate:

```
Gate passes if: LCB(pass_rate, N, α=0.05) ≥ threshold

Wilson score interval:
  LCB = (p + z²/2n - z√(p(1-p)/n + z²/4n²)) / (1 + z²/n)
  z = 1.96 for 95% confidence
```

**Example**: 19/20 passes = 95% raw, but LCB = 75.1%. Gate **fails**.

| Gate Type | Minimum N | Rationale |
|-----------|-----------|-----------|
| P0 (100%) | 3 consecutive runs | Zero tolerance requires repetition |
| P1 (≥95%) | 20 runs minimum | 95% CI width ≤ ±10% |
| P2 (≥80%) | 10 runs minimum | 80% CI width ≤ ±15% |
| Soak test | Traffic-dependent | min(7 days, 300 events) |

#### Split Success Rate: Completion vs Correctness

Track two separate metrics to avoid masking correctness regressions:

| Metric | Definition | Calculation | Use Case |
|--------|------------|-------------|----------|
| **Completion Rate** | Workflow reaches terminal state | `terminals / invocations` | Availability SLI |
| **Correctness Rate** | Terminal state matches pass criteria | `correct_terminals / terminals` | Quality SLI |

```python
class WorkflowMetrics(BaseModel):
    """Per-workflow metrics with completion/correctness split."""
    workflow_id: str
    window_start: datetime
    window_end: datetime
    
    # Completion (availability)
    invocations: int
    terminals: int                        # Reached any terminal state
    completion_rate: float                # terminals / invocations
    
    # Correctness (quality)
    correct_terminals: int                # Terminal matches pass_criteria
    expected_failures: int                # Terminal = expected failure (e.g., policy rejection)
    unexpected_failures: int              # Terminal = unexpected failure
    correctness_rate: float               # correct_terminals / terminals
    
    # Combined
    overall_success_rate: float           # (correct + expected_failure) / invocations


# Gate requirements
GATE_REQUIREMENTS = {
    "completion": {
        "P0": {"threshold": 0.999, "min_n": 100},   # 99.9% must reach terminal
        "P1": {"threshold": 0.99, "min_n": 50},
    },
    "correctness": {
        "P0": {"threshold": 1.0, "min_n": 20},      # 100% correct when completing
        "P1": {"threshold": 0.95, "min_n": 20},
    },
}
```

### 15.2 Determinism Controls

| Control | Specification |
|---------|---------------|
| Model version | Pin exact model string (e.g., `claude-sonnet-4-20250514`) |
| Temperature | 0.0 for deterministic tests; document if >0 |
| Seed | Record and replay seed for LLM calls |
| Time | Mock `datetime.now()` in tests |
| External state | Reset to known fixture before each test |

### 15.3 Test Classification Schema

**By Execution Environment:**

| Tag | Description | External Calls | CI Stage |
|-----|-------------|----------------|----------|
| `unit` | Isolated, all deps mocked | None | Every PR |
| `integration_internal` | Real DB, APIs mocked | PostgreSQL, Redis | Every PR |
| `integration_external` | Real test-mode APIs | Stripe, Shopify | Nightly |
| `e2e` | Full workflow, real APIs | All | Weekly |

**By Assertion Type:**

| Tag | Description | Oracle Source |
|-----|-------------|---------------|
| `state-change` | Verifies DB/API state | Query result |
| `schema-valid` | Verifies output schema | JSON Schema |
| `semantic-equiv` | Verifies meaning | Embedding/LLM judge |
| `statistical` | Verifies distribution | Confidence interval |

**By Determinism:**

| Tag | Description | Retry Policy |
|-----|-------------|--------------|
| `deterministic` | Same input → same output | 0 retries |
| `pseudo-deterministic` | Deterministic with seed | 1 retry same seed |
| `stochastic` | Inherently variable | Statistical assertion |

### 15.4 Oracle Strategy

Every test must declare its oracle type:

| Oracle Type | When to Use | Verification Method |
|-------------|-------------|---------------------|
| `state-change` | Side effects, DB writes | Query DB/API after action |
| `schema-valid` | Input/output schema compliance (including schema rejects) | JSON Schema validation + executor-not-invoked check |
| `semantic-equiv` | LLM-generated content | Embedding similarity or LLM judge |
| `statistical` | Stochastic behavior | Confidence interval on distribution |

**Drift rule:** CI must fail if any test in the Phase 1 Test Suite lacks an oracle entry in §P1.10, or if a referenced Test ID does not exist.

### 15.5 Test Doubles Strategy

| Component | Double Type | Technology | Rationale |
|-----------|-------------|------------|-----------|
| Shopify API | Stub | WireMock | OpenAPI spec available |
| Stripe API | Stub | WireMock | OpenAPI spec available |
| Printful API | Stub | WireMock | Recorded responses |
| SendGrid | Spy | Custom | Verify calls only |
| Slack (HITL) | Stub | Custom | Canned approve/deny |
| LLM (regression) | Recorded | VCR.py | Deterministic replay |
| LLM (exploration) | Seeded | Live + seed | Reproducible |
| PostgreSQL | Real | TestContainers | ORM semantics |
| Redis | Real | TestContainers | Lua scripts |
| Time | Stub | freezegun | Deterministic |

### 15.6 Flake Policy

| Condition | Action |
|-----------|--------|
| Fails once, passes on retry | Log as flaky; **count as FAIL for deploy gate** |
| Fails 2 consecutive times | Count as fail; immediate triage |
| Flaky > 7 days unresolved | Block from golden suite; require owner |
| Flake rate > 5% of suite | Block deploy; triage required |

#### Quarantine Registry

```python
class QuarantineEntry(BaseModel):
    """Quarantined test tracking."""
    
    test_id: str
    quarantined_at: datetime
    quarantine_reason: str
    
    # Ownership
    owner: str                            # Team or individual
    triage_ticket: Optional[str]          # Link to tracking issue
    
    # SLA
    max_quarantine_days: int = 14         # Default SLA
    sla_expires_at: datetime
    
    # Resolution
    status: Literal["QUARANTINED", "FIXING", "FIXED", "DELETED"]
    resolution: Optional[Literal["FIXED", "DELETED", "PROMOTED_TO_KNOWN_FLAKY"]]
    resolved_at: Optional[datetime]
    resolution_notes: Optional[str]


class KnownFlakyTest(BaseModel):
    """Test acknowledged as inherently flaky with justification."""
    
    test_id: str
    justification: str                    # Why this test is inherently flaky
    approved_by: str                      # Who approved flaky status
    approved_at: datetime
    
    # Constraints
    max_flake_rate: float = 0.1          # Must stay under 10% flake rate
    review_interval_days: int = 90        # Periodic review required
    next_review_at: datetime


class FlakePolicy:
    """Enforced flake handling."""
    
    def on_test_flake(self, test_id: str, run_id: str):
        """Handle detected flake."""
        
        # Always count as failure for deploy gate
        self.record_failure(test_id, run_id, is_flake=True)
        
        # Check if already quarantined
        entry = self.quarantine_registry.get(test_id)
        if entry:
            return  # Already tracked
        
        # Check if known flaky
        known = self.known_flaky_registry.get(test_id)
        if known:
            self.update_flake_rate(known, run_id)
            return
        
        # New flake - quarantine
        self.quarantine_test(test_id, run_id)
    
    def enforce_sla(self):
        """Run periodically to enforce quarantine SLA."""
        
        for entry in self.quarantine_registry.get_expired():
            if entry.status == "QUARANTINED":
                # SLA expired without resolution
                self.alert(
                    f"Test {entry.test_id} quarantine SLA expired. "
                    f"Owner: {entry.owner}. Action required: fix, delete, or justify."
                )
                self.block_owner_deploys(entry.owner)
```

### 15.7 Artifact Retention

| Artifact | Retention | Storage | Notes |
|----------|-----------|---------|-------|
| Test execution logs | 90 days | S3 | — |
| Trace transcripts | Per §2 Trace Retention Policy | Hot→Warm→Cold | 7d PG → 90d S3 → 2y Glacier |
| LLM request/response | 30 days (PII scrubbed) | S3 | — |
| Coverage reports | Forever | Git LFS | — |
| Receipts | Forever | PostgreSQL | Immutable |
| Golden suite snapshots | Forever | Git | Versioned |
| Idempotency keys | 25h Redis + Forever PG | Redis + PostgreSQL | Per §2 INV-05 |

### 15.8 Traceability Requirements

All testing must maintain four traceability dimensions:

```
Risk Register ──► Requirement ──► Test Case ──► CI Job
Workflow ───────► Requirement ──► Test Case
Invariant ──────► Test Case (positive + negative)
Test Case ──────► Sandbox Tier
```

---

# PART II: PHASE 1

---

## P1.1 Phase 1 Entry/Exit Criteria

### Entry Criteria

| ID | Criterion | Verification |
|----|-----------|--------------|
| P1-ENTRY-01 | Development environment provisioned | PostgreSQL, Redis, Langfuse running locally |
| P1-ENTRY-02 | API credentials obtained | Shopify, Stripe, Printful test mode keys |
| P1-ENTRY-03 | Repository initialized | Git repo with CI pipeline stub |

### Exit Criteria (Gate to Phase 2)

| ID | Criterion | Acceptance Test | Target |
|----|-----------|-----------------|--------|
| P1-EXIT-01 | P0 workflows passing | All P0 golden tests green | 100% |
| P1-EXIT-02 | P1 workflows passing | P1 golden test suite | ≥95% |
| P1-EXIT-03 | Invariant enforcement | Zero bypass incidents in 7-day soak | 0 bypasses |
| P1-EXIT-04 | Eval gate functional | ≥1 deploy blocked by gate | Demonstrated |
| P1-EXIT-05 | HITL functional | Refund workflow approval works | Demonstrated |
| P1-EXIT-06 | Trace completeness | All runs have correlation ID + cost | 100% |
| P1-EXIT-07 | Idempotency verified | Duplicate within 24h returns cached | Demonstrated |
| P1-EXIT-08 | Tenant isolation | Cross-tenant access blocked in testing | 0 leaks |
| P1-EXIT-09 | Trace redaction | PII masked, secrets rejected | Audit passed |
| P1-EXIT-10 | Event ordering | Out-of-order webhooks handled correctly | Demonstrated |
| P1-EXIT-11 | Reconciliation | Drift detected and repaired in soak | ≥1 repair |
| P1-EXIT-12 | Success rate measured | Per-workflow success rate calculated | Dashboard live |

---

## P1.2 Phase 1 Components

| ID | Module | Component | Technology | Deliverable | Acceptance |
|----|--------|-----------|------------|-------------|------------|
| P1-C01 | Kernel | Orchestrator | LangGraph | `kernel/orchestrator/engine.py` | Runs workflow end-to-end |
| P1-C02 | Kernel | LLM integration | Claude/GPT-4o | `kernel/orchestrator/llm.py` | Model+prompt pinned per run |
| P1-C03 | Kernel | Tool schema validation | Pydantic/JSON Schema | `kernel/executor/schema.py` | Invalid calls rejected |
| P1-C04 | Kernel | Tool executor | Python | `kernel/executor/executor.py` | Tools execute with timeout |
| P1-C05 | Kernel | Permission enforcement | Allowlists | `kernel/executor/permissions.py` | Forbidden ops blocked |
| P1-C06 | Kernel | Bounds enforcement | Caps + kill | `kernel/executor/bounds.py` | Hard terminate on limit |
| P1-C07 | Kernel | Loop detector | History check | `kernel/executor/loop.py` | Repetition terminated |
| P1-C08 | Kernel | State manager | PostgreSQL | `kernel/state/manager.py` | Versioned patches work |
| P1-C09 | Kernel | Idempotency manager | Redis + PostgreSQL | `kernel/executor/idempotency.py` | Duplicates deduplicated |
| P1-C10 | Kernel | Receipt storage | PostgreSQL | `kernel/executor/receipts.py` | Receipts persisted |
| P1-C11 | Kernel | Trace integration | Langfuse | `kernel/trace/langfuse.py` | Correlation IDs present |
| P1-C12 | Kernel | Cost tracking | Langfuse | `kernel/trace/cost.py` | Cost attributed per run |
| P1-C13 | Kernel | HITL approvals | Slack | `kernel/hitl/slack.py` | Approve/deny works |
| P1-C14 | Kernel | Eval runner | Golden tasks | `kernel/eval/runner.py` | Suite executes |
| P1-C15 | Kernel | Deploy gate | CI integration | `kernel/eval/gate.py` | Blocks on failure |
| P1-C16 | Kernel | Config validator | Static checks | `kernel/compile/validator.py` | 4 checks enforced (CC-01..CC-04) |
| P1-C17 | Business | Shopify integration | Shopify API | `businesses/dtc_tshirt/tools/shopify.py` | Orders CRUD works |
| P1-C18 | Business | Stripe integration | Stripe API | `businesses/dtc_tshirt/tools/stripe.py` | Auth/capture/refund |
| P1-C19 | Business | Printful integration | Printful API | `businesses/dtc_tshirt/tools/printful.py` | Fulfillment created |
| P1-C20 | Business | Email integration | SendGrid | `businesses/dtc_tshirt/tools/email.py` | Emails sent |
| P1-C21 | Business | Tax integration | Stripe Tax | `businesses/dtc_tshirt/tools/tax.py` | Tax calculated |
| P1-C22 | Business | BusinessConfig | YAML/Python | `businesses/dtc_tshirt/config.py` | Validates via compile |
| P1-C23 | Kernel | Tenant context | Middleware | `kernel/tenant/context.py` | Tenant ID injected |
| P1-C24 | Kernel | Tenant enforcer | Query filter | `kernel/tenant/enforcer.py` | Cross-tenant blocked |
| P1-C25 | Kernel | Credential scoper | Secret lookup | `kernel/tenant/credentials.py` | Per-tenant keys |
| P1-C26 | Kernel | Event processor | Pipeline | `kernel/events/processor.py` | Ordering + reconciliation |
| P1-C27 | Kernel | Reconciliation jobs | Scheduled | `kernel/events/reconciliation.py` | Drift repair |

---

## P1.3 Phase 1 Workflows

| Priority | ID | Workflow | Trigger | Tool Sequence | HITL | Pass Criteria |
|----------|----|----------|---------|---------------|------|---------------|
| **P0** | P1-WF01 | Order → Fulfill | Order paid webhook | validateOrder → calculateTax → createOrder → createFulfillment → sendConfirmation | No | Fulfillment created + confirmation sent |
| **P0** | P1-WF02 | Payment failure | Auth fail event | classifyFailure → notifyCustomer → createSupportTicket | No | No charge; customer notified |
| **P1** | P1-WF03 | Refund (bounded) | Refund request | fetchOrder → checkPolicy → proposeRefund → executeRefund | Yes | Refund once; receipt stored |
| **P1** | P1-WF04 | Cancel pre-fulfill | Cancel request | fetchOrder → checkFulfillmentState → cancelOrder → voidAuth | Yes if $ | Cancel applied; no orphan |
| **P1** | P1-WF05 | WISMO | Customer email | lookupShipment → draftResponse → sendEmail | No | Correct status + response |
| **P2** | P1-WF06 | Fulfillment exception | POD error event | classifyError → retryWithBackoff → escalate | Yes on repeat | No infinite retry; escalation |
| **P2** | P1-WF07 | Daily closeout | Scheduled | aggregateMetrics → postSlackReport | No | Report matches events |

---

## P1.4 Phase 1 Requirements Traceability Matrix

### Hygiene Requirements (Test Safety)

| Req ID | Requirement Name | Description | Test Case ID | Priority | Status |
|--------|------------------|-------------|--------------|----------|--------|
| P1-RH01 | Test mode enforcement | All external API calls use test/sandbox mode | P1-H01, P1-H02, P1-H03, P1-H04 | P0 | — |
| P1-RH02 | No real customer contact | Tests never email/SMS real customers | P1-H02, P1-H05 | P0 | — |
| P1-RH03 | Isolated test data | Test suite uses isolated database and namespaces | P1-H09 | P0 | — |
| P1-RH04 | Idempotency TTL | Idempotency keys expire after 24-hour window | P1-H07, P1-H08 | P0 | — |
| P1-RH05 | Webhook security | All webhooks validate cryptographic signatures | P1-H10 | P0 | — |

### Functional Requirements

| Req ID | Requirement Name | Description | Test Case ID | Priority | Status |
|--------|------------------|-------------|--------------|----------|--------|
| P1-R01 | Schema validation | All tool calls validated against JSON Schema before execution | P1-T01, P1-T02 | P0 | — |
| P1-R02 | Permission enforcement | Forbidden operations blocked and traced | P1-T03, P1-T04 | P0 | — |
| P1-R03 | Execution bounds | Runs terminated at step/time/token/tool limits | P1-T05, P1-T06, P1-T07 | P0 | — |
| P1-R04 | Loop termination | Repeated tool sequences detected and terminated | P1-T08 | P0 | — |
| P1-R05 | Trace completeness | Every run has correlation ID, steps, cost | P1-T09, P1-T10 | P0 | — |
| P1-R06 | Idempotency | Duplicate side-effect requests return cached result (24h window) | P1-T11, P1-T12 | P0 | — |
| P1-R07 | Receipt storage | All side effects produce stored receipt | P1-T13 | P0 | — |
| P1-R08 | State durability | State patches versioned and replayable | P1-T14, P1-T15 | P0 | — |
| P1-R09 | HITL gating | High-risk ops blocked until approval | P1-T16, P1-T17 | P0 | — |
| P1-R10 | Eval gating | Deploys blocked if suite < threshold | P1-T18 | P0 | — |
| P1-R11 | Order fulfillment | Paid order triggers fulfillment + confirmation | P1-T19, P1-T20 | P0 | — |
| P1-R12 | Payment failure handling | Auth failures notified, no charge | P1-T21 | P0 | — |
| P1-R13 | Refund processing | Refunds executed once with receipt | P1-T22, P1-T23 | P1 | — |
| P1-R14 | Order cancellation | Pre-fulfillment cancels work cleanly | P1-T24 | P1 | — |
| P1-R15 | WISMO response | Shipment status returned accurately | P1-T25 | P1 | — |
| P1-R16 | Fulfillment exceptions | Errors retried with backoff, then escalated | P1-T26 | P2 | — |
| P1-R17 | Daily closeout | Report generated matching event log | P1-T27 | P2 | — |
| P1-R18 | Tool closure check | Compile rejects missing tools | P1-T28 | P0 | — |
| P1-R19 | Bounds check | Compile rejects zero/missing bounds | P1-T29 | P0 | — |
| P1-R20 | Scopes check | Compile rejects missing permission scopes | P1-T30 | P0 | — |

### Tenant Isolation Requirements (Phase 1 Scope)

| Req ID | Requirement Name | Description | Test Case ID | Priority | Status |
|--------|------------------|-------------|--------------|----------|--------|
| P1-R21 | Tenant namespace | All entity IDs prefixed with tenant namespace | P1-T31 | P0 | — |
| P1-R22 | Tenant credential scope | Each tenant uses isolated API credentials | P1-T32 | P0 | — |
| P1-R23 | Tenant query filter | All queries filtered by tenant_id | P1-T33 | P0 | — |
| P1-R24 | Cross-tenant block | Access to other tenant's data rejected | P1-T34 | P0 | — |
| P1-R25 | Trace redaction | PII masked, secrets rejected in traces | P1-T35 | P0 | — |

### Event Processing Requirements

| Req ID | Requirement Name | Description | Test Case ID | Priority | Status |
|--------|------------------|-------------|--------------|----------|--------|
| P1-R26 | Event deduplication | Duplicate webhooks detected and skipped | P1-T36 | P0 | — |
| P1-R27 | Event ordering | Out-of-order events held until predecessor | P1-T37 | P1 | — |
| P1-R28 | Event timeout | Held events released after 60s timeout | P1-T38 | P1 | — |
| P1-R29 | State reconciliation | Drift detected and repaired by sync jobs | P1-T39 | P1 | — |
| P1-R30 | Reconciliation HITL | Financial drift requires human approval | P1-T40 | P1 | — |

---

## P1.4.1 Phase 1 Ops Minimum Requirements

Day-2 operational readiness requires these dashboards and alerts before soak test:

### Required Dashboards

| Dashboard | Metrics | Refresh | Alert Threshold |
|-----------|---------|---------|-----------------|
| **Gate Pass Rates** | LCB per gate, trend, by workflow | 1 min | LCB drops >5% in 1hr |
| **HITL Backlog** | Queue depth, age distribution, oldest item | 1 min | Oldest >15min or depth >50 |
| **Circuit Breaker States** | Per-dependency state, transition history | 1 min | Any breaker OPEN >5min |
| **Reconciliation Queue** | Depth, age, success rate, drift rate | 1 min | Depth >100 or drift rate >5% |
| **Invariant Violations** | Count by type (INV-01..08), trend | 1 min | Any violation |
| **Cost Attribution** | LLM tokens, API calls per workflow | 5 min | Cost >2x baseline |

### Required Alerts

| Alert | Condition | Severity | Escalation |
|-------|-----------|----------|------------|
| **Gate Failure** | Any P0 gate fails | P1 | Page on-call |
| **HITL SLA Breach** | Approval pending >30min | P2 | Slack escalation |
| **Circuit Breaker Open** | Any dependency OPEN | P2 | Slack alert |
| **Reconciliation Backlog** | Queue depth >100 | P2 | Slack alert |
| **Invariant Violation** | Any INV-01..03 violation | P1 | Page on-call |
| **Invariant Violation** | Any INV-04..08 violation | P2 | Slack alert |
| **Deploy Rollback Trigger** | Completion rate <95% post-deploy | P1 | Auto-rollback + page |

### Required Runbooks

| Runbook | Trigger | Contents |
|---------|---------|----------|
| **RB-01: HITL Escalation** | HITL SLA breach | Escalation contacts, override procedure, audit trail |
| **RB-02: Circuit Breaker Trip** | Breaker OPEN >5min | Dependency status check, manual reset, fallback activation |
| **RB-03: Reconciliation Failure** | Drift rate >10% | Root cause triage, manual repair procedure, sync job restart |
| **RB-04: Invariant Violation** | Any violation | Investigation checklist, incident classification, fix verification |
| **RB-05: Deploy Rollback** | Auto-rollback triggered | Rollback verification, root cause, re-deploy checklist |

---

## P1.5 Phase 1 Test Suite

> **Oracle types for each test are specified in §P1.10 Oracle Specification.**

### P0 Hygiene Tests (Must Pass 100% — Safety Guards)

| Test ID | Test Name | Description | Validates | Acceptance Criteria |
|---------|-----------|-------------|-----------|---------------------|
| P1-H01 | Stripe test mode only | Test suite never calls Stripe live API | Test safety | All Stripe calls use `sk_test_*` key |
| P1-H02 | No real customer email | Test suite never emails real customer addresses | Test safety | All emails to `*@test.example.com` or sandbox |
| P1-H03 | Printful sandbox only | Test suite never calls Printful production | Test safety | All calls use sandbox endpoint |
| P1-H04 | Shopify dev store only | Test suite never touches live Shopify store | Test safety | Store URL matches `*.myshopify.com` dev pattern |
| P1-H05 | No real SMS | Test suite never sends real SMS | Test safety | All SMS to test numbers or mocked |
| P1-H06 | No real Slack DM | Test suite never DMs real users | Test safety | All Slack to `#test-*` channels only |
| P1-H07 | Idempotency key deterministic | Idempotency keys are deterministic (no temporal component in key) | INV-05 | Key format: `{tenant}:{tool}:{ver}:{principal}:{fingerprint_32hex}`; TTL tracked via `first_seen_at` metadata |
| P1-H08 | 24-hour lookback honored | Duplicate within 24h returns cached; after 24h re-executes | INV-05 | Both cases verified |
| P1-H09 | No production DB writes | Test suite uses isolated test database | Test safety | DB connection string contains `_test` |
| P1-H10 | Webhook signatures verified | All incoming webhooks validate signatures | Security | Invalid signature rejected |

### P0 Tests (Must Pass 100%)

| Test ID | Test Name | Description | Validates Req | Acceptance Criteria |
|---------|-----------|-------------|---------------|---------------------|
| P1-T01 | Schema valid accept | Valid tool input accepted | P1-R01 | Tool executes successfully |
| P1-T02 | Schema invalid reject | Invalid tool input rejected pre-exec | P1-R01 | Error returned; no execution |
| P1-T03 | Permission allowed | Allowed operation executes | P1-R02 | Operation completes |
| P1-T04 | Permission denied | Forbidden operation blocked | P1-R02 | Error returned; op blocked; trace logged |
| P1-T05 | Bounds step limit | Run terminates at max_steps | P1-R03 | Terminated; violation logged |
| P1-T06 | Bounds time limit | Run terminates at max_time | P1-R03 | Terminated; violation logged |
| P1-T07 | Bounds token limit | Run terminates at max_tokens | P1-R03 | Terminated; violation logged |
| P1-T08 | Loop detection | Repeated sequence terminated | P1-R04 | Terminated; loop logged |
| P1-T09 | Trace correlation | Run has correlation ID | P1-R05 | ID present in all events |
| P1-T10 | Trace cost | Run has cost attribution | P1-R05 | Cost > 0 recorded |
| P1-T11 | Idempotency first call | First call executes and stores | P1-R06 | Execution + receipt stored |
| P1-T12 | Idempotency duplicate | Duplicate call returns cached | P1-R06 | No re-execution; cached returned |
| P1-T13 | Receipt stored | Side effect produces receipt | P1-R07 | Receipt in DB with details |
| P1-T14 | State versioned | State patch creates version | P1-R08 | Version incremented |
| P1-T15 | State replayable | Transcript replays to same state | P1-R08 | States match |
| P1-T16 | HITL blocks | HITL-required op waits for approval | P1-R09 | Execution paused |
| P1-T17 | HITL approves | Approved op executes | P1-R09 | Execution completes |
| P1-T18 | Eval gate blocks | Deploy blocked at <95% (deterministic forced failure) | P1-R10 | CI fails; `deploy_blocked=true` |
| P1-T19 | Order creates fulfillment | Paid order → fulfillment created | P1-R11 | Printful fulfillment exists |
| P1-T20 | Order sends confirmation | Paid order → email sent | P1-R11 | Email delivered |
| P1-T21 | Payment failure notifies | Auth fail → customer notified | P1-R12 | Email sent; no charge |
| P1-T28 | Compile tool closure | Missing tool rejected | P1-R18 | Compile fails with error |
| P1-T29 | Compile bounds check | Zero bounds rejected | P1-R19 | Compile fails with error |
| P1-T30 | Compile scopes check | Missing scope rejected | P1-R20 | Compile fails with error |
| P1-T41 | Compile FINANCIAL no AUTO_APPROVE | FINANCIAL tool with AUTO_APPROVE rejected | Compile | Compile fails with error |

### P0 Tenant Isolation Tests (Must Pass 100%)

| Test ID | Test Name | Description | Validates Req | Acceptance Criteria |
|---------|-----------|-------------|---------------|---------------------|
| P1-T31 | Entity namespace | Entity ID includes tenant prefix | P1-R21 | All entities start with `{tenant}_` |
| P1-T32 | Credential isolation | Tenant A can't use Tenant B's keys | P1-R22 | Access denied; audit logged |
| P1-T33 | Query filter injection | Queries auto-filtered by tenant | P1-R23 | SQL includes `tenant_id = ?` |
| P1-T34 | Cross-tenant blocked | Request for other tenant's data fails | P1-R24 | 403 returned; attempt logged |
| P1-T35 | Trace PII redacted | PII masked in persisted trace | P1-R25 | Email shows `j***@***.com` |

### P1 Event Processing Tests (Must Pass ≥95%)

| Test ID | Test Name | Description | Validates Req | Acceptance Criteria |
|---------|-----------|-------------|---------------|---------------------|
| P1-T36 | Duplicate webhook skipped | Same event ID processed once | P1-R26 | Second call returns cached |
| P1-T37 | Out-of-order held | Later event waits for predecessor | P1-R27 | Event queued until predecessor |
| P1-T38 | Held event timeout | Held event processed after 60s | P1-R28 | Event processed; logged as out-of-order |
| P1-T39 | Drift detected | Sync job finds mismatch | P1-R29 | Drift record created |
| P1-T40 | Drift HITL | Financial drift requires approval | P1-R30 | Repair blocked until approved |

### P1 Tests (Must Pass ≥95%)

| Test ID | Test Name | Description | Validates Req | Acceptance Criteria |
|---------|-----------|-------------|---------------|---------------------|
| P1-T22 | Refund executes | Valid refund request processed | P1-R13 | Stripe refund created; receipt stored |
| P1-T23 | Refund idempotent | Duplicate refund returns cached | P1-R13 | No double refund |
| P1-T24 | Cancel pre-fulfill | Cancel before ship succeeds | P1-R14 | Order cancelled; auth voided |
| P1-T25 | WISMO accurate | Status query returns correct info | P1-R15 | Tracking matches Printful |

### P2 Tests (Should Pass ≥80%)

| Test ID | Test Name | Description | Validates Req | Acceptance Criteria |
|---------|-----------|-------------|---------------|---------------------|
| P1-T26 | Fulfillment retry | POD error retried with backoff | P1-R16 | Retry attempted; escalation on fail |
| P1-T27 | Closeout report | Daily report matches events | P1-R17 | Totals match event store |

---

## P1.6 Phase 1 Testing Entry/Exit Criteria

### Testing Entry Criteria

| ID | Criterion | Verification |
|----|-----------|--------------|
| P1-T-ENTRY-01 | CI pipeline executes tests | `pytest` runs on PR |
| P1-T-ENTRY-02 | Test fixtures for DB state | PostgreSQL fixtures load |
| P1-T-ENTRY-03 | Mock server infrastructure | WireMock running |

### Testing Exit Criteria (Gate to Phase 2)

| ID | Criterion | Acceptance Test | Target |
|----|-----------|-----------------|--------|
| P1-T-EXIT-01 | External APIs mocked | All `integration_internal` use mocks | 100% |
| P1-T-EXIT-02 | Negative invariant tests | INV-01,02,05,07 have ≥3 negative tests each | 12+ tests |
| P1-T-EXIT-03 | Oracle strategy documented | Each P0/P1 test has oracle tag | 100% |
| P1-T-EXIT-04 | Risk register tests | RK01, RK02 have explicit tests | 4+ tests |
| P1-T-EXIT-05 | LCB gate math implemented | Wilson estimator in CI | Demonstrated |
| P1-T-EXIT-06 | Flake policy enforced | Quarantine system functional | Demonstrated |
| P1-T-EXIT-07 | Workflow traceability | All P1-WF* map to Req and Test | 100% |
| P1-T-EXIT-08 | Gating tests deterministic | P1-T18 forces failure deterministically | Demonstrated |

---

## P1.7 Phase 1 Testing Components

| ID | Component | Technology | Deliverable | Acceptance |
|----|-----------|------------|-------------|------------|
| P1-TC01 | Mock server | WireMock | `tests/mocks/wiremock/` | Shopify/Stripe/Printful stubs |
| P1-TC02 | LLM response recorder | VCR.py | `tests/fixtures/llm_cassettes/` | Record/replay works |
| P1-TC03 | DB fixture loader | pytest-postgresql | `tests/fixtures/db/` | State reset per test |
| P1-TC04 | Negative test suite | pytest | `tests/invariants/negative/` | INV-01,02,05,07 covered |
| P1-TC05 | Oracle registry | YAML | `tests/oracles.yaml` | Each test has oracle |
| P1-TC06 | Gate calculator | Python | `kernel/eval/gate_math.py` | LCB implemented |
| P1-TC07 | Flake quarantine | pytest plugin | `tests/conftest.py` | Quarantine works |
| P1-TC08 | Risk test suite | pytest | `tests/risks/` | RK01, RK02 covered |
| P1-TC09 | Workflow trace matrix | Markdown | `docs/traceability/` | WF→Req→Test complete |

---

## P1.8 Phase 1 Negative Invariant Tests

### INV-01 Schema Validation (Negative)

| Test ID | Description | Input | Expected |
|---------|-------------|-------|----------|
| P1-T01-NEG-01 | Malformed JSON | `{invalid json` | 400 + SCHEMA_PARSE_ERROR |
| P1-T01-NEG-02 | Missing required field | `{"order_id": null}` | 400 + field name |
| P1-T01-NEG-03 | Wrong type | `{"amount": "fifty"}` | 400 + type error |
| P1-T01-NEG-04 | SQL injection | `{"name": "'; DROP TABLE--"}` | Sanitized or rejected |
| P1-T01-NEG-05 | Overflow integer | `{"quantity": 9999999999999}` | 400 or capped |
| P1-T01-NEG-06 | Extra fields | `{"order_id": 1, "hack": true}` | Ignored or rejected |

### INV-02 Permission Enforcement (Negative)

| Test ID | Description | Input | Expected |
|---------|-------------|-------|----------|
| P1-T02-NEG-01 | Tool outside scope | Call `refund` from READ scope | 403 + PERMISSION_DENIED |
| P1-T02-NEG-02 | Data cap exceeded | Request 10MB when cap 1MB | 413 + DATA_CAP_EXCEEDED |
| P1-T02-NEG-03 | Network allowlist bypass | Call `http://evil.com` | Blocked + logged |
| P1-T02-NEG-04 | URL encoding bypass | `http://evil%2Ecom` | Normalized + blocked |
| P1-T02-NEG-05 | Scope escalation | Tool A calls Tool B outside scope | Blocked at Tool B |

### INV-05 Idempotency (Negative)

| Test ID | Description | Input | Expected |
|---------|-------------|-------|----------|
| P1-T05-NEG-01 | Key collision | Different request, same key | Return original result |
| P1-T05-NEG-02 | Concurrent duplicates | Same request, 10ms apart | One executes, one cached |
| P1-T05-NEG-03 | Key reuse after TTL | Same key after 25h | New execution |

### INV-07 HITL (Negative)

| Test ID | Description | Input | Expected |
|---------|-------------|-------|----------|
| P1-T07-NEG-01 | Spoofed approval | Approval from non-authorized user | Rejected + audit |
| P1-T07-NEG-02 | Replay attack | Resubmit previous approval token | Rejected (nonce) |
| P1-T07-NEG-03 | Timeout → FAIL | No response within timeout | Action fails + logged |
| P1-T07-NEG-04 | Timeout → ESCALATE | No response, escalate configured | Escalation triggered |

---

## P1.9 Phase 1 Risk Register Tests

### RK01: LLM Rate Limits

| Test ID | Description | Setup | Expected |
|---------|-------------|-------|----------|
| P1-T-RK01a | Rate limit triggers retry | Mock returns 429 | Retry with backoff |
| P1-T-RK01b | Fallback model activates | Primary 429 3x | Fallback used |
| P1-T-RK01c | Exhausted retries | All attempts 429 | Graceful failure |

### RK02: Stripe Webhook Delays

| Test ID | Description | Setup | Expected |
|---------|-------------|-------|----------|
| P1-T-RK02a | Delayed webhook | Arrives 60s late | Idempotent processing |
| P1-T-RK02b | Out-of-order webhooks | `succeeded` before `created` | Correct final state |
| P1-T-RK02c | Duplicate webhook | Same event ID twice | Deduplicated |
| P1-T-RK02d | Missing webhook | Webhook lost | Reconciliation recovers |

### RK07: Out-of-Order Webhooks

| Test ID | Description | Setup | Expected |
|---------|-------------|-------|----------|
| P1-T-RK07a | Hold until predecessor | Event B before A | B queued until A |
| P1-T-RK07b | Timeout releases held | A never arrives | B processed after 60s |

### RK08: PII in Traces

| Test ID | Description | Setup | Expected |
|---------|-------------|-------|----------|
| P1-T-RK08a | Email masked | Email in tool output | `j***@***.com` in trace |
| P1-T-RK08b | Secret rejected | API key in output | Trace write blocked + alert |

### RK06: Cross-Tenant Isolation (Basic)

While formal verification is Phase 3, basic adversarial tests exist in Phase 1:

| Test ID | Description | Setup | Expected |
|---------|-------------|-------|----------|
| P1-T-RK06a | Direct tenant ID manipulation | Request with forged tenant_id header | RLS blocks; audit logged |
| P1-T-RK06b | SQL injection in entity lookup | `'; SELECT * FROM orders--` in order_id | Query parameterized; no leak |
| P1-T-RK06c | Entity ID namespace bypass | Request entity_id with wrong prefix | Application validation rejects |

---

## P1.10 Phase 1 Oracle Specification

> **Coverage:** P1-H01..H10 and P1-T01..T41. CI fails if any listed test lacks an oracle entry, or if a referenced Test ID does not exist. Ranges are only used for contiguous IDs where the oracle definition is identical.

| Test ID | Oracle Type | Oracle Definition |
|---------|-------------|-------------------|
| P1-H01..H06 | `state-change` | Safety doubles enforced: Stripe/Shopify/Printful/SendGrid/SMS/Slack calls routed only to test/sandbox endpoints and test destinations; any live endpoint or non-test destination fails the test |
| P1-H07 | `state-change` | Idempotency key format matches spec; deterministic for identical inputs; no temporal component |
| P1-H08 | `state-change` | Idempotency 24-hour lookback honored: within window returns cached without re-exec; after window re-executes |
| P1-H09 | `state-change` | Database writes confined to isolated `_test` database/namespace; no prod connection strings |
| P1-H10 | `state-change` | Webhook signature validation enforced: invalid signatures rejected pre-store/apply |

| P1-T01 | `schema-valid` | Tool input conforms to schema; tool executes successfully |
| P1-T02 | `schema-valid` | Schema validation fails; error code `SCHEMA_INVALID`; **no tool execution** |
| P1-T03 | `state-change` | Allowed operation completes; execution traced |
| P1-T04 | `state-change` | Error code `PERMISSION_DENIED`; op blocked; denial traced; **no side effect** |
| P1-T05..T07 | `state-change` | Run terminates; `termination_reason` matches configured bound (steps/time/tokens); violation logged |
| P1-T08 | `state-change` | Run terminates with `termination_reason=LOOP_DETECTED`; loop evidence recorded |
| P1-T09 | `state-change` | `correlation_id` present and propagated to all emitted events/records |
| P1-T10 | `state-change` | Cost attribution recorded for run (`cost_total > 0`) |
| P1-T11 | `state-change` | First execution occurs; receipt stored with `internal_idempotency_key` |
| P1-T12 | `state-change` | Duplicate returns cached; **no re-execution**; prior receipt referenced |
| P1-T13 | `state-change` | Receipt exists with provider request id + result hash; includes internal+external idempotency keys (when applicable) |
| P1-T14 | `state-change` | State patch creates new state version; version increments |
| P1-T15 | `state-change` | Transcript replay yields identical final state hash + receipts |
| P1-T16 | `state-change` | HITL request created; status `PENDING`; execution paused |
| P1-T17 | `state-change` | HITL decision logged; status `APPROVED`; execution completes |
| P1-T18 | `state-change` | CI gate fails; artifact `deploy_blocked=true` emitted |
| P1-T19..T21 | `state-change` | Workflow side effects applied once: fulfillment created / email sent / payment-failure notify sent; associated receipts stored; **no unintended charges** for failure path |
| P1-T22 | `state-change` | Stripe refund created; refund receipt stored |
| P1-T23 | `state-change` | Duplicate refund returns cached; **no double refund** |
| P1-T24 | `state-change` | Cancel pre-fulfill succeeds; order cancelled; auth voided; receipts stored |
| P1-T25 | `semantic-equiv` | WISMO response returns correct order + shipment status; tracking number matches Printful record |
| P1-T26 | `state-change` | Fulfillment exception triggers retry/backoff and escalation path per policy |
| P1-T27 | `state-change` | Closeout report totals match event store ledger for the day |
| P1-T28..T30 | `schema-valid` | Compile-time validation fails with correct error code (missing tool / invalid bounds / missing scope); **no execution** |
| P1-T31 | `state-change` | Entity IDs include tenant namespace prefix (`{tenant}_*`) |
| P1-T32 | `state-change` | Cross-tenant credential use denied; attempt audited |
| P1-T33 | `state-change` | Query layer enforces `tenant_id` scoping (verified via explain/trace) |
| P1-T34 | `state-change` | Cross-tenant data access returns 403; attempt logged |
| P1-T35 | `state-change` | Persisted trace redacts PII per policy (e.g., email masked) |
| P1-T36 | `state-change` | Duplicate webhook processed once; second call deduped/cached |
| P1-T37 | `state-change` | Out-of-order event held in `HELD_ORDERING` until predecessor present |
| P1-T38 | `state-change` | Held event released after timeout; processed with out-of-order flag logged |
| P1-T39 | `state-change` | Drift record created by reconciliation detector |
| P1-T40 | `state-change` | Financial drift repair requires HITL; repair blocked until approved/denied |
| P1-T41 | `schema-valid` | Compile rejects FINANCIAL tool with `AUTO_APPROVE` or missing HITL gate; **no execution** |

---

## P1.11 Phase 1 Workflow Traceability Matrix

| Workflow ID | Workflow Name | Requirements | Tests | Risk Coverage |
|-------------|---------------|--------------|-------|---------------|
| P1-WF01 | Order → Fulfill | P1-R11 | P1-T19, P1-T20 | RK02 |
| P1-WF02 | Payment failure | P1-R12 | P1-T21 | RK01 |
| P1-WF03 | Refund | P1-R13 | P1-T22, P1-T23 | — |
| P1-WF04 | Cancel pre-fulfill | P1-R14 | P1-T24 | — |
| P1-WF05 | WISMO | P1-R15 | P1-T25 | — |
| P1-WF06 | Fulfillment exception | P1-R16 | P1-T26 | RK03 |
| P1-WF07 | Daily closeout | P1-R17 | P1-T27 | — |

---

## P1.12 Phase 1 CI Pipeline Specification

```yaml
stages:
  - name: hygiene
    trigger: every PR
    tests: tag:hygiene
    timeout: 2 min
    gate: 100% pass (raw)
    note: Abort pipeline if any hygiene test fails
    
  - name: unit
    trigger: every PR
    tests: tag:unit
    timeout: 5 min
    gate: 100% pass (raw)
    
  - name: integration_internal            # Underscore consistency
    trigger: every PR
    tests: tag:integration_internal
    timeout: 10 min
    gate: 100% pass (raw)                 # No degenerate LCB
    note: All deps mocked; should be deterministic
    
  - name: integration_external            # Underscore consistency
    trigger: nightly + pre-release
    tests: tag:integration_external
    timeout: 30 min
    runs: 3                               # Multiple runs for LCB validity
    gate: LCB(pass_rate, N=3*test_count, α=0.05) ≥ 0.95
    min_tests: 20                         # Minimum N for valid LCB
    
  - name: golden_suite
    trigger: deploy gate
    tests: tag:P0 + tag:P1
    runs: 3
    gate: |
      P0: 100% pass (all 3 runs)
      P1: LCB(pass_rate, N=3*test_count, α=0.05) ≥ 0.95
    min_tests_p1: 20                      # Minimum N for P1 LCB
    flake_handling: any_initial_fail_counts_as_fail
    artifacts: [coverage, traces, flake_report, quarantine_status]
```

#### Tag Naming Standard

```python
# CORRECT: Use underscores consistently
@pytest.mark.unit
@pytest.mark.integration_internal
@pytest.mark.integration_external
@pytest.mark.e2e

# WRONG: Do not mix hyphens
# @pytest.mark.integration-internal  # INVALID
```

---

# PART III: PHASE 2

---

## P2.1 Phase 2 Entry/Exit Criteria

### Entry Criteria

| ID | Criterion | Verification |
|----|-----------|--------------|
| P2-ENTRY-01 | Phase 1 exit criteria met | All P1-EXIT-* verified |
| P2-ENTRY-02 | Phase 1 testing exit criteria met | All P1-T-EXIT-* verified |
| P2-ENTRY-03 | 7-day production soak | DTC shop running with real orders |
| P2-ENTRY-04 | Baseline metrics established | Success rate, latency, cost per workflow |

### Exit Criteria (Gate to Phase 3)

| ID | Criterion | Acceptance Test | Target |
|----|-----------|-----------------|--------|
| P2-EXIT-01 | P0 workflows passing | All P0 golden tests green | 100% |
| P2-EXIT-02 | P1 workflows passing | P1 golden test suite | ≥95% |
| P2-EXIT-03 | Spawn gate functional | New business deployed via gate | Demonstrated |
| P2-EXIT-04 | Second business passing | New shop P1 suite | ≥95% |
| P2-EXIT-05 | Crystallization working | ≥3 skills promoted via replay test | Demonstrated |
| P2-EXIT-06 | Lessons stored | ≥10 lessons in structured store | Count verified |
| P2-EXIT-07 | Burn-rate SLOs active | Alerts triggered on degradation | Demonstrated |
| P2-EXIT-08 | Expanded workflows | All P2 workflows at ≥80% | Suite passing |

---

## P2.2 Phase 2 Components

| ID | Module | Component | Technology | Deliverable | Acceptance |
|----|--------|-----------|------------|-------------|------------|
| P2-C01 | Kernel | Business spawner | Templates + generator | `kernel/spawner/generator.py` | Emits valid BusinessConfig |
| P2-C02 | Kernel | Config validator (expanded) | Static checks | `kernel/compile/validator.py` | Rejects invalid configs |
| P2-C03 | Kernel | Skills registry | PostgreSQL | `skills/registry.py` | Skills stored + versioned |
| P2-C04 | Kernel | Skill promotion | Crystallization | `skills/promotion.py` | Plans promoted to skills |
| P2-C05 | Kernel | Replay testing | Golden suite | `skills/replay.py` | Skills pass replay |
| P2-C06 | Kernel | Lessons store | PostgreSQL | `learning/lessons.py` | Lessons CRUD works |
| P2-C07 | Kernel | Outcome tracking | Event tables | `kernel/trace/outcomes.py` | Outcomes linked to runs |
| P2-C08 | Kernel | SLO engine | Prometheus + Grafana | `kernel/slo/engine.py` | Burn-rate alerts fire |
| P2-C09 | Kernel | Shadow mode | Traffic routing | `kernel/eval/shadow.py` | Shadow runs execute |
| P2-C10 | Business | Return/exchange tools | APIs | `businesses/*/tools/returns.py` | RMA flow works |
| P2-C11 | Business | Discount tools | Shopify | `businesses/*/tools/discounts.py` | Discounts created |
| P2-C12 | Business | Chargeback tools | Stripe | `businesses/*/tools/chargebacks.py` | Evidence submitted |
| P2-C13 | Business | Inventory tools | APIs | `businesses/*/tools/inventory.py` | Stock adjusted |
| P2-C14 | Business | Marketing tools | Ads APIs | `businesses/*/tools/marketing.py` | Spend controlled |
| P2-C15 | Business | Support ticketing | Zendesk/Fresh | `businesses/*/tools/support.py` | Tickets created |
| P2-C16 | Business | Analytics pipeline | PostgreSQL | `businesses/*/analytics/` | KPI tables populated |

---

## P2.3 Phase 2 Workflows

| Priority | ID | Workflow | Trigger | Tool Sequence | HITL | Pass Criteria |
|----------|----|----------|---------|---------------|------|---------------|
| **P0** | P2-WF01 | Spawn new business | Operator request | generateConfig → validateConfig → runGoldenSuite → enableWrites | Yes | New shop critical ≥95% |
| **P1** | P2-WF02 | Product launch | Design approved | createProduct → createVariant → publishListing | Yes | Listing live; no broken variants |
| **P1** | P2-WF03 | Return/exchange | Return request | validateWindow → createRMA → updateInventory → notifyCustomer | Yes on exception | RMA issued; inventory reconciled |
| **P1** | P2-WF04 | Chargeback response | Stripe dispute | gatherEvidence → draftPacket → submitEvidence | Yes | Submitted before deadline |
| **P1** | P2-WF05 | Discount/promo | Promo request | validateMargin → createDiscount | Yes | Margin floor enforced |
| **P2** | P2-WF06 | Inventory threshold | Low-stock event | forecastDemand → adjustAvailability | No | No oversell |
| **P2** | P2-WF07 | Marketing spend control | Budget drift | detectDrift → pauseCampaign | Yes if high | Spend capped |
| **P2** | P2-WF08 | Skill crystallization | Repeated success | extractPlan → runReplayTests → promoteSkill | No | Skill passes ≥95% replay |

---

## P2.4 Phase 2 Requirements Traceability Matrix

### Hygiene Requirements (Test Safety)

| Req ID | Requirement Name | Description | Test Case ID | Priority | Status |
|--------|------------------|-------------|--------------|----------|--------|
| P2-RH01 | Spawned config test mode | Generated configs use test credentials only | P2-H01 | P0 | — |
| P2-RH02 | Marketing sandbox | Marketing/ads tools use sandbox mode | P2-H02 | P0 | — |
| P2-RH03 | Skill replay isolation | Crystallized skill replays never hit live APIs | P2-H05 | P0 | — |
| P2-RH04 | Lesson namespace isolation | Lessons scoped to test namespace | P2-H06 | P0 | — |

### Functional Requirements

| Req ID | Requirement Name | Description | Test Case ID | Priority | Status |
|--------|------------------|-------------|--------------|----------|--------|
| P2-R01 | Business spawn | Generate valid BusinessConfig from template | P2-T01 | P0 | — |
| P2-R02 | Spawn validation | Reject invalid generated configs | P2-T02 | P0 | — |
| P2-R03 | Spawn eval gate | New business must pass ≥95% critical | P2-T03 | P0 | — |
| P2-R04 | Skill extraction | Repeated plans identified for promotion | P2-T04 | P1 | — |
| P2-R05 | Skill replay test | Promoted skills pass replay suite | P2-T05 | P1 | — |
| P2-R06 | Skill invocation | Crystallized skills execute correctly | P2-T06 | P1 | — |
| P2-R07 | Lesson storage | Lessons stored with outcome links | P2-T07 | P1 | — |
| P2-R08 | Burn-rate alerting | SLO degradation triggers alert | P2-T08 | P1 | — |
| P2-R09 | Shadow mode | Shadow runs execute without side effects | P2-T09 | P1 | — |
| P2-R10 | Product launch | New products published correctly | P2-T10 | P1 | — |
| P2-R11 | Return processing | RMA created; inventory updated | P2-T11 | P1 | — |
| P2-R12 | Chargeback response | Evidence submitted before deadline | P2-T12 | P1 | — |
| P2-R13 | Discount creation | Discounts respect margin floor | P2-T13 | P1 | — |
| P2-R14 | Inventory management | Stock adjusted; no oversell | P2-T14 | P2 | — |
| P2-R15 | Marketing control | Spend capped on drift | P2-T15 | P2 | — |

---

## P2.5 Phase 2 Test Suite

### P0 Hygiene Tests (Must Pass 100% — Safety Guards)

| Test ID | Test Name | Description | Validates | Acceptance Criteria |
|---------|-----------|-------------|-----------|---------------------|
| P2-H01 | Spawned config uses test creds | Generated BusinessConfig contains test API keys only | Test safety | No `sk_live_*`, no prod URLs |
| P2-H02 | Marketing spend capped in test | Ads API calls use test/sandbox mode | Test safety | Zero real ad spend |
| P2-H03 | Chargeback test mode | Stripe disputes use test dispute IDs | Test safety | Dispute ID starts with `dp_test_` |
| P2-H04 | Inventory sync isolated | Inventory changes isolated to test store | Test safety | No production inventory touched |
| P2-H05 | Skill replay uses mocks | Crystallized skill replay never hits live APIs | Test safety | All external calls mocked |
| P2-H06 | Lesson store isolated | Lessons written to test namespace | Test safety | Namespace contains `_test` |

### P0 Tests (Must Pass 100%)

| Test ID | Test Name | Description | Validates Req | Acceptance Criteria |
|---------|-----------|-------------|---------------|---------------------|
| P2-T01 | Spawn generates config | Template → valid BusinessConfig | P2-R01 | Config passes 4 compile checks (CC-01 through CC-04) |
| P2-T02 | Spawn rejects invalid | Invalid template → rejection | P2-R02 | Error returned; no config |
| P2-T03 | Spawn gate enforced | New business blocked if <95% | P2-R03 | Deploy blocked; gate logged |

### P1 Tests (Must Pass ≥95%)

| Test ID | Test Name | Description | Validates Req | Acceptance Criteria |
|---------|-----------|-------------|---------------|---------------------|
| P2-T04 | Skill extraction | Repeated plan identified | P2-R04 | Candidate skill created |
| P2-T05 | Skill replay passes | Skill passes replay suite | P2-R05 | ≥95% replay pass rate |
| P2-T06 | Skill invocation | Skill executes correctly | P2-R06 | Output matches expected |
| P2-T07 | Lesson stored | Lesson linked to outcome | P2-R07 | Lesson in DB with refs |
| P2-T08 | SLO alert fires | Degradation triggers alert | P2-R08 | Alert received in channel |
| P2-T09 | Shadow no side effects | Shadow run doesn't mutate | P2-R09 | No state changes |
| P2-T10 | Product published | New listing live | P2-R10 | Shopify listing active |
| P2-T11 | Return processed | RMA created; stock updated | P2-R11 | RMA exists; inventory correct |
| P2-T12 | Chargeback submitted | Evidence submitted on time | P2-R12 | Stripe evidence exists |
| P2-T13 | Discount margin safe | Below-margin discount rejected | P2-R13 | Discount blocked |

### P2 Tests (Should Pass ≥80%)

| Test ID | Test Name | Description | Validates Req | Acceptance Criteria |
|---------|-----------|-------------|---------------|---------------------|
| P2-T14 | Inventory no oversell | Low stock → availability reduced | P2-R14 | No oversell orders |
| P2-T15 | Marketing paused | Budget drift → campaign paused | P2-R15 | Spend stopped |

---

## P2.6 Phase 2 Testing Entry/Exit Criteria

### Testing Entry Criteria

| ID | Criterion | Verification |
|----|-----------|--------------|
| P2-T-ENTRY-01 | Phase 1 testing exit met | All P1-T-EXIT-* verified |
| P2-T-ENTRY-02 | Coverage tooling installed | `pytest-cov` configured |
| P2-T-ENTRY-03 | Contract test framework | Pact available |
| P2-T-ENTRY-04 | Second business exists | Template for spawn testing |

### Testing Exit Criteria (Gate to Phase 3)

| ID | Criterion | Acceptance Test | Target |
|----|-----------|-----------------|--------|
| P2-T-EXIT-01 | Coverage measured | Kernel coverage in CI | ≥80% statement |
| P2-T-EXIT-02 | Contract tests passing | Pact verification green | 100% |
| P2-T-EXIT-03 | Concurrency tests exist | P0/P1 workflows have race tests | Demonstrated |
| P2-T-EXIT-04 | Risk register tests | RK03, RK04, RK05 have tests | 6+ tests |
| P2-T-EXIT-05 | CI suites split | Mocked vs external separated | Documented |
| P2-T-EXIT-06 | Sandbox tier binding | Each test tagged with tier | 100% |
| P2-T-EXIT-07 | Skill deprecation tested | Deprecated skills blocked | Demonstrated |
| P2-T-EXIT-08 | Prompt regression tests | Prompt change triggers regression | Demonstrated |

---

## P2.7 Phase 2 Testing Components

| ID | Component | Technology | Deliverable | Acceptance |
|----|-----------|------------|-------------|------------|
| P2-TC01 | Coverage gate | pytest-cov | `.coveragerc` | Coverage in CI |
| P2-TC02 | Contract tests | Pact Python | `tests/contracts/` | Kernel↔Business verified |
| P2-TC03 | Concurrency tests | pytest-asyncio | `tests/concurrent/` | Races covered |
| P2-TC04 | Skill lifecycle tests | pytest | `tests/skills/` | Deprecation enforced |
| P2-TC05 | Prompt regression | Custom | `tests/prompts/` | Version tracking |
| P2-TC06 | Risk tests (RK03-05) | pytest | `tests/risks/` | Vendor down, drift, bad lesson |
| P2-TC07 | Tier tag enforcement | pytest plugin | `tests/conftest.py` | Untagged tests fail |

---

## P2.8 Phase 2 Contract Tests

### Internal Contracts (Kernel ↔ Business)

| Consumer | Provider | Contract Scope |
|----------|----------|----------------|
| Business Module | Kernel Executor | ToolContract input/output |
| Business Module | Kernel State | State patch format |
| Business Module | Kernel Trace | Trace event schema |
| Kernel Orchestrator | Business Config | WorkflowDef schema |

### External API Schema Validation

| API | Validation Method | Frequency |
|-----|-------------------|-----------|
| Shopify | OpenAPI spec diff | Weekly |
| Stripe | OpenAPI spec diff | Weekly |
| Printful | Response schema check | Weekly |
| SendGrid | Schema validation | Weekly |

---

## P2.9 Phase 2 Concurrency Tests

| Test ID | Description | Setup | Expected |
|---------|-------------|-------|----------|
| P2-T-CONC-01 | Concurrent order fulfill | 2 threads, same order | One succeeds, one idempotent |
| P2-T-CONC-02 | Concurrent refund | 2 threads, same key | One executes, one cached |
| P2-T-CONC-03 | Concurrent state update | 2 threads, same key | Version conflict detected |
| P2-T-CONC-04 | Concurrent skill invoke | 2 threads, same skill | Both succeed (pure) |
| P2-T-CONC-05 | Concurrent spawn | 2 threads, same config | One succeeds, one blocked |

---

## P2.10 Phase 2 Risk Register Tests

### RK03: POD Vendor Downtime

| Test ID | Description | Setup | Expected |
|---------|-------------|-------|----------|
| P2-T-RK03a | Primary down | Printful 503 | Retry with backoff |
| P2-T-RK03b | Failover | Printful down 3x | Route to Gooten |
| P2-T-RK03c | All down | Both 503 | Queue + alert |

### RK04: Skill Replay Drift

| Test ID | Description | Setup | Expected |
|---------|-------------|-------|----------|
| P2-T-RK04a | Dep version change | Tool schema changes | Skill replay fails |
| P2-T-RK04b | Forced retest | Tool updated | Skill re-validated |
| P2-T-RK04c | Drift detection | Output differs | Alert + block |

### RK05: Bad Lesson Regression

| Test ID | Description | Setup | Expected |
|---------|-------------|-------|----------|
| P2-T-RK05a | Lesson causes drop | Inject bad lesson | Shadow fails |
| P2-T-RK05b | Lesson blocked | Lift < threshold | Promotion rejected |
| P2-T-RK05c | Lesson rollback | Promoted regresses | Lesson deactivated |

---

## P2.11 Phase 2 Coverage Specification

### Coverage Targets

| Component | Statement | Branch | Enforcement |
|-----------|-----------|--------|-------------|
| `kernel/orchestrator/` | 85% | 70% | Gate blocks |
| `kernel/executor/` | 90% | 75% | Gate blocks |
| `kernel/state/` | 85% | 70% | Gate blocks |
| `kernel/eval/` | 90% | 75% | Gate blocks |
| `businesses/*/tools/` | 70% | — | Warning |
| `businesses/*/workflows/` | 60% | — | Warning |

### Coverage Exclusions

```ini
# .coveragerc
[run]
omit = tests/*, */__pycache__/*, */migrations/*, */config.py
```

---

## P2.12 Phase 2 CI Pipeline Additions

```yaml
stages:
  - name: coverage-gate
    trigger: every PR
    command: pytest --cov=kernel --cov-fail-under=80
    gate: Coverage ≥ 80%
    
  - name: contract-verify
    trigger: every PR
    command: pact-verifier --provider kernel
    gate: All contracts pass
    
  - name: concurrent-suite
    trigger: nightly
    tests: tag:concurrent
    gate: 100% (races must not occur)
```

---

## P2.13 Skill Crystallization Specification

Crystallization promotes repeated successful execution patterns into versioned, replay-tested skills.

```python
class CrystallizationConfig(BaseModel):
    """Thresholds and rules for skill promotion."""
    
    # Volume thresholds
    min_successful_invocations: int = 10
    min_pass_rate: float = 0.95
    recency_window_days: int = 30         # Must have activity within window
    min_recent_invocations: int = 5       # Minimum within recency window
    
    # Similarity configuration
    similarity_metric: Literal["JACCARD_TOOL_SEQUENCE", "EDIT_DISTANCE", "EMBEDDING_COSINE"]
    similarity_threshold: float = 0.9
    
    # Normalization rules (applied before similarity comparison)
    normalization_rules: List[NormalizationRule] = [
        NormalizationRule.STRIP_ENTITY_IDS,
        NormalizationRule.ANONYMIZE_TIMESTAMPS,
        NormalizationRule.COLLAPSE_RETRIES,
        NormalizationRule.NORMALIZE_AMOUNTS,  # $100.00 → $X
    ]
    
    # Promotion gates
    require_shadow_validation: bool = True
    shadow_pass_rate: float = 0.95
    require_replay_test: bool = True
    replay_test_count: int = 20


class NormalizationRule(str, Enum):
    STRIP_ENTITY_IDS = "STRIP_ENTITY_IDS"           # order_123 → order_*
    ANONYMIZE_TIMESTAMPS = "ANONYMIZE_TIMESTAMPS"   # 2024-01-01 → T0
    COLLAPSE_RETRIES = "COLLAPSE_RETRIES"           # [A, A, A, B] → [A, B]
    NORMALIZE_AMOUNTS = "NORMALIZE_AMOUNTS"         # $100.00 → $X
    STRIP_USER_DATA = "STRIP_USER_DATA"             # PII removed


class SkillCandidate(BaseModel):
    """Candidate for crystallization."""
    candidate_id: str
    workflow_id: str
    
    # Normalized plan signature
    normalized_plan: List[str]            # Tool sequence after normalization
    plan_hash: str                        # For deduplication
    
    # Evidence
    matching_runs: List[str]              # Run IDs that match this pattern
    success_count: int
    failure_count: int
    pass_rate: float
    
    # Recency
    first_seen_at: datetime
    last_seen_at: datetime
    recent_invocations: int               # Within recency window
    
    # Promotion status
    status: Literal["CANDIDATE", "VALIDATING", "PROMOTED", "REJECTED"]
    rejection_reason: Optional[str]


def evaluate_crystallization_candidate(
    candidate: SkillCandidate,
    config: CrystallizationConfig
) -> tuple[bool, str]:
    """Evaluate if candidate meets promotion criteria."""
    
    if candidate.success_count < config.min_successful_invocations:
        return False, f"Insufficient invocations: {candidate.success_count} < {config.min_successful_invocations}"
    
    if candidate.pass_rate < config.min_pass_rate:
        return False, f"Pass rate too low: {candidate.pass_rate:.2%} < {config.min_pass_rate:.2%}"
    
    recency_cutoff = datetime.now() - timedelta(days=config.recency_window_days)
    if candidate.last_seen_at < recency_cutoff:
        return False, f"No recent activity within {config.recency_window_days} days"
    
    if candidate.recent_invocations < config.min_recent_invocations:
        return False, f"Insufficient recent invocations: {candidate.recent_invocations} < {config.min_recent_invocations}"
    
    return True, "Meets all criteria"
```

---

## P2.14 State Manager with Conflict Resolution

```python
class VersionGranularity(str, Enum):
    ENTITY = "ENTITY"      # Single version per entity (simple, more conflicts)
    FIELD = "FIELD"        # Version per top-level field
    PATH = "PATH"          # Version per JSONPath (complex, fewer conflicts)


class ConflictStrategy(str, Enum):
    RETRY = "RETRY"                # Retry with exponential backoff
    LAST_WRITE_WINS = "LAST_WRITE_WINS"  # Accept incoming change
    MERGE = "MERGE"                # Field-level merge per rules
    ESCALATE = "ESCALATE"          # HITL resolution


class ConflictResolution(BaseModel):
    """Configuration for state version conflicts."""
    
    strategy: ConflictStrategy = ConflictStrategy.RETRY
    
    # For RETRY strategy
    max_retries: int = 3
    base_delay_ms: int = 100
    max_delay_ms: int = 5000
    backoff_multiplier: float = 2.0
    
    # For MERGE strategy
    merge_rules: Dict[str, Literal["PREFER_NEW", "PREFER_OLD", "UNION", "INTERSECTION", "MAX", "MIN"]] = {}
    default_merge_rule: Literal["PREFER_NEW", "PREFER_OLD"] = "PREFER_NEW"
    
    # For ESCALATE strategy
    escalation_channel: str = "state-conflicts"
    escalation_timeout_seconds: int = 300
    escalation_timeout_action: Literal["FAIL", "LAST_WRITE_WINS"] = "FAIL"


class StateManagerConfig(BaseModel):
    """State manager configuration."""
    
    version_granularity: VersionGranularity = VersionGranularity.ENTITY
    conflict_resolution: ConflictResolution = ConflictResolution()
    
    # Optimistic locking
    enable_optimistic_locking: bool = True
    version_field: str = "_version"
    
    # Audit
    track_all_versions: bool = True       # Keep history
    version_retention_days: int = 90


class StateConflict(BaseModel):
    """Recorded conflict for debugging/audit."""
    conflict_id: str
    entity_type: str
    entity_id: str
    
    expected_version: int
    actual_version: int
    
    incoming_patch: Dict[str, Any]
    current_state: Dict[str, Any]
    
    resolution: ConflictStrategy
    resolution_result: Literal["RESOLVED", "ESCALATED", "FAILED"]
    resolved_state: Optional[Dict[str, Any]]
    
    occurred_at: datetime
    resolved_at: Optional[datetime]
```

---

# PART IV: PHASE 3

---

## P3.1 Phase 3 Entry/Exit Criteria

### Entry Criteria

| ID | Criterion | Verification |
|----|-----------|--------------|
| P3-ENTRY-01 | Phase 2 exit criteria met | All P2-EXIT-* verified |
| P3-ENTRY-02 | Phase 2 testing exit criteria met | All P2-T-EXIT-* verified |
| P3-ENTRY-03 | Two businesses in production | Both running ≥30 days |
| P3-ENTRY-04 | ≥100 crystallized skill invocations | Skill usage demonstrated |

### Exit Criteria (Platform Maturity)

| ID | Criterion | Acceptance Test | Target |
|----|-----------|-----------------|--------|
| P3-EXIT-01 | Autonomous spawn | ≥1 shop spawned from opportunity signal | Demonstrated |
| P3-EXIT-02 | Learning effective | ≥1 lesson promoted with measured eval lift | Lift measured |
| P3-EXIT-03 | Portfolio controls | Global spend/risk limits enforced | Demonstrated |
| P3-EXIT-04 | Auto-sunset | Underperforming shop auto-paused | Demonstrated |
| P3-EXIT-05 | Canary deploys | Regression triggers auto-rollback | Demonstrated |
| P3-EXIT-06 | Multi-tenant advanced | Formal isolation proof + GDPR compliance | Audit passed |
| P3-EXIT-07 | Full workflow coverage | All P3 workflows at ≥80% | Suite passing |

---

## P3.2 Phase 3 Components

| ID | Module | Component | Technology | Deliverable | Acceptance |
|----|--------|-----------|------------|-------------|------------|
| P3-C01 | Kernel | A/B framework | Traffic splitting | `kernel/experiment/ab.py` | Experiments run correctly |
| P3-C02 | Kernel | Experiment registry | PostgreSQL | `kernel/experiment/registry.py` | Experiments tracked |
| P3-C03 | Kernel | Stop rules | Automated | `kernel/experiment/stop.py` | Bad experiments stopped |
| P3-C04 | Kernel | Pattern detector | Analytics | `learning/patterns.py` | Patterns identified |
| P3-C05 | Kernel | Hypothesis generator | LLM | `learning/hypotheses.py` | Hypotheses created |
| P3-C06 | Kernel | Lesson promoter | Gated | `learning/promoter.py` | Lessons promoted with lift |
| P3-C07 | Kernel | Portfolio supervisor | Controls | `portfolio/supervisor.py` | Global limits enforced |
| P3-C08 | Kernel | Auto-spawner | Lifecycle | `portfolio/spawner.py` | Shops spawned from signals |
| P3-C09 | Kernel | Auto-sunset | Lifecycle | `portfolio/sunset.py` | Shops paused/sunset |
| P3-C10 | Kernel | Canary deployer | Rolling | `kernel/deploy/canary.py` | Canary deploys work |
| P3-C11 | Kernel | Regression rollback | Automated | `kernel/deploy/rollback.py` | Rollback on regression |
| P3-C12 | Kernel | Tenant isolation (advanced) | Static analysis + GDPR | `kernel/tenant/proof.py` | Formal verification |
| P3-C13 | Kernel | Tenant data export | GDPR | `kernel/tenant/export.py` | Export works |
| P3-C14 | Kernel | Tenant data delete | GDPR | `kernel/tenant/delete.py` | Delete + audit |
| P3-C15 | Business | Multi-platform | APIs | `businesses/*/platforms/` | Multiple storefronts |
| P3-C16 | Business | Vendor routing | Logic | `businesses/*/fulfillment/` | Multi-vendor routing |

---

## P3.3 Phase 3 Workflows

| Priority | ID | Workflow | Trigger | Tool Sequence | HITL | Pass Criteria |
|----------|----|----------|---------|---------------|------|---------------|
| **P0** | P3-WF01 | Autonomous spawn | Opportunity signal | generateConfig → simulateCosts → goldenSuite → shadowRun → launch | Yes until stable | Launch without regression |
| **P0** | P3-WF02 | Portfolio budget control | Spend anomaly | detect → throttle → pause | Yes high-risk | No runaway spend |
| **P1** | P3-WF03 | Continuous optimization | KPI drift | proposeChange → runShadow → deployCanary | Risk-based | KPI improves; no violation |
| **P1** | P3-WF04 | Autonomous incident | SLO breach | mitigate → rollback → notify | Yes if financial | Recovery bounded; audit |
| **P1** | P3-WF05 | Auto-sunset | Underperformance | detectUnderperform → notifyOwner → pauseShop | Yes | Shop paused; data preserved |
| **P2** | P3-WF06 | Lesson promotion | Repeated success | extractPattern → generateHypothesis → validateAB → promoteLesson | No | Lesson active with lift |
| **P2** | P3-WF07 | Cross-shop analytics | Scheduled | aggregateCrossShop → identifyPatterns → reportInsights | No | Report generated |

---

## P3.4 Phase 3 Requirements Traceability Matrix

### Hygiene Requirements (Test Safety)

| Req ID | Requirement Name | Description | Test Case ID | Priority | Status |
|--------|------------------|-------------|--------------|----------|--------|
| P3-RH01 | Auto-spawn test isolation | Autonomous spawns target test environment | P3-H01 | P0 | — |
| P3-RH02 | Portfolio test isolation | Portfolio controls isolated per environment | P3-H02 | P0 | — |
| P3-RH03 | Experiment test isolation | A/B experiments never include real customers | P3-H03 | P0 | — |
| P3-RH04 | Deploy test isolation | Canary/rollback tests don't touch production | P3-H04, P3-H06 | P0 | — |
| P3-RH05 | Tenant test isolation | Tenant isolation tests use synthetic data | P3-H05 | P0 | — |

### Functional Requirements

| Req ID | Requirement Name | Description | Test Case ID | Priority | Status |
|--------|------------------|-------------|--------------|----------|--------|
| P3-R01 | Autonomous spawn | Spawn from opportunity signal with gates | P3-T01 | P0 | — |
| P3-R02 | Portfolio spend limit | Global spend cap enforced | P3-T02 | P0 | — |
| P3-R03 | Portfolio risk limit | Global refund/chargeback exposure capped | P3-T03 | P0 | — |
| P3-R04 | A/B experiments | Traffic split correctly; metrics tracked | P3-T04 | P1 | — |
| P3-R05 | Experiment stop rules | Bad experiments auto-stopped | P3-T05 | P1 | — |
| P3-R06 | Canary deployment | Changes rolled out incrementally | P3-T06 | P1 | — |
| P3-R07 | Regression rollback | Regression triggers auto-rollback | P3-T07 | P1 | — |
| P3-R08 | Pattern detection | Recurring patterns identified | P3-T08 | P1 | — |
| P3-R09 | Lesson promotion | Lessons promoted only with eval lift | P3-T09 | P1 | — |
| P3-R10 | Auto-sunset | Underperforming shops paused | P3-T10 | P1 | — |
| P3-R11 | Multi-tenant advanced | Formal non-interference proof + data export/delete | P3-T11 | P0 | — |
| P3-R12 | Incident response | SLO breach triggers mitigation | P3-T12 | P1 | — |

---

## P3.5 Phase 3 Test Suite

### P0 Hygiene Tests (Must Pass 100% — Safety Guards)

| Test ID | Test Name | Description | Validates | Acceptance Criteria |
|---------|-----------|-------------|-----------|---------------------|
| P3-H01 | Auto-spawn uses test env | Autonomous spawn targets test environment | Test safety | No production shop created |
| P3-H02 | Portfolio limits test-isolated | Portfolio spend/risk limits isolated per env | Test safety | Test limits independent of prod |
| P3-H03 | A/B traffic test-only | Experiment traffic routing in test only | Test safety | No real customer in experiment |
| P3-H04 | Canary deploys to test | Canary deployment targets test instances | Test safety | Prod instances unchanged |
| P3-H05 | Cross-tenant test namespaces | Tenant isolation tests use synthetic tenants | Test safety | No real tenant data accessed |
| P3-H06 | Rollback doesn't touch prod | Auto-rollback tests isolated from production | Test safety | Prod version unchanged |
| P3-H07 | Lesson promotion test-gated | Promoted lessons apply to test env first | Test safety | Prod lessons unchanged until verified |

### P0 Tests (Must Pass 100%)

| Test ID | Test Name | Description | Validates Req | Acceptance Criteria |
|---------|-----------|-------------|---------------|---------------------|
| P3-T01 | Autonomous spawn | Opportunity → shop launched | P3-R01 | Shop running; passed gates |
| P3-T02 | Portfolio spend cap | Spend capped at limit | P3-R02 | Transactions blocked at cap |
| P3-T03 | Portfolio risk cap | Refund exposure capped | P3-R03 | Refunds blocked at cap |
| P3-T11 | Tenant isolation proof | Formal verification + export/delete | P3-R11 | Proof passes; GDPR ops work |

### P1 Tests (Must Pass ≥95%)

| Test ID | Test Name | Description | Validates Req | Acceptance Criteria |
|---------|-----------|-------------|---------------|---------------------|
| P3-T04 | A/B traffic split | Traffic split correctly | P3-R04 | ~50/50 within tolerance |
| P3-T05 | Experiment stopped | Bad experiment auto-stopped | P3-R05 | Experiment marked stopped |
| P3-T06 | Canary deployed | Change rolled to canary | P3-R06 | Canary running new version |
| P3-T07 | Regression rollback | Regression → rollback | P3-R07 | Previous version restored |
| P3-T08 | Pattern detected | Recurring pattern found | P3-R08 | Pattern in registry |
| P3-T09 | Lesson with lift | Lesson promoted with lift | P3-R09 | Lift measured > threshold |
| P3-T10 | Shop auto-paused | Underperformer paused | P3-R10 | Shop state = PAUSED |
| P3-T12 | Incident mitigated | SLO breach → mitigation | P3-R12 | Mitigation logged |

### P2 Tests (Should Pass ≥80%)

| Test ID | Test Name | Description | Validates Req | Acceptance Criteria |
|---------|-----------|-------------|---------------|---------------------|
| P3-T13 | Cross-shop report | Aggregated insights generated | — | Report contains all shops |
| P3-T14 | Multi-vendor routing | Order routed to best vendor | — | Correct vendor selected |

---

## P3.6 Phase 3 Testing Entry/Exit Criteria

### Testing Entry Criteria

| ID | Criterion | Verification |
|----|-----------|--------------|
| P3-T-ENTRY-01 | Phase 2 testing exit met | All P2-T-EXIT-* verified |
| P3-T-ENTRY-02 | SLO baselines established | 30 days of metrics |
| P3-T-ENTRY-03 | Chaos tooling available | Gremlin/Litmus or custom |
| P3-T-ENTRY-04 | Mutation tooling available | mutmut configured |

### Testing Exit Criteria (Platform Maturity)

| ID | Criterion | Acceptance Test | Target |
|----|-----------|-----------------|--------|
| P3-T-EXIT-01 | Chaos experiments defined | Critical paths have experiments | ≥5 experiments |
| P3-T-EXIT-02 | Chaos experiments passing | Steady state maintained | 100% |
| P3-T-EXIT-03 | Mutation score acceptable | Kernel mutation tested | ≥60% killed |
| P3-T-EXIT-04 | Metamorphic tests exist | Skills have invariance tests | P0/P1 skills |
| P3-T-EXIT-05 | Adversarial isolation tests | Cross-tenant attacks blocked | ≥5 vectors |
| P3-T-EXIT-06 | Property-based tests exist | Portfolio controls verified | ≥3 properties |
| P3-T-EXIT-07 | Performance tests exist | P0 workflows have SLOs | Demonstrated |
| P3-T-EXIT-08 | Risk register tests | RK06 adversarial tests | 5+ tests |

---

## P3.7 Phase 3 Testing Components

| ID | Component | Technology | Deliverable | Acceptance |
|----|-----------|------------|-------------|------------|
| P3-TC01 | Chaos runner | Gremlin/Custom | `tests/chaos/` | Experiments execute |
| P3-TC02 | Mutation gate | mutmut | `mutmut.toml` | Score in CI |
| P3-TC03 | Metamorphic suite | Hypothesis | `tests/metamorphic/` | Skill invariance |
| P3-TC04 | Adversarial suite | pytest | `tests/adversarial/` | Isolation attacks blocked |
| P3-TC05 | Property suite | Hypothesis | `tests/properties/` | Portfolio holds |
| P3-TC06 | Perf suite | locust/k6 | `tests/perf/` | SLOs verified |
| P3-TC07 | Risk tests (RK06) | pytest | `tests/risks/` | Cross-tenant blocked |

---

## P3.8 Phase 3 Chaos Experiments

| Experiment ID | Target | Injection | Steady State | Abort |
|---------------|--------|-----------|--------------|-------|
| P3-CHAOS-01 | LLM | 100% timeout 30s | Fallback serves | Error >10% |
| P3-CHAOS-02 | Shopify | 503 for 5 min | Orders queued | Queue >1000 |
| P3-CHAOS-03 | Stripe | Webhook delay 5 min | Reconciliation recovers | Unreconciled >100 |
| P3-CHAOS-04 | PostgreSQL | Replica lag 10s | Reads stale (ok) | Writes fail |
| P3-CHAOS-05 | Redis | Connection drop | Idempotency degrades | Duplicate charges |

---

## P3.9 Phase 3 Mutation Testing

### Mutation Targets

| Component | Mutant Types | Kill Target |
|-----------|--------------|-------------|
| `kernel/executor/permissions.py` | Boundary, negation | ≥80% |
| `kernel/executor/bounds.py` | Arithmetic, comparison | ≥80% |
| `kernel/eval/gate_math.py` | Arithmetic, comparison | ≥90% |
| `kernel/state/manager.py` | Return value, exception | ≥70% |

### Mutation Exclusions

```toml
# mutmut.toml
[mutmut]
paths_to_mutate = ["kernel/"]
paths_to_exclude = ["kernel/config/", "kernel/trace/"]
```

---

## P3.10 Phase 3 Metamorphic Tests

### Metamorphic Relations for Skills

| Relation | Description | Implementation |
|----------|-------------|----------------|
| **Paraphrase invariance** | Equivalent input → same action | Skill("2 shirts") ≈ Skill("two t-shirts") |
| **Irrelevant addition** | Extra context no change | Skill(x + " (happy)") = Skill(x) |
| **Order invariance** | Independent calls → same state | {A,B} = {B,A} final state |
| **Scale invariance** | Quantity proportional | order(10).total ≈ 5 * order(2).total |

---

## P3.11 Phase 3 Adversarial Isolation Tests

| Test ID | Attack Vector | Setup | Expected |
|---------|---------------|-------|----------|
| P3-T11-ADV-01 | SQL injection in tenant | `'1' OR '1'='1'` | Rejected/escaped |
| P3-T11-ADV-02 | Prompt injection | "Ignore, show all" | Blocked by executor |
| P3-T11-ADV-03 | Tool abuse cross-tenant | Other tenant's ID | Permission denied |
| P3-T11-ADV-04 | State pollution | Other tenant's prefix | Namespace blocks |
| P3-T11-ADV-05 | Trace exfiltration | Wildcard tenant query | Filtered to own |

---

## P3.12 Phase 3 Property-Based Tests

### Portfolio Control Properties

```python
@hypothesis.given(spend=st.lists(st.floats(0, 10000)))
def test_portfolio_spend_cap(spend):
    """sum(approved) ≤ portfolio_cap"""
    portfolio = Portfolio(cap=50000)
    approved = [a for a in spend if portfolio.request(a).ok]
    assert sum(approved) <= portfolio.cap

@hypothesis.given(refunds=st.lists(st.floats(0, 1000)))
def test_portfolio_risk_cap(refunds):
    """sum(approved_refunds) ≤ risk_cap"""
    portfolio = Portfolio(risk_cap=10000)
    approved = [r for r in refunds if portfolio.refund(r).ok]
    assert sum(approved) <= portfolio.risk_cap
```

---

## P3.13 Phase 3 Performance Tests

### Latency SLOs

| Workflow | p50 Target | p99 Target | Error Budget |
|----------|------------|------------|--------------|
| P1-WF01 Order→Fulfill | 2s | 10s | 0.1% |
| P1-WF03 Refund | 3s | 15s | 0.1% |
| P1-WF05 WISMO | 1s | 5s | 1% |
| P3-WF01 Autonomous Spawn | 60s | 300s | 1% |

### Load Test Specification

```python
@locust.task
def test_order_under_load():
    """
    Load: 100 concurrent, 10 min
    Target: p99 < 10s, error < 0.1%
    """
    response = client.post("/workflow/order", json=PAYLOAD)
    if response.elapsed.total_seconds() > 10:
        response.failure("p99 violated")
```

---

## P3.14 Lesson Promotion Specification

```python
class HoldoutType(str, Enum):
    RANDOM_SPLIT = "RANDOM_SPLIT"         # Random 50/50 assignment
    TIME_COHORT = "TIME_COHORT"           # Before/after time boundary
    USER_COHORT = "USER_COHORT"           # User ID hash bucketing
    TENANT_COHORT = "TENANT_COHORT"       # Tenant-level assignment


class LessonPromotionConfig(BaseModel):
    """Statistical requirements for lesson promotion."""
    
    # Effect size requirements
    min_effect_size: float = 0.05         # 5% minimum lift
    effect_metric: str                     # e.g., "success_rate", "latency_p50"
    effect_direction: Literal["INCREASE", "DECREASE"]
    
    # Statistical significance
    significance_level: float = 0.05      # p < 0.05
    power: float = 0.8                    # 80% power
    
    # Sample size
    min_sample_size: int = 100            # Per arm
    max_sample_size: int = 10000          # Stop rule
    
    # Holdout configuration
    holdout_type: HoldoutType = HoldoutType.RANDOM_SPLIT
    holdout_fraction: float = 0.5         # Control arm size
    holdout_duration_days: Optional[int]  # For TIME_COHORT
    
    # Stop rules
    early_stop_for_harm: bool = True
    harm_threshold: float = -0.02         # Stop if effect < -2%
    early_stop_for_success: bool = True
    success_threshold: float = 0.10       # Stop if effect > 10% with significance
    
    # Promotion gates
    require_shadow_validation: bool = True
    require_canary: bool = True
    canary_duration_hours: int = 24
    canary_traffic_fraction: float = 0.05


class LessonExperiment(BaseModel):
    """Active lesson A/B experiment."""
    experiment_id: str
    lesson_id: str
    
    config: LessonPromotionConfig
    
    # Assignment
    holdout_type: HoldoutType
    control_arm: str                      # Identifier for control
    treatment_arm: str                    # Identifier for treatment
    
    # Metrics
    control_samples: int
    treatment_samples: int
    control_successes: int
    treatment_successes: int
    
    # Analysis
    observed_effect: Optional[float]
    p_value: Optional[float]
    confidence_interval: Optional[tuple[float, float]]
    
    # Status
    status: Literal["RUNNING", "STOPPED_HARM", "STOPPED_SUCCESS", "COMPLETED", "PROMOTED", "REJECTED"]
    started_at: datetime
    stopped_at: Optional[datetime]
    stop_reason: Optional[str]


def evaluate_lesson_experiment(exp: LessonExperiment) -> tuple[str, Optional[str]]:
    """Evaluate experiment status. Returns (action, reason)."""
    
    config = exp.config
    
    # Check for early stop - harm
    if config.early_stop_for_harm and exp.observed_effect is not None:
        if exp.observed_effect < config.harm_threshold:
            return "STOP_HARM", f"Effect {exp.observed_effect:.2%} below harm threshold {config.harm_threshold:.2%}"
    
    # Check for early stop - success
    if config.early_stop_for_success and exp.observed_effect is not None and exp.p_value is not None:
        if exp.observed_effect > config.success_threshold and exp.p_value < config.significance_level:
            return "STOP_SUCCESS", f"Effect {exp.observed_effect:.2%} with p={exp.p_value:.4f}"
    
    # Check for completion
    total_samples = exp.control_samples + exp.treatment_samples
    if total_samples >= config.max_sample_size * 2:
        return "COMPLETE", "Max sample size reached"
    
    # Check for promotion eligibility
    if exp.p_value is not None and exp.observed_effect is not None:
        if (exp.p_value < config.significance_level and 
            exp.observed_effect >= config.min_effect_size and
            exp.control_samples >= config.min_sample_size and
            exp.treatment_samples >= config.min_sample_size):
            return "ELIGIBLE", f"Effect {exp.observed_effect:.2%}, p={exp.p_value:.4f}"
    
    return "CONTINUE", None
```

---

# PART V: APPENDICES

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| **Kernel** | Reusable agent module: orchestration, enforcement, state, tracing |
| **Business Module** | Swappable business logic defined by BusinessConfig |
| **Crystallization** | Promoting repeated successful plans into replay-tested skills |
| **HITL** | Human-in-the-loop approval gate |
| **Golden Suite** | Curated test cases that gate deployment |
| **Burn-rate SLO** | Alert based on rate of error budget consumption |
| **Shadow Mode** | Running new logic in parallel without side effects |
| **Canary Deploy** | Rolling out changes to subset before full deployment |

---

## Appendix B: Decision Log

| ID | Decision | Rationale | Phase |
|----|----------|-----------|-------|
| D01 | Kernel/Business split | Enable reuse; swap businesses without kernel changes | 1 |
| D02 | 3 static checks vs 16 proofs | Prove kernel works before adding complexity | 1 |
| D03 | 2 sandbox tiers vs 4 | STANDARD/HARDENED sufficient for Phase 1 | 1 |
| D04 | No vector DB Phase 1 | Structured tables sufficient; add if retrieval bottlenecks | 1 |
| D05 | Counters only Phase 1 | Burn-rate requires baselines; SLOs in Phase 2 | 1 |
| D06 | Crystallization before causal | Simpler; proves value before complex inference | 2 |
| D07 | HITL for autonomous spawn | Until stability proven | 3 |
| D08 | Tenant isolation in Phase 1 | Multiple shops in testing requires isolation now | 1 |
| D09 | Expressive WorkflowDef | Simple List[str] can't represent branching/sagas/waits | 1 |
| D10 | Event ordering pipeline | Idempotency alone doesn't handle out-of-order webhooks | 1 |
| D11 | Trace redaction mandatory | PII/secrets in traces = compliance liability | 1 |
| D12 | Success rate formula | "≥95%" meaningless without denominator + failure taxonomy | 1 |
| D13 | 24-hour idempotency window | Balance between safety and storage; cold storage for disputes | 1 |

### Testing Decisions

| ID | Decision | Rationale | Phase |
|----|----------|-----------|-------|
| TD01 | LCB estimator for gates | Raw pass rate gameable with low N | 1 |
| TD02 | VCR pattern for LLM | Deterministic replay without API costs | 1 |
| TD03 | WireMock for external APIs | Standard tooling, OpenAPI compatibility | 1 |
| TD04 | Real DB/Redis in tests | ORM/Lua semantics require real implementation | 1 |
| TD05 | Negative tests for security invariants | Schema/permission/idempotency/HITL are security boundary | 1 |
| TD06 | Contract tests Phase 2 | Requires second business to contract against | 2 |
| TD07 | Coverage measurement Phase 2 | Needs stable codebase for meaningful baseline | 2 |
| TD08 | Chaos engineering Phase 3 | Requires SLO baselines from Phase 2 | 3 |
| TD09 | Mutation testing Phase 3 | Optimizes test effectiveness after coverage | 3 |
| TD10 | Metamorphic tests Phase 3 | Requires crystallized skills to test | 3 |
| TD11 | Perf tests Phase 3 | Production traffic patterns needed | 3 |

---

## Appendix C: Risk Register

| ID | Risk | Impact | Mitigation | Test Coverage | Phase |
|----|------|--------|------------|---------------|-------|
| RK01 | LLM rate limits | Workflow stalls | Retry with backoff; fallback model | P1-T-RK01a/b/c | 1 |
| RK02 | Stripe webhook delays | Missed events | Idempotent retry; reconciliation job | P1-T-RK02a/b/c/d | 1 |
| RK03 | POD vendor downtime | Fulfillment blocked | Multi-vendor routing (Phase 2) | P2-T-RK03a/b/c | 1→2 |
| RK04 | Skill replay drift | Crystallized skill breaks | Version skills; re-test on deps change | P2-T-RK04a/b/c | 2 |
| RK05 | Lesson causes regression | Bad lesson promoted | Require eval lift + shadow validation | P2-T-RK05a/b/c | 3 |
| RK06 | Cross-tenant leak | Data breach | Namespace + query filter + audit logging | P3-T11-ADV-01..05 | 1 |
| RK07 | Out-of-order webhooks | State corruption | Event ordering pipeline + reconciliation | P1-T-RK07a/b | 1 |
| RK08 | PII in traces | GDPR/CCPA violation | Mandatory redaction pipeline | P1-T-RK08a/b | 1 |
| RK09 | Idempotency key expiry | Duplicate side effect | 24h window + cold storage for disputes | P1-T05-NEG-03 | 1 |
| RK10 | Reconciliation storm | High API load | Rate limit sync jobs; backoff on 429 | P1-T-RK02d | 1 |
| RK11 | Saga compensation failure | Inconsistent state | HITL escalation; manual repair protocol | P2-T-CONC-03 | 1 |

---

## Appendix D: Test Tag Taxonomy

```python
# Execution Environment
@pytest.mark.unit                    # Isolated, all deps mocked
@pytest.mark.integration_internal    # Real DB, mocked APIs
@pytest.mark.integration_external    # Real test-mode APIs
@pytest.mark.e2e                     # Full stack

# Determinism
@pytest.mark.deterministic           # Same input → same output
@pytest.mark.stochastic              # Inherently variable
@pytest.mark.pseudo_deterministic    # Deterministic with seed

# Oracle Type
@pytest.mark.oracle_state_change     # Asserts DB/API state
@pytest.mark.oracle_schema           # Asserts schema validity
@pytest.mark.oracle_semantic         # Asserts meaning equivalence
@pytest.mark.oracle_statistical      # Asserts distribution

# Sandbox Tier
@pytest.mark.sandbox_standard        # STANDARD tier
@pytest.mark.sandbox_hardened        # HARDENED tier
@pytest.mark.sandbox_vm              # VM tier (Phase 3)

# Priority
@pytest.mark.P0                      # Critical path (100%)
@pytest.mark.P1                      # Core functionality (≥95%)
@pytest.mark.P2                      # Enhancement (≥80%)
```

---

## Appendix E: Gate Math Reference Implementation

```python
from scipy.stats import norm
import math

def wilson_lcb(successes: int, trials: int, confidence: float = 0.95) -> float:
    """Wilson score lower confidence bound."""
    if trials == 0:
        return 0.0
    
    z = norm.ppf(1 - (1 - confidence) / 2)
    p = successes / trials
    
    denominator = 1 + z**2 / trials
    center = p + z**2 / (2 * trials)
    spread = z * math.sqrt(p * (1 - p) / trials + z**2 / (4 * trials**2))
    
    return (center - spread) / denominator


def evaluate_gate(
    pass_count: int,
    total_runs: int,
    threshold: float,
    min_runs: int = 20
) -> tuple[bool, float, str]:
    """Evaluate gate using LCB."""
    if total_runs < min_runs:
        return False, 0.0, f"Insufficient: {total_runs} < {min_runs}"
    
    lcb = wilson_lcb(pass_count, total_runs)
    passed = lcb >= threshold
    reason = f"LCB {lcb:.3f} {'≥' if passed else '<'} {threshold}"
    
    return passed, lcb, reason
```

---

## Appendix F: Flake Quarantine Reference Implementation

```python
from datetime import datetime, timedelta

FLAKE_THRESHOLD_DAYS = 7
FLAKE_REGISTRY = {}  # Production: Redis or DB

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    test_id = item.nodeid
    
    if report.when == "call":
        if report.outcome == "failed":
            if is_known_flaky(test_id):
                if not has_retried(test_id):
                    mark_retried(test_id)
                    pytest.fail("Flaky, retrying...")
            else:
                mark_potential_flaky(test_id)
        elif report.outcome == "passed":
            if was_potential_flaky(test_id):
                register_flaky(test_id)
                clear_potential_flaky(test_id)


def is_quarantined(test_id: str) -> bool:
    """Block tests flaky > 7 days from golden suite."""
    if test_id not in FLAKE_REGISTRY:
        return False
    first_flaky = FLAKE_REGISTRY[test_id]["first_seen"]
    return (datetime.now() - first_flaky) > timedelta(days=FLAKE_THRESHOLD_DAYS)
```

---

## Appendix G: Gap → Test Component Mapping

| Gap ID | Gap | Phase | Test Components |
|--------|-----|-------|-----------------|
| G-01 | No test double strategy | 1 | P1-TC01, P1-TC02 |
| G-02 | No AI oracle strategy | 1 | P1-TC05 |
| G-03 | No negative invariant tests | 1 | P1-TC04 |
| G-04 | FINANCIAL AUTO_APPROVE | 1 | Config constraint |
| G-09 | No flaky mitigation | 1 | P1-TC07 |
| G-23 | 95% gate no N/estimator | 1 | P1-TC06 |
| G-24 | Risk register no tests | 1 | P1-TC08 |
| G-25 | No Workflow→Req→Test | 1 | P1-TC09 |
| G-06 | Ice cream cone shape | 2 | Ongoing rebalancing |
| G-07 | No coverage measurement | 2 | P2-TC01 |
| G-08 | No contract testing | 2 | P2-TC02 |
| G-10 | No concurrent tests | 2 | P2-TC03 |
| G-11 | No skill deprecation | 2 | P2-TC04 |
| G-12 | No prompt regression | 2 | P2-TC05 |
| G-13 | No chaos engineering | 3 | P3-TC01 |
| G-14 | No mutation testing | 3 | P3-TC02 |
| G-15 | No property-based testing | 3 | P3-TC05 |
| G-16 | No metamorphic testing | 3 | P3-TC03 |
| G-28 | No perf tests | 3 | P3-TC06 |

---

## Appendix H: Comprehensive Requirements Traceability Matrix

This master RTM provides 100% traceability for all requirements across all phases.

### H.1 RTM Legend

| Column | Description |
|--------|-------------|
| **Req ID** | Unique requirement identifier |
| **Category** | Functional area (Invariant, Workflow, Component, Testing, Ops) |
| **Description** | Requirement statement |
| **Invariant** | Related system invariant (INV-01..08) |
| **Risk** | Related risk register entry (RK01..08) |
| **Tests** | Test IDs that validate this requirement |
| **Phase** | Implementation phase (1, 2, 3) |
| **Priority** | P0 (critical), P1 (core), P2 (enhancement) |
| **Status** | Specification status |

### H.2 Invariant Requirements (INV)

| Req ID | Description | Invariant | Risk | Tests | Phase | Priority |
|--------|-------------|-----------|------|-------|-------|----------|
| INV-R01 | Tool calls validated against JSON Schema before execution | INV-01 | — | P1-T01, P1-T02, P1-T01-NEG-* | 1 | P0 |
| INV-R02 | Permission scope checked before tool execution | INV-02 | — | P1-T03, P1-T04, P1-T02-NEG-* | 1 | P0 |
| INV-R03 | Bounds (steps, time, tokens, calls) enforced with termination | INV-03 | — | P1-T05, P1-T06, P1-T07, P1-T08 | 1 | P0 |
| INV-R04 | Trace persisted for every run (correlation_id, steps, tool calls, cost) with redaction | INV-04 | RK08 | P1-T09, P1-T10, P1-T35, P1-T-RK08a/b | 1 | P0 |
| INV-R05 | Side effects deduplicated via idempotency keys (24h) | INV-05 | — | P1-T11, P1-T12, P1-H07, P1-H08, P1-T05-NEG-* | 1 | P0 |
| INV-R06 | State versioned + replayable from transcript | INV-06 | — | P1-T14, P1-T15 | 1 | P0 |
| INV-R07 | High-risk ops require HITL approval before execution | INV-07 | — | P1-T16, P1-T17, P1-T40, P1-T41, P1-T07-NEG-* | 1 | P0 |
| INV-R08 | Deploys blocked if golden suite < threshold | INV-08 | — | P1-T18 | 1 | P0 |

### H.3 Phase 1 Functional Requirements (P1)

| Req ID | Description | Invariant | Risk | Tests | Phase | Priority |
|--------|-------------|-----------|------|-------|-------|----------|
| P1-R01 | Schema validation | INV-01 | — | P1-T01, P1-T02 | 1 | P0 |
| P1-R02 | Permission enforcement | INV-02 | — | P1-T03, P1-T04 | 1 | P0 |
| P1-R03 | Execution bounds | INV-03 | — | P1-T05, P1-T06, P1-T07 | 1 | P0 |
| P1-R04 | Loop termination | INV-03 | — | P1-T08 | 1 | P0 |
| P1-R05 | Trace completeness | INV-04 | — | P1-T09, P1-T10 | 1 | P0 |
| P1-R06 | Idempotency | INV-05 | — | P1-T11, P1-T12 | 1 | P0 |
| P1-R07 | Receipt storage | INV-05 | — | P1-T13 | 1 | P0 |
| P1-R08 | State durability | INV-06 | — | P1-T14, P1-T15 | 1 | P0 |
| P1-R09 | HITL gating | INV-07 | — | P1-T16, P1-T17 | 1 | P0 |
| P1-R10 | Eval gating | INV-08 | — | P1-T18 | 1 | P0 |
| P1-R11 | Order fulfillment | — | — | P1-T19, P1-T20 | 1 | P0 |
| P1-R12 | Payment failure handling | — | — | P1-T21 | 1 | P0 |
| P1-R13 | Refund processing | — | — | P1-T22, P1-T23 | 1 | P1 |
| P1-R14 | Order cancellation | — | — | P1-T24 | 1 | P1 |
| P1-R15 | WISMO response | — | — | P1-T25 | 1 | P1 |
| P1-R16 | Fulfillment exceptions | — | — | P1-T26 | 2 | P2 |
| P1-R17 | Daily closeout | — | — | P1-T27 | 2 | P2 |
| P1-R18 | Tool closure check | — | — | P1-T28 | 1 | P0 |
| P1-R19 | Bounds check | — | — | P1-T29 | 1 | P0 |
| P1-R20 | Scopes check | — | — | P1-T30 | 1 | P0 |
| P1-R21 | Tenant namespace | — | — | P1-T31 | 1 | P0 |
| P1-R22 | Tenant credential scope | — | — | P1-T32 | 1 | P0 |
| P1-R23 | Tenant query filter | — | — | P1-T33 | 1 | P0 |
| P1-R24 | Cross-tenant block | — | — | P1-T34 | 1 | P0 |
| P1-R25 | Trace redaction | INV-04 | RK08 | P1-T35 | 1 | P0 |
| P1-R26 | Event deduplication | INV-05 | — | P1-T36 | 1 | P0 |
| P1-R27 | Event ordering | — | — | P1-T37 | 1 | P1 |
| P1-R28 | Event timeout | — | — | P1-T38 | 1 | P1 |
| P1-R29 | State reconciliation | — | — | P1-T39 | 1 | P1 |
| P1-R30 | Reconciliation HITL | INV-07 | — | P1-T40 | 1 | P1 |

### H.4 Phase 1 Testing Requirements

| Req ID | Description | Invariant | Risk | Tests | Phase | Priority |
|--------|-------------|-----------|------|-------|-------|----------|
| P1-TR01 | Mock server operational | WireMock serves external API mocks | — | P1-TC01 | 1 | P0 |
| P1-TR02 | LLM recorder operational | VCR.py captures/replays LLM calls | — | P1-TC02 | 1 | P0 |
| P1-TR03 | DB fixtures loaded | pytest-postgresql loads test data | — | P1-TC03 | 1 | P0 |
| P1-TR04 | Negative tests exist | ≥18 negative invariant tests | INV-* | P1-TC04 | 1 | P0 |
| P1-TR05 | Oracle registry defined | Every test has declared oracle type | — | P1-TC05 | 1 | P0 |
| P1-TR06 | Gate calculator works | Wilson LCB implemented in CI | — | P1-TC06, P1-T-EXIT-05 | 1 | P0 |
| P1-TR07 | Flake quarantine works | Flaky tests quarantined per policy | — | P1-TC07 | 1 | P1 |
| P1-TR08 | Risk tests exist | ≥11 risk register tests | RK01..08 | P1-TC08 | 1 | P0 |
| P1-TR09 | Traceability complete | Workflow→Req→Test matrix 100% | — | P1-TC09 | 1 | P0 |

### H.5 Phase 1 Ops Requirements

| Req ID | Description | Invariant | Risk | Tests | Phase | Priority |
|--------|-------------|-----------|------|-------|-------|----------|
| P1-OR01 | Gate dashboard live | LCB per gate displayed | — | — | 1 | P0 |
| P1-OR02 | HITL dashboard live | Queue depth/age displayed | INV-07 | — | 1 | P0 |
| P1-OR03 | Circuit breaker dashboard | Per-dependency state displayed | — | — | 1 | P1 |
| P1-OR04 | Reconciliation dashboard | Queue depth/drift rate displayed | — | — | 1 | P1 |
| P1-OR05 | Invariant violation alerts | Alerts on any violation | INV-* | — | 1 | P0 |
| P1-OR06 | Runbooks documented | RB-01..05 written and tested | — | — | 1 | P1 |

### H.6 Phase 2 Functional Requirements

| Req ID | Description | Invariant | Risk | Tests | Phase | Priority |
|--------|-------------|-----------|------|-------|-------|----------|
| P2-R01 | Business spawn | Generate valid BusinessConfig from template | — | P2-T01 | 2 | P0 |
| P2-R02 | Skill catalog | Register and discover reusable skills | — | P2-T02, P2-T03 | 2 | P1 |
| P2-R03 | Skill invocation | Execute skill with parameter binding | — | P2-T04 | 2 | P0 |
| P2-R04 | Skill versioning | SemVer with deprecation flow | RK04 | P2-T05, P2-T-RK04a/b/c | 2 | P1 |
| P2-R05 | Lesson recording | Capture successful execution patterns | — | P2-T06 | 2 | P1 |
| P2-R06 | Lesson retrieval | RAG retrieves relevant lessons | — | P2-T07 | 2 | P1 |
| P2-R07 | Eval gate | Gated deployment based on eval score | RK05 | P2-T08, P2-T-RK05a/b/c | 2 | P0 |
| P2-R08 | Skill deprecation | Old skill versions phased out | RK04 | P2-T09 | 2 | P1 |
| P2-R09 | Multi-business isolation | ≥2 businesses isolated | INV-06 | P2-T10, P2-T11 | 2 | P0 |
| P2-R10 | Crystallization | Repeated success → promoted skill | — | P2-T12 | 2 | P1 |
| P2-R11 | Shadow mode | New logic validated without side effects | — | P2-T13 | 2 | P1 |
| P2-R12 | State conflict resolution | Version conflicts handled per strategy | — | P2-T14 | 2 | P1 |

### H.7 Phase 2 Testing Requirements

| Req ID | Description | Invariant | Risk | Tests | Phase | Priority |
|--------|-------------|-----------|------|-------|-------|----------|
| P2-TR01 | Coverage measured | ≥80% statement coverage | — | P2-TC01 | 2 | P1 |
| P2-TR02 | Contract tests pass | Kernel↔Business contracts verified | — | P2-TC02 | 2 | P0 |
| P2-TR03 | Concurrency tests exist | Race conditions tested | — | P2-TC03 | 2 | P0 |
| P2-TR04 | Skill lifecycle tested | Create/deprecate/version tested | RK04 | P2-TC04 | 2 | P1 |
| P2-TR05 | Prompt regression tested | LLM output stability verified | RK05 | P2-TC05 | 2 | P1 |
| P2-TR06 | Risk tests (RK03-05) | ≥9 tests for POD/skill/lesson risks | RK03..05 | P2-TC06 | 2 | P0 |
| P2-TR07 | Sandbox tier binding | Every test tagged with tier | — | P2-TC07 | 2 | P1 |

### H.8 Phase 3 Functional Requirements

| Req ID | Description | Invariant | Risk | Tests | Phase | Priority |
|--------|-------------|-----------|------|-------|-------|----------|
| P3-R01 | Autonomous spawn | Agent spawns new business from market signal | — | P3-T01 | 3 | P1 |
| P3-R02 | Spawn approval | Human approves spawn before activation | INV-07 | P3-T02 | 3 | P0 |
| P3-R03 | Portfolio management | Multiple businesses managed as portfolio | — | P3-T03, P3-T04 | 3 | P1 |
| P3-R04 | Portfolio spend cap | Aggregate spend bounded | INV-03 | P3-T05 | 3 | P0 |
| P3-R05 | Portfolio risk cap | Aggregate refunds bounded | INV-03 | P3-T06 | 3 | P0 |
| P3-R06 | Causal inference | Root cause identified from failure patterns | — | P3-T07 | 3 | P2 |
| P3-R07 | Adaptive learning | System improves from experience | — | P3-T08 | 3 | P2 |
| P3-R08 | Lesson promotion | A/B tested lessons promoted to skills | RK05 | P3-T09 | 3 | P1 |
| P3-R09 | Market adaptation | Business config adjusted to market | — | P3-T10 | 3 | P2 |
| P3-R10 | Formal verification | Non-interference proof for tenancy | INV-06 | P3-T11 | 3 | P1 |

### H.9 Phase 3 Testing Requirements

| Req ID | Description | Invariant | Risk | Tests | Phase | Priority |
|--------|-------------|-----------|------|-------|-------|----------|
| P3-TR01 | Chaos experiments defined | ≥5 chaos experiments | RK01..03 | P3-TC01 | 3 | P0 |
| P3-TR02 | Chaos steady state maintained | 100% pass | — | P3-CHAOS-01..05 | 3 | P0 |
| P3-TR03 | Mutation score acceptable | ≥60% mutants killed | — | P3-TC02 | 3 | P1 |
| P3-TR04 | Metamorphic tests exist | ≥4 metamorphic relations | — | P3-TC03 | 3 | P1 |
| P3-TR05 | Adversarial tests pass | ≥5 attack vectors tested | RK06 | P3-TC04 | 3 | P0 |
| P3-TR06 | Property-based tests exist | ≥3 properties verified | — | P3-TC05 | 3 | P1 |
| P3-TR07 | Perf SLOs met | P0 workflows meet latency targets | — | P3-TC06 | 3 | P0 |
| P3-TR08 | Risk tests (RK06) | ≥5 cross-tenant adversarial tests | RK06 | P3-TC07 | 3 | P0 |

### H.10 Cross-Phase Traceability Summary

| Category | Phase 1 | Phase 2 | Phase 3 | Total |
|----------|---------|---------|---------|-------|
| Invariant Requirements | 8 | 0 | 0 | 8 |
| Functional Requirements | 31 | 12 | 10 | 53 |
| Testing Requirements | 9 | 7 | 8 | 24 |
| Ops Requirements | 6 | — | — | 6 |
| **Total** | **54** | **19** | **18** | **91** |

### H.11 Invariant → Test Coverage Matrix

| Invariant | Positive Tests | Negative Tests | Risk Tests | Total |
|-----------|----------------|----------------|------------|-------|
| INV-01 Schema | P1-T01, P1-T02 | P1-T05-NEG-01..06 | — | 8 |
| INV-02 Permission | P1-T03, P1-T04 | P1-T05-NEG-07..11 | — | 7 |
| INV-03 Bounds | P1-T05..T08 | — | — | 4 |
| INV-04 Trace | P1-T09, P1-T10 | — | P1-T-RK08a/b | 4 |
| INV-05 Idempotency | P1-T11, P1-T12, P1-H07, P1-H08 | P1-T05-NEG-12..14 | — | 7 |
| INV-06 Tenant | P1-T31..T34 | — | P1-T-RK06a/b/c, P3-T11 | 8 |
| INV-07 HITL | P1-T13..T15, P1-T26..T30, P1-T41 | P1-T05-NEG-15..18 | — | 13 |
| INV-04 Trace | P1-T09, P1-T10 | — | — | 2 |
| **Total** | **31** | **18** | **6** | **53** |

### H.12 Risk → Test Coverage Matrix

| Risk ID | Risk Description | Tests | Coverage |
|---------|------------------|-------|----------|
| RK01 | LLM rate limits | P1-T-RK01a/b/c | 3 tests |
| RK02 | Stripe webhook delays | P1-T-RK02a/b/c/d | 4 tests |
| RK03 | POD vendor down | P2-T-RK03a/b/c | 3 tests |
| RK04 | Skill drift | P2-T-RK04a/b/c | 3 tests |
| RK05 | Bad lesson | P2-T-RK05a/b/c | 3 tests |
| RK06 | Cross-tenant | P1-T-RK06a/b/c, P3-T-RK06a..e | 8 tests |
| RK07 | Out-of-order webhooks | P1-T-RK07a/b | 2 tests |
| RK08 | PII in traces | P1-T-RK08a/b | 2 tests |
| **Total** | — | — | **28 tests** |

### H.13 Workflow → Requirement → Test Matrix

| Phase | Workflow ID | Workflow Name | Requirements | Tests |
|-------|-------------|---------------|--------------|-------|
| **P1** | P1-WF01 | Order→Fulfill | P1-R09, P1-R10, P1-R11 | P1-T19, P1-T20, P1-T21 |
| **P1** | P1-WF02 | Fulfill→Track | P1-R11 | P1-T21 |
| **P1** | P1-WF03 | Refund | P1-R12, P1-R13 | P1-T22, P1-T23 |
| **P1** | P1-WF04 | Customer notify | P1-R14 | P1-T24 |
| **P1** | P1-WF05 | WISMO | P1-R15 | P1-T25 |
| **P1** | P1-WF06 | HITL approval | P1-R16, P1-R17, P1-R18, P1-R19 | P1-T26..T30 |
| **P1** | P1-WF07 | Webhook ingest | P1-R21..R27 | P1-T36..T40 |
| **P2** | P2-WF01 | Business spawn | P2-R01 | P2-T01 |
| **P2** | P2-WF02 | Skill register | P2-R02 | P2-T02 |
| **P2** | P2-WF03 | Skill invoke | P2-R03 | P2-T04 |
| **P2** | P2-WF04 | Skill version | P2-R04 | P2-T05 |
| **P2** | P2-WF05 | Lesson record | P2-R05 | P2-T06 |
| **P2** | P2-WF06 | Lesson retrieve | P2-R06 | P2-T07 |
| **P2** | P2-WF07 | Eval gate | P2-R07 | P2-T08 |
| **P2** | P2-WF08 | Crystallization | P2-R10 | P2-T12 |
| **P3** | P3-WF01 | Autonomous spawn | P3-R01, P3-R02 | P3-T01, P3-T02 |
| **P3** | P3-WF02 | Portfolio manage | P3-R03, P3-R04, P3-R05 | P3-T03..T06 |
| **P3** | P3-WF03 | Causal inference | P3-R06 | P3-T07 |
| **P3** | P3-WF04 | Adaptive learning | P3-R07 | P3-T08 |
| **P3** | P3-WF05 | Lesson promotion | P3-R08 | P3-T09 |

### H.14 Compile Check → Test Matrix

| Check ID | Check Name | Phase | Tests |
|----------|------------|-------|-------|
| CC-01 | Tool closure | 1+ | P1-T-CC01 |
| CC-02 | Bounds present | 1+ | P1-T-CC02 |
| CC-03 | Scopes present | 1+ | P1-T-CC03 |
| CC-04 | FINANCIAL HITL | 1+ | P1-T41, P1-T-CC04 |

### H.15 Exit Criteria → Verification Matrix

#### Phase 1 Exit Criteria

| Exit ID | Criterion | Verification | Status |
|---------|-----------|--------------|--------|
| P1-EXIT-01 | P0 tests 100% | CI dashboard | — |
| P1-EXIT-02 | P1 tests ≥95% LCB | CI dashboard | — |
| P1-EXIT-03 | All invariants tested | RTM §H.11 | — |
| P1-EXIT-04 | Soak test passed | 7-day production run | — |
| P1-EXIT-05 | External APIs mocked 100% | Test audit | — |
| P1-EXIT-06 | Negative tests exist ≥12 | Test count | — |
| P1-EXIT-07 | Oracle strategy documented | §P1.10 | — |
| P1-EXIT-08 | Risk register tests ≥4 | §P1.9 | — |
| P1-EXIT-09 | LCB gate math implemented | §Appendix E | — |
| P1-EXIT-10 | Flake policy enforced | §15.6 | — |
| P1-EXIT-11 | Workflow traceability 100% | §H.13 | — |
| P1-EXIT-12 | Success rate measured | Dashboard | — |
| P1-EXIT-13 | Ops dashboards live | §P1.4.1 | — |
| P1-EXIT-14 | Runbooks documented | §P1.4.1 | — |

#### Phase 2 Exit Criteria

| Exit ID | Criterion | Verification | Status |
|---------|-----------|--------------|--------|
| P2-EXIT-01 | Phase 1 exits maintained | CI regression | — |
| P2-EXIT-02 | Second business spawned | Spawn test | — |
| P2-EXIT-03 | Both businesses ≥95% LCB | CI dashboard | — |
| P2-EXIT-04 | Skill catalog working | ≥5 skills registered | — |
| P2-EXIT-05 | Crystallization working | ≥3 skills promoted | — |
| P2-EXIT-06 | Coverage ≥80% | pytest-cov | — |
| P2-EXIT-07 | Contract tests pass | Pact verifier | — |
| P2-EXIT-08 | Concurrency tests exist | Test audit | — |

#### Phase 3 Exit Criteria

| Exit ID | Criterion | Verification | Status |
|---------|-----------|--------------|--------|
| P3-EXIT-01 | Phase 2 exits maintained | CI regression | — |
| P3-EXIT-02 | Autonomous spawn tested | P3-T01, P3-T02 | — |
| P3-EXIT-03 | Portfolio caps enforced | P3-T05, P3-T06 | — |
| P3-EXIT-04 | Chaos experiments pass | P3-CHAOS-* | — |
| P3-EXIT-05 | Mutation score ≥60% | mutmut | — |
| P3-EXIT-06 | Perf SLOs met | locust/k6 | — |
| P3-EXIT-07 | Formal isolation proof | Static analysis | — |
| P3-EXIT-08 | Adversarial tests pass | P3-TC04 | — |
