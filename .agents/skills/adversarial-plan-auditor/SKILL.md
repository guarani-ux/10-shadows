---
name: adversarial-plan-auditor
description: "Adversarially audits implementation plans for unresolved systems-engineering risks, unsupported assumptions, and missing verification evidence before code is written."
---

# Adversarial Plan Auditor

This skill enforces a rigorous, adversarial pre-build audit on proposed implementation plans, technical specifications, and architecture documents before any code is generated.

## Execution Position

```
draft plan
  → adversarial plan audit (THIS SKILL)
  → corrected and approved plan
  → proposer
  → immutable candidate
  → independent verifier
  → promotion gate
```

---

## Section A: Scope & Applicability Determination

Before applying checks, the auditor must explicitly determine the target system's execution scope. Every dimension and check is classified into one of four states:

1. **APPLICABLE:** The proposed system utilizes this capability or touches this boundary.
2. **NOT APPLICABLE:** The proposed system does not utilize this capability (must state explicit technical rationale; e.g., "SQL-only migration, no Python runtime or subprocess execution").
3. **UNVERIFIED:** The plan relies on external environment assumptions, budget guarantees, or platform constraints without mechanical enforcement proof.
4. **IMPLEMENTATION-DEPENDENT:** The control cannot be resolved at plan-time and must be verified by the physical verifier harness during execution.

*Do not require Python-, Windows-, network-, subprocess-, AST-, or filesystem-specific controls when the proposed design does not use those capabilities.*

---

## Section B: Primary 10 Shadows Integrity Dimensions

Every applicable plan must be evaluated against these core architectural dimensions:

### 1. Production-Path Integrity
- Are changes wired into the real production entrypoint, or do they exist as dead/isolated code?
- Is end-to-end component flow verified rather than routing through artificial wrappers?

### 2. Artifact Provenance & Downstream Consumption
- Are artifacts bound to immutable cryptographic hashes (`content_sha256`, `tree_sha256`)?
- Does downstream logic consume the exact verified artifact rather than a reconstructed copy?

### 3. Single Persistence Authority
- Is all transactional state, run history, and receipt logging anchored to a single database/authority in WAL mode?
- Is split-brain persistence across multiple uncoordinated databases strictly prohibited?

### 4. Immutable Candidate Identity & 8-Point Binding
- Are proposal manifests and verification receipts bound to:
  1. `task_id`
  2. `spec_hash`
  3. `base_commit_sha`
  4. `candidate_commit_sha` (when created)
  5. `candidate_tree_sha` (when created)
  6. `verifier_version`
  7. `acceptance_test_digest`
  8. `env_fingerprint`

### 5. Promotion Authorization & State Machine
- Does promotion follow the strict 6-state custody lifecycle:
  `CANDIDATE_SEALED` → `VERIFYING` → (`VERIFIED` | `REJECTED` | `BLOCKED`) → `PROMOTION_PENDING` → `PROMOTED` → `POST_PROMOTION_VERIFIED`
- Is automatic pushing without verification prohibited? Does promotion verify target branch identity and clean worktree status?

### 6. Interruption Recovery & Reconciliation
- Is promotion designed as an idempotent write-ahead log (WAL) protocol?
- Does the system implement startup reconciliation to safely resolve or rollback interrupted `PROMOTION_PENDING` transactions after unexpected crashes?

### 7. Mock, Fallback & Substitute Detection
- Are route-critical components, databases, and network dependencies tested with real implementations where integration is claimed?
- Are silent fallback paths and test-only mocks that mask defects identified and rejected?

### 8. Concurrency, Retry & Idempotency
- Are retries bounded by exponential backoff with jitter, honoring provider `Retry-After` headers?
- Are mutation operations protected by idempotency keys to prevent duplicate side effects?

### 9. Schema, Compatibility & Regression Protection
- Are data schema changes backward-compatible or explicitly versioned?
- Does the verification plan run existing regression tests alongside new acceptance tests?

### 10. Acceptance-Evidence Quality
- Do test oracles prove defect detection by failing on intentionally corrupted/defective fixtures (negative testing)?
- Are assertions non-vacuous (rejecting `assert True` or trivial existence checks)?

---

## Section C: Conditional Specialist Checks

When specific technologies are declared in scope, apply these conditional rules:

### Python Runtime & AST (Conditional)
- **Interpreter Binding:** Prefer `sys.executable` for Python subprocesses.
- **AST Scope:** Treat AST banned-call scanning as a policy lint, not a security sandbox. Account for dynamic reflection (`getattr`), imports, and aliases.
- **Payload Extraction:** Reject ambiguous multi-fence markdown. Require structured JSON or single-file extraction.

