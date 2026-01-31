# AutoBiz Phase 1 Execution Task Table (Merged v1.0)

**Version:** 1.0 (Merged from Claude-54 + Alt-28)  
**Spec Alignment:** AUTOBIZ_ECOSYSTEM_PLAN v4.6  
**Generated:** 2026-01-30

---

## Merge Rationale

This task list merges:
- **Alt-28 structure**: Consolidated tasks with superior quality metadata
- **Claude-54 traceability**: Complete requirement/test mapping
- **Claude-54 prioritization**: P0/P1/P2 discrimination (vs Alt-28's 100% P0)
- **Explicit safety boundaries**: Circuit breakers, loop detection as separate tasks
- **Explicit gates**: Entry criteria verification, soak test as trackable tasks

---

## Schema

| Column | Type | Required | Notes |
|--------|------|----------|-------|
| Task_ID | `P1-TASK-##` | ✓ | Sequential 01-32 |
| Phase | `P1` | ✓ | Fixed for this table |
| Workstream | enum | ✓ | Infra/Data/Security/Kernel/Eval/Business/Ops/QA |
| Component | string | ✓ | P1-C## or logical grouping |
| Spec_Section | string | ✓ | `§` anchor(s) |
| Requirement_IDs | list | ✓ | INV-##, P1-R##, P1-RH##, P1-TR##, P1-OR## |
| Workflow_Scope | list | — | P1-WF## or `Global` |
| Deliverable | string | ✓ | Concrete output |
| Acceptance_Criteria | string | ✓ | Binary pass definition |
| Verification_Method | enum | ✓ | TEST/REVIEW/DEMO/DEPLOY |
| Test_Cases | list | — | P1-T##, P1-H##, P1-T-RK## |
| Oracle_Type | enum | — | From §P1.10 |
| Priority | enum | ✓ | P0/P1/P2 |
| Effort | enum | ✓ | S/M/L/XL |
| Owner | string | — | Team/role |
| Depends_On | list | — | Task_IDs |
| Blocked_By | string | — | Runtime blockers |
| Risks | string | ✓ | Top 1-3 failure modes |
| Rollback | string | ✓ | Revert strategy |
| Telemetry | string | ✓ | Signals/dashboards |
| Security_Notes | string | ✓ | RLS, PII, secrets |
| Status | enum | ✓ | NOT_STARTED/IN_PROGRESS/BLOCKED/IN_REVIEW/DONE |
| PR_Link | URL | — | Code review |
| Evidence_Link | URL | — | CI artifact |
| Target_Date | date | — | Deadline |

---

## Summary Statistics

| Metric | Value |
|--------|-------|
| Total Tasks | 32 |
| P0 Tasks | 28 (87%) |
| P1 Tasks | 4 (13%) |
| P2 Tasks | 0 (0%) |
| Critical Path Length | 13 tasks |
| Estimated Total Effort | ~28-35 developer-weeks |
| Requirements Covered | 58/58 (100%) |
| Tests Mapped | 66/66 (100%) |

---

## Workstream Distribution

| Workstream | Tasks | P0 | P1 |
|------------|-------|----|----|
| Infra | 3 | 3 | 0 |
| Data | 1 | 1 | 0 |
| Security | 3 | 3 | 0 |
| Kernel | 12 | 11 | 1 |
| Eval | 1 | 1 | 0 |
| Business | 4 | 4 | 0 |
| Ops | 1 | 0 | 1 |
| QA | 5 | 5 | 0 |
| Gate | 2 | 2 | 0 |

---

## Critical Path

```
P1-TASK-01 (Repo)
    │
    ▼
P1-TASK-02 (Local Dev)
    │
    ▼
P1-TASK-03 (Schemas)
    │
    ├──────────────────┬──────────────────┐
    ▼                  ▼                  ▼
P1-TASK-04         P1-TASK-06         P1-TASK-10
(Tenant RLS)       (Schema Valid)     (Tracing)
    │                  │                  │
    ▼                  ▼                  │
P1-TASK-05         P1-TASK-07            │
(Credentials)      (Permission)          │
                       │                  │
                       ▼                  │
                   P1-TASK-08 ◄───────────┘
                   (Bounds)
                       │
                       ▼
                   P1-TASK-15
                   (Orchestrator)
                       │
                       ▼
                   P1-TASK-16
                   (HITL)
                       │
                       ▼
                   P1-TASK-23
                   (Workflows)
                       │
                       ▼
                   P1-TASK-29
                   (Tests)
                       │
                       ▼
                   P1-TASK-30
                   (CI Pipeline)
                       │
                       ▼
                   P1-TASK-32
                   (Soak + Exit)
                       │
                       ▼
               ═══════════════
               PHASE 1 EXIT
               ═══════════════
```

---

## Task Details

---

### P1-TASK-01: Repo + Tooling

| Field | Value |
|-------|-------|
| **Task_ID** | P1-TASK-01 |
| **Phase** | P1 |
| **Workstream** | Infra |
| **Component** | Repo + tooling |
| **Spec_Section** | §P1.1 Entry Criteria |
| **Requirement_IDs** | P1-ENTRY-03 |
| **Workflow_Scope** | Global |
| **Deliverable** | Repo initialized; lint/format; test runner skeleton |
| **Acceptance_Criteria** | CI runs lint + unit test stub on PR |
| **Verification_Method** | DEPLOY |
| **Test_Cases** | (build) |
| **Oracle_Type** | Consistency |
| **Priority** | P0 |
| **Effort** | S |
| **Owner** | DevOps |
| **Depends_On** | — |
| **Blocked_By** | — |
| **Risks** | Dev env drift; no reproducible runs |
| **Rollback** | Revert to last green commit |
| **Telemetry** | CI status; build duration; failure reasons |
| **Security_Notes** | Secrets absent; no prod creds in repo |
| **Status** | NOT_STARTED |

---

### P1-TASK-02: Local Dev Stack

| Field | Value |
|-------|-------|
| **Task_ID** | P1-TASK-02 |
| **Phase** | P1 |
| **Workstream** | Infra |
| **Component** | Local dev stack |
| **Spec_Section** | §P1.1 Entry Criteria, §P1.4.1 |
| **Requirement_IDs** | P1-ENTRY-01 |
| **Workflow_Scope** | Global |
| **Deliverable** | Docker Compose (PostgreSQL/Redis/trace backend) + env templates; `make dev` target |
| **Acceptance_Criteria** | `make dev` brings stack up; healthchecks green; tests pass locally in <5 min setup |
| **Verification_Method** | DEMO |
| **Test_Cases** | P1-H09 |
| **Oracle_Type** | Consistency |
| **Priority** | P0 |
| **Effort** | M |
| **Owner** | DevOps |
| **Depends_On** | P1-TASK-01 |
| **Blocked_By** | — |
| **Risks** | Flaky local infra blocks progress; works on one machine fails on another |
| **Rollback** | Tear down volumes; pin versions |
| **Telemetry** | Service health metrics; container logs |
| **Security_Notes** | Isolated *_test DB; no prod endpoints; local-only test credentials |
| **Status** | NOT_STARTED |

---

### P1-TASK-03: Core Schemas + Migrations

| Field | Value |
|-------|-------|
| **Task_ID** | P1-TASK-03 |
| **Phase** | P1 |
| **Workstream** | Data |
| **Component** | P1-C08/C09/C10 (Event Store, State Store, Tenant Manager) |
| **Spec_Section** | §11.2a Event Store, §12 Tenant Isolation, §P1.2 P1-C08/C10/C26 |
| **Requirement_IDs** | INV-06, P1-R07, P1-R08, P1-R26, P1-R27, P1-R28, P1-R29, P1-R30 |
| **Workflow_Scope** | Global |
| **Deliverable** | DB migrations for `tenants`, `state_versions`, `receipts`, `traces`, `event_store`, `reconciliation`, `hitl_requests` tables + indexes (idx_events_tenant_source, idx_events_tenant_status) |
| **Acceptance_Criteria** | Fresh DB migrates cleanly; downgrade path documented; key indexes present; RLS ready |
| **Verification_Method** | DEPLOY |
| **Test_Cases** | P1-T13, P1-T14, P1-T31, P1-T36 |
| **Oracle_Type** | Durability, Consistency |
| **Priority** | P0 |
| **Effort** | M |
| **Owner** | Backend |
| **Depends_On** | P1-TASK-02 |
| **Blocked_By** | — |
| **Risks** | Schema mismatch breaks replay/idempotency/event ordering |
| **Rollback** | Rollback via down migrations; restore snapshot |
| **Telemetry** | Migration timings; index usage; slow query logs |
| **Security_Notes** | RLS ready; tenant_id NOT NULL; audit columns (created_at, updated_at) |
| **Status** | NOT_STARTED |

---

### P1-TASK-04: Tenant Context + RLS Isolation

| Field | Value |
|-------|-------|
| **Task_ID** | P1-TASK-04 |
| **Phase** | P1 |
| **Workstream** | Security |
| **Component** | P1-C10 (Tenant Manager) |
| **Spec_Section** | §12 Tenant Isolation Model, §P1-R21..R25 |
| **Requirement_IDs** | INV-02, INV-04, INV-06, P1-R21, P1-R22, P1-R23, P1-R24, P1-R25 |
| **Workflow_Scope** | Global |
| **Deliverable** | Request/transaction tenant context; `set_tenant_context()` function; query filter injection; entity namespace prefixing; RLS policies on all tables |
| **Acceptance_Criteria** | Cross-tenant reads/writes rejected; all entities prefixed; context set per transaction; 403 logged |
| **Verification_Method** | TEST |
| **Test_Cases** | P1-T31, P1-T32, P1-T33, P1-T34, P1-T35, P1-T-RK06a/b/c |
| **Oracle_Type** | Permission, Consistency |
| **Priority** | P0 |
| **Effort** | M |
| **Owner** | Backend |
| **Depends_On** | P1-TASK-03 |
| **Blocked_By** | — |
| **Risks** | Silent data bleed across tenants; RLS bypass |
| **Rollback** | Disable feature flag; revoke creds; audit traces |
| **Telemetry** | 403 counts; cross-tenant attempt logs; tenant_id coverage |
| **Security_Notes** | RLS enforced; secrets never in traces; all cross-tenant attempts logged as security incidents |
| **Status** | NOT_STARTED |

---

### P1-TASK-05: Credential Scoper

| Field | Value |
|-------|-------|
| **Task_ID** | P1-TASK-05 |
| **Phase** | P1 |
| **Workstream** | Security |
| **Component** | P1-C10 (Tenant Manager) |
| **Spec_Section** | §12.4 Credential Rotation Policy |
| **Requirement_IDs** | P1-R22 |
| **Workflow_Scope** | Global |
| **Deliverable** | Per-tenant secret lookup + caching; deny cross-tenant credential usage; secrets manager integration (AWS Secrets Manager / Vault) |
| **Acceptance_Criteria** | Tenant A cannot access Tenant B keys; audit logged; rotation API exists |
| **Verification_Method** | TEST |
| **Test_Cases** | P1-T32 |
| **Oracle_Type** | Permission |
| **Priority** | P0 |
| **Effort** | S |
| **Owner** | Backend |
| **Depends_On** | P1-TASK-04 |
| **Blocked_By** | — |
| **Risks** | Wrong key used in external side effects; credential leak in logs |
| **Rollback** | Rotate keys; invalidate cache; replay with correct tenant |
| **Telemetry** | Key-access audit log; cache hit rate; credential_rotation_age_days |
| **Security_Notes** | Encrypt at rest; least-privilege secret paths; no keys in logs |
| **Status** | NOT_STARTED |

---

### P1-TASK-06: Tool Registry + Schema Validation

| Field | Value |
|-------|-------|
| **Task_ID** | P1-TASK-06 |
| **Phase** | P1 |
| **Workstream** | Kernel |
| **Component** | P1-C01 (Executor), P1-C03 (Tool Registry) |
| **Spec_Section** | §4.3 ToolContract, §INV-01 |
| **Requirement_IDs** | INV-01, P1-R01, P1-R18 |
| **Workflow_Scope** | Global |
| **Deliverable** | `ToolRegistry` class; `SchemaValidator` class; JSON Schema validation before execution; standardized error model; tool lookup by name/version |
| **Acceptance_Criteria** | Valid input accepted; invalid tool calls rejected before execution with `SCHEMA_INVALID`; errors traced; unknown tool returns error |
| **Verification_Method** | TEST |
| **Test_Cases** | P1-T01, P1-T02, P1-T28, P1-T01-NEG-* |
| **Oracle_Type** | Schema |
| **Priority** | P0 |
| **Effort** | M |
| **Owner** | Kernel Dev |
| **Depends_On** | P1-TASK-01 |
| **Blocked_By** | — |
| **Risks** | Agents bypass schemas; undefined tool inputs cause side effects; schema too permissive/strict |
| **Rollback** | Hard-fail executor; quarantine tool; flag to bypass (admin only) |
| **Telemetry** | Schema reject counts; tool-call validation latency; tool_invocation_total by tool/version |
| **Security_Notes** | Reject unknown fields; no eval bypass; validation runs before any side effects |
| **Status** | NOT_STARTED |

---

### P1-TASK-07: Permission Enforcement

| Field | Value |
|-------|-------|
| **Task_ID** | P1-TASK-07 |
| **Phase** | P1 |
| **Workstream** | Kernel |
| **Component** | P1-C01 (Executor), P1-C05 (Permission Enforcer) |
| **Spec_Section** | §4.4 PermissionScope, §5.1 BusinessConfig, §INV-02 |
| **Requirement_IDs** | INV-02, P1-R02, P1-R20 |
| **Workflow_Scope** | Global |
| **Deliverable** | `PermissionEnforcer` class; PermissionScope allowlists per tool; enforcement in executor; deny-by-default |
| **Acceptance_Criteria** | Forbidden ops blocked + traced; allowed ops succeed; denial logged with principal/tool/action |
| **Verification_Method** | TEST |
| **Test_Cases** | P1-T03, P1-T04, P1-T30, P1-T02-NEG-* |
| **Oracle_Type** | Permission |
| **Priority** | P0 |
| **Effort** | M |
| **Owner** | Kernel Dev |
| **Depends_On** | P1-TASK-06 |
| **Blocked_By** | — |
| **Risks** | Over-broad scopes allow irreversible ops; overly restrictive blocks business |
| **Rollback** | Emergency scope revoke; feature flag per tool; revert to previous scope config |
| **Telemetry** | Denied-op rate; scope coverage by tool; permission_check_pass/deny_total |
| **Security_Notes** | Principals + tenant in every decision; audit trail; all denials logged |
| **Status** | NOT_STARTED |

---

### P1-TASK-08: Bounds + Timeouts

| Field | Value |
|-------|-------|
| **Task_ID** | P1-TASK-08 |
| **Phase** | P1 |
| **Workstream** | Kernel |
| **Component** | P1-C02 (Bounds Enforcer) |
| **Spec_Section** | §3 BoundsConfig, §INV-03 |
| **Requirement_IDs** | INV-03, P1-R03, P1-R19 |
| **Workflow_Scope** | Global |
| **Deliverable** | `BoundsEnforcer` class; max_steps/max_time/max_tokens/max_tool_calls + per-tool timeout + hard termination |
| **Acceptance_Criteria** | Runs terminate at each bound; termination_reason matches bound type; violations logged |
| **Verification_Method** | TEST |
| **Test_Cases** | P1-T05, P1-T06, P1-T07, P1-T29 |
| **Oracle_Type** | Bounds |
| **Priority** | P0 |
| **Effort** | M |
| **Owner** | Kernel Dev |
| **Depends_On** | P1-TASK-06 |
| **Blocked_By** | — |
| **Risks** | Runaway loops; cost explosions; bounds too loose or too tight |
| **Rollback** | Kill-switch; circuit breaker; quarantine prompt; increase bounds |
| **Telemetry** | Termination reasons; cost per run; p95 tool latency; run_steps_histogram |
| **Security_Notes** | Resource caps enforced below LLM; defense-in-depth |
| **Status** | NOT_STARTED |

---

### P1-TASK-09: Loop Detector

| Field | Value |
|-------|-------|
| **Task_ID** | P1-TASK-09 |
| **Phase** | P1 |
| **Workstream** | Kernel |
| **Component** | P1-C02 (Bounds Enforcer) |
| **Spec_Section** | §3 BoundsConfig |
| **Requirement_IDs** | P1-R04 |
| **Workflow_Scope** | Global |
| **Deliverable** | History-based repetition detection with termination policy; configurable thresholds |
| **Acceptance_Criteria** | Repeated tool sequences terminated; loop logged; configurable retry allowlist |
| **Verification_Method** | TEST |
| **Test_Cases** | P1-T08 |
| **Oracle_Type** | Consistency |
| **Priority** | P0 |
| **Effort** | S |
| **Owner** | Kernel Dev |
| **Depends_On** | P1-TASK-08 |
| **Blocked_By** | — |
| **Risks** | False positives kill valid retries OR false negatives allow infinite retry |
| **Rollback** | Tune thresholds; add allowlisted retry patterns |
| **Telemetry** | Loop detections per workflow; retry stats; loop_detection_total |
| **Security_Notes** | No suppression without config change + audit |
| **Status** | NOT_STARTED |

---

### P1-TASK-10: Tracing + Correlation + Cost

| Field | Value |
|-------|-------|
| **Task_ID** | P1-TASK-10 |
| **Phase** | P1 |
| **Workstream** | Kernel |
| **Component** | P1-C06 (Cost Tracker), P1-C07 (Trace Store) |
| **Spec_Section** | §2 Trace Redaction Policy, §INV-04 |
| **Requirement_IDs** | INV-04, P1-R05 |
| **Workflow_Scope** | Global |
| **Deliverable** | `TraceStore` class; `CostTracker` class; correlation ID propagation; step/tool/state-diff trace; token/API cost attribution; tiered retention (hot/warm/cold) |
| **Acceptance_Criteria** | Every run has correlation + cost; persisted transcript; cost > 0 for runs with LLM/API calls |
| **Verification_Method** | TEST |
| **Test_Cases** | P1-T09, P1-T10 |
| **Oracle_Type** | Trace, Cost |
| **Priority** | P0 |
| **Effort** | M |
| **Owner** | Kernel Dev |
| **Depends_On** | P1-TASK-06 |
| **Blocked_By** | — |
| **Risks** | Missing evidence breaks audits and debugging; cost not attributed |
| **Rollback** | Fallback local trace sink; block deploy if trace missing |
| **Telemetry** | Trace completeness %; missing-correlation alerts; cost per workflow; run_cost_histogram |
| **Security_Notes** | Exclude secrets; enforce trace schema; PII handled per redaction policy |
| **Status** | NOT_STARTED |

---

### P1-TASK-11: Trace Redaction

| Field | Value |
|-------|-------|
| **Task_ID** | P1-TASK-11 |
| **Phase** | P1 |
| **Workstream** | Security |
| **Component** | P1-C07 (Trace Store) |
| **Spec_Section** | §2 Trace Redaction Policy, §P1-R25 |
| **Requirement_IDs** | INV-04, P1-R25 |
| **Workflow_Scope** | Global |
| **Deliverable** | Allowlist filter; sensitive field redactor; defense-in-depth scanners (secret/CC/PII); scanner alert on detection |
| **Acceptance_Criteria** | Persisted traces show masked PII; secret patterns rejected; only allowlisted fields in trace; scanner detections alert for review |
| **Verification_Method** | TEST |
| **Test_Cases** | P1-T35, P1-T-RK08a, P1-T-RK08b |
| **Oracle_Type** | Security |
| **Priority** | P0 |
| **Effort** | S |
| **Owner** | Kernel Dev |
| **Depends_On** | P1-TASK-10 |
| **Blocked_By** | — |
| **Risks** | Leak of PII/keys into logs/traces; over-redaction makes traces useless |
| **Rollback** | Purge traces; rotate secrets; incident playbook; retroactive redaction (expensive) |
| **Telemetry** | Redaction hit counts; secret-reject counts; scanner_detection_total by type |
| **Security_Notes** | PII regex list; allowlist structured safe fields; scanner detection = allowlist misconfiguration |
| **Status** | NOT_STARTED |

---

### P1-TASK-12: State Manager Version + Replay

| Field | Value |
|-------|-------|
| **Task_ID** | P1-TASK-12 |
| **Phase** | P1 |
| **Workstream** | Kernel |
| **Component** | P1-C09 (State Store) |
| **Spec_Section** | §P2.14 State Manager, §INV-06 |
| **Requirement_IDs** | INV-06, P1-R08 |
| **Workflow_Scope** | Global |
| **Deliverable** | `StateStore` class; `TranscriptReplayer` class; versioned state patches; optimistic locking; transcript replay to deterministic state; deterministic clock injection |
| **Acceptance_Criteria** | Patch increments version; version conflicts detected; replay produces identical final state hash and receipts |
| **Verification_Method** | TEST |
| **Test_Cases** | P1-T14, P1-T15 |
| **Oracle_Type** | Durability, Consistency |
| **Priority** | P0 |
| **Effort** | M |
| **Owner** | Kernel Dev |
| **Depends_On** | P1-TASK-03, P1-TASK-10 |
| **Blocked_By** | — |
| **Risks** | Non-deterministic state prevents reproducibility; clock drift causes different conditions |
| **Rollback** | Disable non-deterministic tools; snapshot+restore; restore previous version |
| **Telemetry** | State version drift; replay mismatch rate; state_conflict_total |
| **Security_Notes** | State writes require tenant context + correlation id; replay uses recorded clock |
| **Status** | NOT_STARTED |

---

### P1-TASK-13: Idempotency Manager

| Field | Value |
|-------|-------|
| **Task_ID** | P1-TASK-13 |
| **Phase** | P1 |
| **Workstream** | Kernel |
| **Component** | P1-C05 (Idempotency Store) |
| **Spec_Section** | §2 Idempotency Key Specification, §INV-05 |
| **Requirement_IDs** | INV-05, P1-R06 |
| **Workflow_Scope** | Global |
| **Deliverable** | `IdempotencyStore` class; RFC 8785 JCS canonicalization; deterministic key (SHA-256); 24h lookback; Redis hot + PostgreSQL cold; fixed-length external key mapping (`autobiz:{sha256(internal_key)[:32]}`) |
| **Acceptance_Criteria** | First call executes; duplicate within 24h returns cached result; after window re-executes; key format deterministic; TTL honored |
| **Verification_Method** | TEST |
| **Test_Cases** | P1-T11, P1-T12, P1-H07, P1-H08, P1-T05-NEG-* |
| **Oracle_Type** | Idempotency |
| **Priority** | P0 |
| **Effort** | M |
| **Owner** | Kernel Dev |
| **Depends_On** | P1-TASK-03, P1-TASK-06 |
| **Blocked_By** | — |
| **Risks** | Double-charge/duplicate fulfillments; provider key length issues; key collision |
| **Rollback** | Disable external calls; refund/void; reconcile receipts; flush Redis (causes re-execution) |
| **Telemetry** | Duplicate-attempt rate; cache hit rate; TTL expiry; idempotency_hit/miss_total |
| **Security_Notes** | Store first_seen_at; audit duplicates; provider-safe keys; keys contain tenant ID |
| **Status** | NOT_STARTED |

---

### P1-TASK-14: Receipt Storage

| Field | Value |
|-------|-------|
| **Task_ID** | P1-TASK-14 |
| **Phase** | P1 |
| **Workstream** | Kernel |
| **Component** | P1-C05 (Idempotency Store) |
| **Spec_Section** | §2 External Idempotency Specification, §P1-R07 |
| **Requirement_IDs** | INV-05, P1-R07 |
| **Workflow_Scope** | Global |
| **Deliverable** | `ReceiptStore` class; receipt schema + persistence; link receipts to execution_id + internal/external idempotency keys; `FinancialReceipt` model for FINANCIAL tools |
| **Acceptance_Criteria** | Every side effect writes receipt with payload + timestamps; internal + external keys linked; receipts immutable |
| **Verification_Method** | TEST |
| **Test_Cases** | P1-T13 |
| **Oracle_Type** | SideEffect, Durability |
| **Priority** | P0 |
| **Effort** | S |
| **Owner** | Backend |
| **Depends_On** | P1-TASK-03, P1-TASK-13 |
| **Blocked_By** | — |
| **Risks** | Missing receipts breaks dedup and disputes |
| **Rollback** | Backfill from provider logs; block tool if receipt write fails |
| **Telemetry** | Receipt write failure rate; receipt coverage by tool; receipt_created_total |
| **Security_Notes** | Receipts store only necessary PII; encrypt sensitive fields; append-only audit evidence |
| **Status** | NOT_STARTED |

---

### P1-TASK-15: Orchestrator Engine + LLM Pinning

| Field | Value |
|-------|-------|
| **Task_ID** | P1-TASK-15 |
| **Phase** | P1 |
| **Workstream** | Kernel |
| **Component** | P1-C01 (Executor), P1-C02 (Orchestrator) |
| **Spec_Section** | §5.2 WorkflowStep, §P1.9 Risk Register (RK01) |
| **Requirement_IDs** | P1-R03, P1-R05 |
| **Workflow_Scope** | Global |
| **Deliverable** | `WorkflowExecutor` class; `LLMClient` class; workflow engine integration; model+prompt pinned per run; run context injection; primary/fallback routing; timeout handling; retry with backoff |
| **Acceptance_Criteria** | Workflows run end-to-end under executor controls; pin recorded in trace; primary timeout triggers fallback; costs tracked |
| **Verification_Method** | TEST |
| **Test_Cases** | P1-T05..T10 (via runs), P1-T-RK01a/b/c |
| **Oracle_Type** | Consistency |
| **Priority** | P0 |
| **Effort** | M |
| **Owner** | Kernel Dev |
| **Depends_On** | P1-TASK-06, P1-TASK-07, P1-TASK-08, P1-TASK-09, P1-TASK-10 |
| **Blocked_By** | — |
| **Risks** | Model drift changes behavior; nondeterministic prompts; fallback also fails |
| **Rollback** | Pin versions; require config hash; rollback to last known good; disable LLM features |
| **Telemetry** | Run config hash; model version distribution; llm_request_total; llm_fallback_triggered_total |
| **Security_Notes** | No dynamic model switching without deploy gate; API keys from secrets manager |
| **Status** | NOT_STARTED |

---

### P1-TASK-16: HITL Approvals

| Field | Value |
|-------|-------|
| **Task_ID** | P1-TASK-16 |
| **Phase** | P1 |
| **Workstream** | Kernel |
| **Component** | P1-C04 (HITL Engine) |
| **Spec_Section** | §5.4 HITLRule, §INV-07 |
| **Requirement_IDs** | INV-07, P1-R09, P1-R30 |
| **Workflow_Scope** | WF03/WF04 + Drift repair |
| **Deliverable** | `HITLEngine` class; HITL queue + audit log + ConditionExpr evaluation; decision API (approve/deny); Slack approval adapter; timeout handler (FAIL for FINANCIAL); financial drift HITL integration |
| **Acceptance_Criteria** | HITL-required ops pause; approve/deny resumes/aborts; decision recorded with approver ID; FINANCIAL timeout = FAIL |
| **Verification_Method** | TEST |
| **Test_Cases** | P1-T16, P1-T17, P1-T40, P1-T41, P1-T07-NEG-* |
| **Oracle_Type** | Permission, Timing |
| **Priority** | P0 |
| **Effort** | M |
| **Owner** | Kernel Dev |
| **Depends_On** | P1-TASK-03, P1-TASK-07, P1-TASK-10 |
| **Blocked_By** | — |
| **Risks** | Bypass approvals or approvals lost/stale; stuck in PENDING |
| **Rollback** | Manual override path; replay from transcript; audit review; admin override (audited) |
| **Telemetry** | HITL backlog depth/age; approval SLA; decision rates; hitl_request_created_total |
| **Security_Notes** | Approval identity verified; immutable audit entries; FINANCIAL tools MUST trigger HITL |
| **Status** | NOT_STARTED |

---

### P1-TASK-17: Compile Validator (CC-01..CC-04)

| Field | Value |
|-------|-------|
| **Task_ID** | P1-TASK-17 |
| **Phase** | P1 |
| **Workstream** | Kernel |
| **Component** | P1-C16 (Config Validator) |
| **Spec_Section** | §8 Compile Checks, §P1-R18..R20 |
| **Requirement_IDs** | INV-07, P1-R18, P1-R19, P1-R20 |
| **Workflow_Scope** | Global |
| **Deliverable** | `BusinessConfigValidator` class; 4 checks: CC-01 (tool closure), CC-02 (bounds present), CC-03 (scopes present), CC-04 (FINANCIAL HITL + no AUTO_APPROVE) |
| **Acceptance_Criteria** | Invalid configs fail compile deterministically; correct error codes; no runtime execution of invalid config |
| **Verification_Method** | TEST |
| **Test_Cases** | P1-T28, P1-T29, P1-T30, P1-T41, P1-T-CC01..CC04 |
| **Oracle_Type** | Schema, Permission |
| **Priority** | P0 |
| **Effort** | S |
| **Owner** | Kernel Dev |
| **Depends_On** | P1-TASK-06, P1-TASK-07, P1-TASK-16 |
| **Blocked_By** | — |
| **Risks** | Bad configs reach runtime; unsafe financial ops; validator blocks valid config |
| **Rollback** | Block merge on compile; revert config commit; bypass flag (requires security approval) |
| **Telemetry** | Compile failure reasons; config hash distribution; config_validation_pass/fail_total |
| **Security_Notes** | Treat configs as code; signed releases; FINANCIAL tools MUST have HITL |
| **Status** | NOT_STARTED |

---

### P1-TASK-18: Golden Suite Runner + Deploy Gate

| Field | Value |
|-------|-------|
| **Task_ID** | P1-TASK-18 |
| **Phase** | P1 |
| **Workstream** | Eval |
| **Component** | P1-C14/C15 (Test Harness) |
| **Spec_Section** | §P1.12 CI Pipeline, §INV-08, §Appendix E |
| **Requirement_IDs** | INV-08, P1-R10, P1-TR06 |
| **Workflow_Scope** | Global |
| **Deliverable** | Test harness executes golden suite; computes raw + Wilson LCB gates; blocks deploy below thresholds; `evaluate_gate()` function per §Appendix E |
| **Acceptance_Criteria** | CI fails when forced failures drop below gate; deploy blocked flag set; LCB ≥ 0.95 for P1 tests |
| **Verification_Method** | TEST |
| **Test_Cases** | P1-T18, P1-T-EXIT-05 |
| **Oracle_Type** | Consistency |
| **Priority** | P0 |
| **Effort** | M |
| **Owner** | QA/DevOps |
| **Depends_On** | P1-TASK-17 |
| **Blocked_By** | — |
| **Risks** | False gate pass lets regressions ship; LCB math error causes false confidence |
| **Rollback** | Fail-closed; quarantine mechanism; mandatory reruns; manual override (requires 2 approvals) |
| **Telemetry** | Gate pass rates; LCB values; flake report; golden_suite_lcb |
| **Security_Notes** | No prod deploy without gate evidence artifact; tampering is security incident |
| **Status** | NOT_STARTED |

---

### P1-TASK-19: External Tool Wrappers + Sandbox Guards

| Field | Value |
|-------|-------|
| **Task_ID** | P1-TASK-19 |
| **Phase** | P1 |
| **Workstream** | Business |
| **Component** | P1-C17..C21 (Shopify/Stripe/Printful/SendGrid Clients) |
| **Spec_Section** | §P1.6 Testing Infrastructure |
| **Requirement_IDs** | P1-RH01, P1-RH02, P1-RH03, P1-RH04, P1-RH05, P1-TR01, P1-TR02 |
| **Workflow_Scope** | Global |
| **Deliverable** | Provider clients with enforced sandbox/test-mode + safe destinations; WireMock for external APIs; VCR.py for LLM; SendGrid sandbox routing; webhook signature validation stubs |
| **Acceptance_Criteria** | Hygiene suite proves no live keys/endpoints/real recipients used; WireMock starts in CI; VCR records/replays LLM calls |
| **Verification_Method** | TEST |
| **Test_Cases** | P1-H01, P1-H02, P1-H03, P1-H04, P1-H05, P1-H06, P1-H09 |
| **Oracle_Type** | Security, Consistency |
| **Priority** | P0 |
| **Effort** | M |
| **Owner** | Business Dev |
| **Depends_On** | P1-TASK-05 |
| **Blocked_By** | — |
| **Risks** | Accidental live charges/emails; WireMock port conflicts; VCR cassette drift |
| **Rollback** | Immediate credential revoke; provider rollback (refund/cancel) |
| **Telemetry** | Outbound call audit; destination allowlist hits; cassette file count |
| **Security_Notes** | Hard block live endpoints; test-only allowlist; test credentials only |
| **Status** | NOT_STARTED |

---

### P1-TASK-20: Shopify Tools

| Field | Value |
|-------|-------|
| **Task_ID** | P1-TASK-20 |
| **Phase** | P1 |
| **Workstream** | Business |
| **Component** | P1-C17 (Shopify Client) |
| **Spec_Section** | §P1.11 Workflow Traceability |
| **Requirement_IDs** | P1-R11, P1-R14 |
| **Workflow_Scope** | WF01, WF04 |
| **Deliverable** | Order fetch/update/cancel tools for Shopify dev store |
| **Acceptance_Criteria** | Order CRUD works in dev store; receipts stored for side effects |
| **Verification_Method** | TEST |
| **Test_Cases** | P1-T19, P1-T24 |
| **Oracle_Type** | SideEffect |
| **Priority** | P0 |
| **Effort** | M |
| **Owner** | Business Dev |
| **Depends_On** | P1-TASK-19, P1-TASK-14 |
| **Blocked_By** | — |
| **Risks** | Order state mismatches cause orphan fulfillment |
| **Rollback** | Reconcile against Shopify truth; cancel/void pipeline |
| **Telemetry** | Tool latency; error codes; receipts coverage |
| **Security_Notes** | Webhook signatures; least privilege scopes |
| **Status** | NOT_STARTED |

---

### P1-TASK-21: Stripe Tools

| Field | Value |
|-------|-------|
| **Task_ID** | P1-TASK-21 |
| **Phase** | P1 |
| **Workstream** | Business |
| **Component** | P1-C18/C21 (Stripe Client) |
| **Spec_Section** | §2 External Idempotency, §P1.11 |
| **Requirement_IDs** | P1-R11, P1-R12, P1-R13 |
| **Workflow_Scope** | WF01, WF02, WF03, WF04 |
| **Deliverable** | Auth/capture/void/refund/tax helpers using Stripe test mode; external idempotency key injection |
| **Acceptance_Criteria** | Charges/refunds created exactly once; receipts written; no live keys; external idempotency header sent |
| **Verification_Method** | TEST |
| **Test_Cases** | P1-T20, P1-T21, P1-T22, P1-T23, P1-H01, P1-H10 |
| **Oracle_Type** | SideEffect, Idempotency |
| **Priority** | P0 |
| **Effort** | M |
| **Owner** | Business Dev |
| **Depends_On** | P1-TASK-19, P1-TASK-13, P1-TASK-14 |
| **Blocked_By** | — |
| **Risks** | Double charge/double refund |
| **Rollback** | Immediate refund; idempotency hard-stop; audit receipts |
| **Telemetry** | Payment failure rate; refund rate; duplicate attempts |
| **Security_Notes** | Financial ops require HITL where configured; webhook signature validation |
| **Status** | NOT_STARTED |

---

### P1-TASK-22: Printful Tools

| Field | Value |
|-------|-------|
| **Task_ID** | P1-TASK-22 |
| **Phase** | P1 |
| **Workstream** | Business |
| **Component** | P1-C19 (Printful Client) |
| **Spec_Section** | §P1.11 Workflow Traceability |
| **Requirement_IDs** | P1-R11, P1-R15, P1-R16 |
| **Workflow_Scope** | WF01, WF05, WF06 |
| **Deliverable** | Create fulfillment, get shipment/tracking via Printful sandbox |
| **Acceptance_Criteria** | Fulfillment created; shipment lookup accurate; retry/escalation hooks exist |
| **Verification_Method** | TEST |
| **Test_Cases** | P1-T19, P1-T25, P1-T26 |
| **Oracle_Type** | SideEffect, Timing |
| **Priority** | P0 |
| **Effort** | M |
| **Owner** | Business Dev |
| **Depends_On** | P1-TASK-19, P1-TASK-14 |
| **Blocked_By** | — |
| **Risks** | Fulfillment created without confirmation; WISMO wrong status |
| **Rollback** | Cancel fulfillment; notify support; reconcile shipments |
| **Telemetry** | Fulfillment latency; POD error rates; retry counts |
| **Security_Notes** | Sandbox endpoint enforced; webhook verification |
| **Status** | NOT_STARTED |

---

### P1-TASK-23: Workflow Graphs P0/P1

| Field | Value |
|-------|-------|
| **Task_ID** | P1-TASK-23 |
| **Phase** | P1 |
| **Workstream** | Kernel |
| **Component** | P1-C13 (Workflow Library) |
| **Spec_Section** | §P1.3 WF01..WF07, §P1.11 Workflow Traceability |
| **Requirement_IDs** | P1-R11, P1-R12, P1-R13, P1-R14, P1-R15 |
| **Workflow_Scope** | WF01..WF07 |
| **Deliverable** | Graph definitions + tool sequence wiring + HITL points for refund/cancel; `OrderFulfillWorkflow`, `PaymentFailureWorkflow`, `RefundWorkflow`, `OrderCancellationWorkflow`, `WISMOHandler`, `FulfillmentExceptionHandler`, `DailyCloseoutJob` |
| **Acceptance_Criteria** | P0 workflows pass 100%; P1 workflows meet ≥95% LCB gate; receipts and state changes verified |
| **Verification_Method** | TEST |
| **Test_Cases** | P1-T19, P1-T20, P1-T21, P1-T22, P1-T23, P1-T24, P1-T25, P1-T26, P1-T27 |
| **Oracle_Type** | Consistency, SideEffect |
| **Priority** | P0 |
| **Effort** | L |
| **Owner** | Kernel+Business |
| **Depends_On** | P1-TASK-15, P1-TASK-16, P1-TASK-20, P1-TASK-21, P1-TASK-22 |
| **Blocked_By** | — |
| **Risks** | Wrong branching; unsafe actions without checks; compensation not triggered |
| **Rollback** | Disable workflow; fall back to manual ops; replay runs |
| **Telemetry** | Workflow success rates; gate LCB; step histograms; workflow_completion_total by status |
| **Security_Notes** | HITL required for refunds/cancel thresholds; customer PII handled per redaction policy |
| **Status** | NOT_STARTED |

---

### P1-TASK-24: Webhook Ingress + Signature Verification

| Field | Value |
|-------|-------|
| **Task_ID** | P1-TASK-24 |
| **Phase** | P1 |
| **Workstream** | Kernel |
| **Component** | P1-C08 (Event Store) |
| **Spec_Section** | §11.2a Event Store, §P1-RH05 |
| **Requirement_IDs** | P1-RH05, P1-R26 |
| **Workflow_Scope** | WF01, WF02 + events |
| **Deliverable** | Webhook endpoints validate signatures (Stripe/Shopify/Printful), normalize events, write to event_store; `EventStore` class with payload_sha256, deduplication |
| **Acceptance_Criteria** | Invalid signature rejected pre-store; valid signature sets signature_valid=true; duplicate webhook skipped; payload hash computed |
| **Verification_Method** | TEST |
| **Test_Cases** | P1-H10, P1-T36 |
| **Oracle_Type** | Security, Consistency |
| **Priority** | P0 |
| **Effort** | M |
| **Owner** | Backend |
| **Depends_On** | P1-TASK-03, P1-TASK-04 |
| **Blocked_By** | — |
| **Risks** | Forged webhooks trigger side effects; clock skew rejects valid events |
| **Rollback** | Disable endpoint; rotate secrets; block source IPs |
| **Telemetry** | Signature failure rate; dedup hits; ingress latency; event_received_total |
| **Security_Notes** | Secret rotation; strict timestamp tolerance; events contain PII per retention policy |
| **Status** | NOT_STARTED |

---

### P1-TASK-25: Event Processing + Reconciliation

| Field | Value |
|-------|-------|
| **Task_ID** | P1-TASK-25 |
| **Phase** | P1 |
| **Workstream** | Kernel |
| **Component** | P1-C08 (Event Store), P1-C26/C27 (Reconciliation) |
| **Spec_Section** | §11.3 Ordering Guarantees, §11.4 Reconciliation Jobs, §11.5 State Repair |
| **Requirement_IDs** | P1-R26, P1-R27, P1-R28, P1-R29, P1-R30 |
| **Workflow_Scope** | WF01, WF02 + drift |
| **Deliverable** | `EventOrderingGate` class; `ReconciliationDetector` class; processor: dedup, ordering hold (60s timeout), timeout release with precondition check, reconcile jobs; financial drift HITL |
| **Acceptance_Criteria** | Out-of-order held then processed; timeout releases with flag; drift detected/repaired with HITL for financial; precondition violations routed to reconciliation |
| **Verification_Method** | TEST |
| **Test_Cases** | P1-T37, P1-T38, P1-T39, P1-T40, P1-T-RK02a/b/c/d, P1-T-RK07a/b |
| **Oracle_Type** | Timing, Consistency |
| **Priority** | P0 |
| **Effort** | L |
| **Owner** | Backend |
| **Depends_On** | P1-TASK-24, P1-TASK-16 |
| **Blocked_By** | — |
| **Risks** | Stuck queues; incorrect repairs; silent drift; events stuck forever |
| **Rollback** | Drain queue; disable reconciliation; manual repair runbook; manual event release |
| **Telemetry** | Queue depth/age; drift rate; repair outcomes; event_held_total; event_timeout_released_total |
| **Security_Notes** | Tenant-scoped queries; audit every repair; timeout events flagged for audit |
| **Status** | NOT_STARTED |

---

### P1-TASK-26: Circuit Breakers

| Field | Value |
|-------|-------|
| **Task_ID** | P1-TASK-26 |
| **Phase** | P1 |
| **Workstream** | Kernel |
| **Component** | — |
| **Spec_Section** | §11.6 Circuit Breaker Configuration |
| **Requirement_IDs** | — |
| **Workflow_Scope** | Global |
| **Deliverable** | `CircuitBreaker` class; per-dependency state (CLOSED/OPEN/HALF_OPEN); Redis-backed state persistence; half-open probing |
| **Acceptance_Criteria** | Breaker opens on threshold failures; half-open after duration; closes on success |
| **Verification_Method** | TEST |
| **Test_Cases** | — (unit tests) |
| **Oracle_Type** | state-change |
| **Priority** | P1 |
| **Effort** | M |
| **Owner** | Backend |
| **Depends_On** | P1-TASK-02 |
| **Blocked_By** | — |
| **Risks** | Breaker stuck open → extended outage; breaker never opens → cascade failure |
| **Rollback** | Manual breaker reset via admin API |
| **Telemetry** | circuit_breaker_state gauge by dependency; circuit_breaker_transition_total |
| **Security_Notes** | Admin-only reset; all transitions logged |
| **Status** | NOT_STARTED |

---

### P1-TASK-27: Dashboards + Alerts + Runbooks

| Field | Value |
|-------|-------|
| **Task_ID** | P1-TASK-27 |
| **Phase** | P1 |
| **Workstream** | Ops |
| **Component** | — |
| **Spec_Section** | §P1.4.1 Ops Minimum Requirements |
| **Requirement_IDs** | P1-OR01, P1-OR02, P1-OR03, P1-OR04, P1-OR05, P1-OR06 |
| **Workflow_Scope** | Global |
| **Deliverable** | Dashboards: Gate Pass Rates (LCB per gate), HITL Backlog (depth/age), Circuit Breaker States, Reconciliation Queue, Invariant Violations, Cost Attribution; Alerts: Gate >5% drop, HITL oldest >15min or depth >50, Breaker OPEN >5min, Drift detection, Invariant violation, Deploy rollback; Runbooks: RB-01 (HITL escalation), RB-02 (Circuit breaker trip), RB-03 (Reconciliation failure), RB-04 (Invariant violation), RB-05 (Deploy rollback) |
| **Acceptance_Criteria** | Soak ready: dashboards live; alerts fire in test; runbooks exist and linked from alerts |
| **Verification_Method** | DEMO |
| **Test_Cases** | — (ops gate) |
| **Oracle_Type** | Observability |
| **Priority** | P1 |
| **Effort** | M |
| **Owner** | DevOps |
| **Depends_On** | P1-TASK-10, P1-TASK-16, P1-TASK-25, P1-TASK-26 |
| **Blocked_By** | — |
| **Risks** | No visibility during incidents; uncontrolled dependency failure; alert fatigue |
| **Rollback** | Disable auto actions; manual override; rollback deploy |
| **Telemetry** | Dashboard freshness; alert firing logs; breaker state transitions |
| **Security_Notes** | Least privilege; no PII in dashboards; runbooks access controlled |
| **Status** | NOT_STARTED |

---

### P1-TASK-28: Implement Hygiene Tests (P1-H##)

| Field | Value |
|-------|-------|
| **Task_ID** | P1-TASK-28 |
| **Phase** | P1 |
| **Workstream** | QA |
| **Component** | P1-TC01, P1-TC02, P1-TC03 |
| **Spec_Section** | §P1.5 Test Suite, §P1.6 Testing Infrastructure |
| **Requirement_IDs** | P1-TR01, P1-TR02, P1-TR03 |
| **Workflow_Scope** | Global |
| **Deliverable** | P1-H01..H10 test implementations; safety guards for external services; fixtures validation |
| **Acceptance_Criteria** | All hygiene tests pass; any live endpoint call fails the test; WireMock/VCR operational |
| **Verification_Method** | TEST |
| **Test_Cases** | P1-H01, P1-H02, P1-H03, P1-H04, P1-H05, P1-H06, P1-H07, P1-H08, P1-H09, P1-H10 |
| **Oracle_Type** | state-change |
| **Priority** | P0 |
| **Effort** | M |
| **Owner** | QA |
| **Depends_On** | P1-TASK-19 |
| **Blocked_By** | — |
| **Risks** | Hygiene test passes incorrectly → production call in test |
| **Rollback** | N/A (test infra) |
| **Telemetry** | — |
| **Security_Notes** | Hygiene tests are security guards; sandbox keys only |
| **Status** | NOT_STARTED |

---

### P1-TASK-29: Implement Phase 1 Tests + Tags

| Field | Value |
|-------|-------|
| **Task_ID** | P1-TASK-29 |
| **Phase** | P1 |
| **Workstream** | QA |
| **Component** | P1-TC04, P1-TC05, P1-TC08, P1-TC09 |
| **Spec_Section** | §P1.5–P1.10, §P1.12 |
| **Requirement_IDs** | P1-TR04, P1-TR05, P1-TR08, P1-TR09; All P1-R*, INV-*, P1-RH* |
| **Workflow_Scope** | All |
| **Deliverable** | Pytest suites for P1-T01..T41; tags per pipeline (unit/integration_internal/integration_external); oracle assertions per §P1.10; negative tests for INV-01..08; risk tests P1-T-RK01..08 |
| **Acceptance_Criteria** | P0 hygiene + P0 tests 100%; P1 tests ≥95% LCB; artifacts produced; ≥18 negative tests; ≥11 risk tests |
| **Verification_Method** | TEST |
| **Test_Cases** | P1-T01..T41, P1-T01-NEG-*, P1-T02-NEG-*, P1-T05-NEG-*, P1-T07-NEG-*, P1-T-RK01..RK08 |
| **Oracle_Type** | All |
| **Priority** | P0 |
| **Effort** | L |
| **Owner** | QA |
| **Depends_On** | P1-TASK-06..P1-TASK-25, P1-TASK-28 |
| **Blocked_By** | — |
| **Risks** | Tests flaky; oracles drift from reality; missing negative tests |
| **Rollback** | Quarantine flake; regenerate oracle table from test metadata; rerun 3x |
| **Telemetry** | Flake report; per-test pass rate; LCB stats |
| **Security_Notes** | Sandbox keys only; ensure no real contact/charges |
| **Status** | NOT_STARTED |

---

### P1-TASK-30: CI Pipeline Implementation

| Field | Value |
|-------|-------|
| **Task_ID** | P1-TASK-30 |
| **Phase** | P1 |
| **Workstream** | QA |
| **Component** | P1-TC06, P1-TC07 |
| **Spec_Section** | §P1.12 CI Pipeline Specification, §15.6 Flake Policy |
| **Requirement_IDs** | INV-08, P1-R10, P1-TR06, P1-TR07 |
| **Workflow_Scope** | Global |
| **Deliverable** | CI stages (hygiene → unit → integration_internal → integration_external → golden_suite) + timeouts + 3-run LCB logic; artifact upload (coverage, traces, flake_report); flake quarantine implementation |
| **Acceptance_Criteria** | Pipeline matches spec; deploy job blocked on gate evidence; flaky tests quarantined; SLA tracked |
| **Verification_Method** | DEMO |
| **Test_Cases** | P1-T18, P1-T-EXIT-05 |
| **Oracle_Type** | Consistency |
| **Priority** | P0 |
| **Effort** | M |
| **Owner** | DevOps |
| **Depends_On** | P1-TASK-29 |
| **Blocked_By** | — |
| **Risks** | Gate logic wrong; regressions slip OR blocks everything; flake not detected |
| **Rollback** | Roll back CI config; pin runner image; manual override documented |
| **Telemetry** | Stage durations; artifact availability; gate computations; test_flake_total |
| **Security_Notes** | No prod creds in CI; restricted runners |
| **Status** | NOT_STARTED |

---

### P1-TASK-31: Entry Criteria Verification

| Field | Value |
|-------|-------|
| **Task_ID** | P1-TASK-31 |
| **Phase** | P1 |
| **Workstream** | Gate |
| **Component** | — |
| **Spec_Section** | §P1.1 Entry Criteria |
| **Requirement_IDs** | P1-ENTRY-01, P1-ENTRY-02, P1-ENTRY-03, P1-ENTRY-04 |
| **Workflow_Scope** | Global |
| **Deliverable** | Checklist verification: Test-mode credentials configured (ENTRY-01), Design review completed (ENTRY-02), Repo structure initialized (ENTRY-03), CI pipeline skeleton deployed (ENTRY-04) |
| **Acceptance_Criteria** | All 4 entry criteria documented as met; evidence links provided |
| **Verification_Method** | REVIEW |
| **Test_Cases** | — |
| **Oracle_Type** | — |
| **Priority** | P0 |
| **Effort** | S |
| **Owner** | Tech Lead |
| **Depends_On** | P1-TASK-01, P1-TASK-02 |
| **Blocked_By** | — |
| **Risks** | Starting Phase 1 without prerequisites → rework |
| **Rollback** | N/A |
| **Telemetry** | — |
| **Security_Notes** | Test-mode credentials only |
| **Status** | NOT_STARTED |

---

### P1-TASK-32: Soak Test + Exit Criteria Verification

| Field | Value |
|-------|-------|
| **Task_ID** | P1-TASK-32 |
| **Phase** | P1 |
| **Workstream** | Gate |
| **Component** | — |
| **Spec_Section** | §P1.2 Exit Criteria, §H.15 |
| **Requirement_IDs** | P1-EXIT-01..P1-EXIT-14 |
| **Workflow_Scope** | Global |
| **Deliverable** | 7-day production soak test (min 300 events, all workflows exercised); exit criteria verification: P0 tests 100% (EXIT-01), P1 tests ≥95% LCB (EXIT-02), all invariants tested (EXIT-03), soak passed (EXIT-04), external APIs mocked 100% (EXIT-05), negative tests ≥12 (EXIT-06), oracle strategy documented (EXIT-07), risk register tests ≥4 (EXIT-08), LCB gate implemented (EXIT-09), flake policy enforced (EXIT-10), workflow traceability 100% (EXIT-11), success rate measured (EXIT-12), ops dashboards live (EXIT-13), runbooks documented (EXIT-14) |
| **Acceptance_Criteria** | LCB ≥ 0.95 sustained for 7 days; no invariant violations; no P0 incidents; all 14 exit criteria documented as met |
| **Verification_Method** | DEMO |
| **Test_Cases** | — |
| **Oracle_Type** | — |
| **Priority** | P0 |
| **Effort** | XL |
| **Owner** | Tech Lead |
| **Depends_On** | P1-TASK-01..P1-TASK-30 |
| **Blocked_By** | — |
| **Risks** | Soak test reveals issues → Phase 1 delayed; insufficient traffic → inconclusive |
| **Rollback** | Pause soak; address issues; restart |
| **Telemetry** | All dashboards; full observability stack |
| **Security_Notes** | Production data; full security controls active |
| **Status** | NOT_STARTED |

---

## Dependency Matrix

| Task | Depends On |
|------|------------|
| P1-TASK-01 | — |
| P1-TASK-02 | 01 |
| P1-TASK-03 | 02 |
| P1-TASK-04 | 03 |
| P1-TASK-05 | 04 |
| P1-TASK-06 | 01 |
| P1-TASK-07 | 06 |
| P1-TASK-08 | 06 |
| P1-TASK-09 | 08 |
| P1-TASK-10 | 06 |
| P1-TASK-11 | 10 |
| P1-TASK-12 | 03, 10 |
| P1-TASK-13 | 03, 06 |
| P1-TASK-14 | 03, 13 |
| P1-TASK-15 | 06, 07, 08, 09, 10 |
| P1-TASK-16 | 03, 07, 10 |
| P1-TASK-17 | 06, 07, 16 |
| P1-TASK-18 | 17 |
| P1-TASK-19 | 05 |
| P1-TASK-20 | 19, 14 |
| P1-TASK-21 | 19, 13, 14 |
| P1-TASK-22 | 19, 14 |
| P1-TASK-23 | 15, 16, 20, 21, 22 |
| P1-TASK-24 | 03, 04 |
| P1-TASK-25 | 24, 16 |
| P1-TASK-26 | 02 |
| P1-TASK-27 | 10, 16, 25, 26 |
| P1-TASK-28 | 19 |
| P1-TASK-29 | 06..25, 28 |
| P1-TASK-30 | 29 |
| P1-TASK-31 | 01, 02 |
| P1-TASK-32 | 01..30 |

---

## Requirement → Task Traceability

| Requirement | Task(s) |
|-------------|---------|
| INV-01 | 06 |
| INV-02 | 04, 07 |
| INV-03 | 08 |
| INV-04 | 04, 10, 11 |
| INV-05 | 13, 14 |
| INV-06 | 03, 04, 12 |
| INV-07 | 16, 17 |
| INV-08 | 18, 30 |
| P1-R01..R02 | 06, 07 |
| P1-R03..R04 | 08, 09 |
| P1-R05 | 10, 15 |
| P1-R06..R07 | 13, 14 |
| P1-R08 | 12 |
| P1-R09 | 16 |
| P1-R10 | 18, 30 |
| P1-R11..R15 | 20, 21, 22, 23 |
| P1-R16..R17 | 23 (P2 scope) |
| P1-R18..R20 | 06, 07, 17 |
| P1-R21..R25 | 04, 05, 11 |
| P1-R26..R30 | 24, 25 |
| P1-RH01..RH05 | 19, 24 |
| P1-TR01..TR09 | 19, 28, 29, 30 |
| P1-OR01..OR06 | 27 |
| P1-ENTRY-* | 31 |
| P1-EXIT-* | 32 |

---

## Test → Task Traceability

| Test Range | Task(s) |
|------------|---------|
| P1-H01..H10 | 19, 21, 24, 28 |
| P1-T01..T04 | 06, 07 |
| P1-T05..T08 | 08, 09 |
| P1-T09..T10 | 10 |
| P1-T11..T13 | 13, 14 |
| P1-T14..T15 | 12 |
| P1-T16..T17 | 16 |
| P1-T18 | 18, 30 |
| P1-T19..T27 | 20, 21, 22, 23 |
| P1-T28..T30 | 06, 07, 17 |
| P1-T31..T35 | 04, 05, 11 |
| P1-T36..T40 | 24, 25 |
| P1-T41 | 16, 17 |
| P1-T-RK01..RK08 | 15, 25, 04, 11, 29 |
| P1-T-CC01..CC04 | 17 |
| P1-T-NEG-* | 29 |

---

## Effort Summary

| Effort | Count | Developer-Weeks |
|--------|-------|-----------------|
| S | 6 | 3-6 |
| M | 20 | 15-20 |
| L | 3 | 4-6 |
| XL | 1 | 2-3 |
| **Total** | **32** | **28-35** |

---

## Change Log

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-30 | Merged from Claude-54 + Alt-28; adopted Alt-28 structure with Claude-54 traceability |