### Subprocess & Process Isolation (Conditional)
- **Environment Allowlist:** Do NOT prescribe `env={}`. Require an explicit allowlisted environment retaining necessary OS runtime variables (`SYSTEMROOT`, `PATH`, `USERPROFILE`, `TMP`) while removing sensitive secrets.
- **PYTHONPATH:** Permit `PYTHONPATH` only when declared as part of the runtime design. Prefer execution inside a clean virtual environment.
- **Stdin & Timeouts:** Require `stdin=subprocess.DEVNULL` for non-interactive commands. Require operation-specific timeouts with process-tree termination (`SIGTERM` / `taskkill /T`).

### Filesystem & Platform Hazards (Conditional)
- **Path Handling:** Use `pathlib` with explicit project-root anchoring. Validate resolved paths remain within authorized boundaries.
- **Serialization:** Use real JSON serializers rather than relying on `.as_posix()` for string safety.
- **Platform Conditions:** Treat Windows file locking (`WinError 32`) and read-only cleanup as platform-conditional checks requiring context managers and error handlers.

### Retention & Evidence Quarantine (Conditional)
- **Preservation Lifecycle:** Do not automatically prune failed worktrees. Transition through: `ACTIVE` → `VERIFIED` | `REJECTED` | `QUARANTINED` → `ELIGIBLE_FOR_CLEANUP` → `PRUNED`.
- **Forensic Quarantine:** Failed candidates, receipts, failure signatures, and full traces must be preserved under `.quarantine/` before workspace cleanup.

### Economic Governors & Failure Attribution (Conditional)
- **Failure Taxonomy:** Classify failures into: `CANDIDATE_FAILURE`, `REGRESSION_FAILURE`, `SPEC_FAILURE`, `ENVIRONMENT_FAILURE`, `NETWORK_FAILURE`, `PERMISSION_FAILURE`, `FLAKY_FAILURE`, `GOVERNOR_FAILURE`.
- **Strike Attribution:** Only `CANDIDATE_FAILURE` and `REGRESSION_FAILURE` consume implementation strikes.
- **Anti-Oscillation:** Track cumulative normalized failure signatures to detect cyclical fixes.

---

## Section D: Finding Severity & Evidence Classification

Every finding must be classified into:

### Severities
- **CRITICAL:** Defect that will cause data loss, torn state, security escape, test bypass, unrecoverable crash, or silent promotion of defective code.
- **HIGH:** Architecture defect that compromises isolation, produces incorrect strike allocation, or causes flaky execution under load.
- **MEDIUM:** Inefficient resource usage, incomplete error compaction, or missing non-critical telemetry.
- **LOW:** Stylistic inconsistency, minor documentation gap, or non-blocking naming issue.

### Finding Status
- **CONFIRMED:** Physically proven defect in plan logic.
- **PLAN-GAP:** Missing specification or unaddressed failure mode in the document.
- **ASSUMPTION:** Plan assumes an external guarantee without mechanical enforcement.
- **IMPLEMENTATION-DEPENDENT:** Requires runtime verifier confirmation.

---

## Section E: Audit Output Protocol

Format every finding strictly as:

```text
[FINDING ID: FINDING NAME]
- Severity: CRITICAL | HIGH | MEDIUM | LOW
- Status: CONFIRMED | PLAN-GAP | ASSUMPTION | IMPLEMENTATION-DEPENDENT
- Applicable Because: <Exact reason this dimension applies to the plan>
- Failure Scenario: <Concrete trigger or execution path where failure occurs>
- Impact: <Observable consequence on system, data, or integrity>
- Required Plan Change: <Specific architectural or text correction>
- Required Verification: <Physical test or acceptance evidence needed>
- Residual Risk: <Remaining risk after plan change is made>
```

Conclude every audit report with the exact summary block:

```text
PLAN AUDIT RESULT: PASS | CONDITIONAL PASS | REVISE | BLOCK

Declared Audit Scope:
- <Dimension>: APPLICABLE | NOT APPLICABLE (<reason>) | UNVERIFIED | IMPLEMENTATION-DEPENDENT

Critical Findings: <Count and IDs>
High Findings: <Count and IDs>
Unverified Assumptions: <List of assumptions>
Not-Applicable Dimensions: <List and rationale>
Implementation-Dependent Controls: <List of controls delegated to runtime verifier>
Required Acceptance Evidence: <List of physical test requirements>
Residual Risks: <Documented operational risks>

PLAN AUDIT PASSED: No unresolved CRITICAL findings were identified within the declared audit scope. Implementation and operational verification remain required.
```
*(Note: Output `PLAN AUDIT PASSED: ...` only when Result is PASS or CONDITIONAL PASS. If Result is REVISE or BLOCK, omit the pass statement).*

---

## Section F: Explicit Limitations

> [!IMPORTANT]
> **Mandatory Audit Limitation:**
> Passing this plan audit proves only that no unresolved CRITICAL findings were identified within the declared scope. It does not prove that the implementation is correct, secure, complete, operationally proven, or vulnerability-free.
