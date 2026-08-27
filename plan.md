# Grounded Satisfaction Resolution — Master Implementation Plan
*Amended Architecture & Epistemic Verification Specification*

---

## 1. Scope Lock & Architectural Mission

This project is strictly focused on **Grounded Satisfaction Resolution (GSR)**. It is **NOT** a historical consolidation, museum, or archaeology project. Historical mechanisms from prior projects are reused only if they physically exist in the current repository or provide the minimum justified implementation for a demonstrated GSR requirement.

### The Grounded Satisfaction Resolution Lifecycle:

```
RAW INTENT
   ↓
CANONICAL REQUIREMENTS
   ↓
[ OBJECTIVE ADEQUACY GATE ]  ← "Was human objective faithfully & legitimately represented?"
   ↓ (Adequate)
SATISFACTION OBLIGATION DERIVATION  ← "What must become observably true?"
   ↓
GROUNDED SATISFACTION RESOLVER  ← Recursive Frontier Closure & Semantic Contract Binding
   ↓
RESOLUTION PROOF  ← Machine-Induced RequiredOperations & Sealed Exact Capability Bindings
   ↓
EXECUTION GRAPH COMPILER  ← Direct Binding from ResolutionProof (No Re-selection)
   ↓
AUTHORIZED SANDBOXED EXECUTION & PHYSICAL VERIFIERS  ← Worktree / Kernel DB / Receipts
   ↓
EARNED RECURSIVE IMPROVEMENT  ← Physical Verifier Acceptance Fixtures
```

---

## 2. Core Architectural Amendments

### A. Authority Separation (Interpretation vs. Solution)
- **Objective Adequacy Gate (`Forge/core/adequacy.py`):** Answers strictly: *"Was the human objective faithfully and legitimately represented?"* Evaluates bijective clause coverage, semantic additions, and ambiguity preservation. Does **not** derive satisfaction obligations or search capabilities.
- **Obligation Derivation (`Forge/core/obligations.py` or `resolution.py`):** Takes an adequate `CanonicalObjective` and derives the formal `SatisfactionObligation`s answering: *"What must become observably true to satisfy that adequate objective?"*

### B. System-Induced vs. Model Proposals (Epistemic Authority)
- Models may propose semantic interpretations, candidate obligations, candidate bindings, and candidate derived requirements.
- **Model Proposal Authority Invariant:** Model proposals possess **ZERO execution authority** by generation alone. They become authoritative only through:
  1. Source traceability to explicit intent/evidence,
  2. Provenance-backed physical capability contracts,
  3. System invariants, or
  4. Explicit human approval gate.
- No brittle regex-only rule replacements for semantic interpretation; deterministic validation gates verify model proposals.

### C. Capability Trust & Provenance Classification (`CapabilityKind`)
`CapabilityKind` serves strictly as a **trust and provenance classification**, not a domain taxonomy:
- `PHYSICAL_ADAPTER`: Real local subsystem implementation (Authorized for production closure).
- `VERIFIED_EXTERNAL_ADAPTER`: Formally verified external adapter (Authorized for production closure).
- `NON_AUTHORITATIVE_TEST_DOUBLE`: Mock, stub, or test double (Forbidden from satisfying production closure).
- `UNAVAILABLE`: Staging, deprecated, or missing capability.

### D. Physical Precision vs. False Generality
- Binding a manifest to real code does not establish general applicability.
- Every physical capability must explicitly declare:
  - Exact input schema & types (no loose kwargs),
  - Exact output schema & observable side-effects,
  - Exact limitations & applicable operational contexts,
  - Authority requirements (e.g., `SANDBOX_FILE_WRITE`, `SUBPROCESS_EXECUTE`),
  - Evidence requirements & provenance,
  - Deterministic verifier function.
- Domain-specific tools are not exposed as generic operators merely because they map to broad verbs (`EXTRACT`, `TRANSFORM`, `ACT`).

---

## 3. Non-Negotiable System Invariants

1. **OperatorType Inequality Law:** `OperatorType` equality (e.g., both are `COMPARE`) never establishes capability-obligation compatibility. Exact schema subsumption and effect contracts govern compatibility.
2. **Zero Injected Operations:** Callers, tests, and evaluators are strictly forbidden from injecting candidate `RequiredOperation`s or `VerificationContract`s into production runs. Operations are strictly machine-induced from frontier closure.
3. **No Globally Assumed Domain Inputs:** No arbitrary global inputs (`force`, `area`, `claims`) are assumed to exist. Every root input must physically exist in the initial environment or be reachably produced by upstream operations.
4. **Complete Blocking Verification Coverage:** `DecompositionProof.closure_status == SATISFIED` requires 100% blocking verification contract coverage over all operations.
5. **ResolutionProof Seals Exact Identities:** `ResolutionProof` cryptographically seals exact capability IDs. The compiler must bind directly from the proof without re-selecting or substituting capabilities.
6. **Tested Artifact == Executable Artifact:** Dynamic capabilities synthesized by provisioners must execute real physical acceptance tests in sterile isolation before advancing to `VERIFIED_FOR_TASK`.
7. **No Direct Lifecycle Mutation in Tests:** Acceptance tests are forbidden from manually altering `manifest.lifecycle_state` or calling `record_reuse()` to fake promotion. Promotion requires true independent task execution and physical verifier receipts.
8. **Ingress Convergence:** Raw string intent and structured JSON envelopes follow the exact same execution law and pass through identical adequacy, obligation, resolution, and execution gates.
9. **Subsystem Reuse:** Leverage existing repository assets (`KernelDatabase`, `Governor`, `AuthorizationGate`, `ReceiptStore`, `GitWorktreeHarness`, `validate_ast_security`, `run_isolated_pytest`) before creating new equivalents.

---

## 4. Proposed Changes by Component

```
c:\10 SHADOWS\
├── Forge\
│   ├── core\
│   │   ├── substrate.py         [MODIFY] Finalize CapabilityKind (trust-only), SatisfactionObligation, CapabilityBinding, ResolutionDeficit, ResolutionProof
│   │   ├── registry.py          [MODIFY] Bind real SVRIS contradiction, SVRIS extractor, DAG engine, AST gate, pytest runner, sandbox file adapter with exact contracts
│   │   ├── obligations.py       [NEW] Satisfaction obligation derivation from adequate CanonicalObjective
│   │   ├── resolution.py        [NEW] GroundedSatisfactionResolver: recursive frontier closure, deficit emission, operation induction
│   │   ├── adequacy.py          [MODIFY] Keep strictly focused on intent representation adequacy (separate from obligation derivation)
│   │   ├── decomposition.py     [MODIFY] Remove word-overlap heuristics; verify exact contract reachability without global input assumptions
│   │   ├── closure.py           [MODIFY] Validate bound capability kinds, exact contracts, and enforce Anti-Cheating Invariant
│   │   ├── compiler.py          [MODIFY] Compile execution graph directly from ResolutionProof capability bindings
│   │   ├── provisioner.py       [MODIFY] Require real physical test fixture execution in isolated workspace before VERIFIED_FOR_TASK
│   │   └── forge.py             [MODIFY] Wire end-to-end GSR pipeline; remove operation injection from production path
│   └── adapters\
│       └── actions.py           [MODIFY] Ensure physical path-safe execution
├── loop_engine\
│   └── runners\
│       └── forge_runner.py      [MODIFY] Wire ForgeDomainRunner directly into the hardened GroundedSatisfactionResolver
└── tests\
    └── test_grounded_satisfaction_resolution.py [NEW] Permanent 12-rule adversarial test battery + 4 normal-ingress domain traces
```

---

## 5. Detailed Component Specifications

### 1. Substrate Primitives ([`Forge/core/substrate.py`](file:///c:/10%20SHADOWS/Forge/core/substrate.py))
- `CapabilityKind`: `PHYSICAL_ADAPTER`, `VERIFIED_EXTERNAL_ADAPTER`, `NON_AUTHORITATIVE_TEST_DOUBLE`, `UNAVAILABLE`.
- `SatisfactionObligation`: `obligation_id`, `source_requirement_ids`, `required_effect_type`, `required_input_contract`, `required_output_contract`, `required_evidence`, `required_authority`, `required_verification`, `is_blocking`.
- `CapabilityBinding`: `obligation_id`, `capability_id`, `kind`, `confidence`, `input_mapping`, `output_mapping`.
- `ResolutionDeficit`: `deficit_id`, `deficit_type` (`CAPABILITY_DEFICIT`, `EVIDENCE_DEFICIT`, `AUTHORITY_DEFICIT`, `VERIFIER_DEFICIT`, `SEMANTIC_BINDING_DEFICIT`, `DOMAIN_MODEL_DEFICIT`, `REPRESENTATION_DEFICIT`, `INPUT_DEFICIT`), `obligation_id`, `resolution_route`.
- `ResolutionProof`: `objective_hash`, `closed: bool`, `bindings: List[CapabilityBinding]`, `induced_operations: List[RequiredOperation]`, `induced_contracts: List[VerificationContract]`, `deficits: List[ResolutionDeficit]`.

### 2. Truthful Physical Capability Registry ([`Forge/core/registry.py`](file:///c:/10%20SHADOWS/Forge/core/registry.py))
- Exposes physical subsystems with exact, non-generic input/output/limitation contracts:
  1. `svris_contradiction_detector`: Physical SVRIS contradiction detector (`svris.core.contradiction`).
  2. `svris_structured_extractor`: Physical SVRIS structured claim extractor (`svris.core.extractor`).
  3. `shadow_dag_decomposer`: Physical 10 Shadows DAG engine (`graphlib` / topological sort).
  4. `shadow_ast_repair`: Physical AST syntax parser and patcher (`loop_engine.verifiers.ast_gate`).
  5. `shadow_sterile_pytest`: Physical isolated pytest execution bridge (`loop_engine.verifiers.test_gate`).
  6. `forge_sandbox_file_adapter`: Physical sandboxed file mutation adapter (`Forge.adapters.actions.SandboxFileAdapter`).
  7. `forge_authorization_gate`: Physical authorization gate (`Forge.core.authorize.AuthorizationGate`).
- All physical adapters tagged as `CapabilityKind.PHYSICAL_ADAPTER`. Lambda test doubles explicitly tagged `CapabilityKind.NON_AUTHORITATIVE_TEST_DOUBLE`.

### 3. Obligation Derivation ([`Forge/core/obligations.py`](file:///c:/10%20SHADOWS/Forge/core/obligations.py))
- Takes an adequate `CanonicalObjective` and model interpretations to produce formal, machine-verifiable `SatisfactionObligations`.
- Establishes explicit input contracts, required observable effects, and verification criteria for each requirement.

### 4. Grounded Satisfaction Resolver ([`Forge/core/resolution.py`](file:///c:/10%20SHADOWS/Forge/core/resolution.py))
- **Frontier Expansion:** Starts with derived obligations. Expands missing dependencies into upstream obligations.
- **Contract Matching:** Matches capabilities where `cap.kind == PHYSICAL_ADAPTER`, exact effect types align, input contracts are satisfied by available state, and output contracts satisfy obligation needs.
- **Cycle & Reachability Proof:** Verifies topological acyclicity and root input reachability from initial payload.
- **Operation Induction:** Constructs `RequiredOperation` and `VerificationContract` instances from the closed frontier.

### 5. Hardened Compiler & Provisioner ([`Forge/core/compiler.py`](file:///c:/10%20SHADOWS/Forge/core/compiler.py), [`Forge/core/provisioner.py`](file:///c:/10%20SHADOWS/Forge/core/provisioner.py))
- `ExecutionGraphCompiler`: Accepts `ResolutionProof` and compiles execution graph directly from sealed `CapabilityBindings`. No runtime re-selection.
- `CapabilityProvisioner`: Dynamically provisioned capabilities must pass an independent executable test fixture in a sandbox before receiving `VERIFIED_FOR_TASK` status.

---

## 6. Completion Evidence & Verification Plan

Per the pre-implementation amendment, completion requires proving the following **11 explicit criteria**:

### Required Verification Battery ([`tests/test_grounded_satisfaction_resolution.py`](file:///c:/10%20SHADOWS/tests/test_grounded_satisfaction_resolution.py)):

1. **4 Normal-Ingress Domain Traces (No Injections):**
   - *Trace 1 (Ten Shadows Control):* Multi-step media brief decomposition autonomously resolved from plain text.
   - *Trace 2 (Adjacent Knowledge Work):* RFC contradiction detection using physical SVRIS engine.
   - *Trace 3 (Foreign Technical/Scientific):* Materials stress calculation requiring dynamic capability synthesis.
   - *Trace 4 (Representation-Break Logistics):* Warehouse logistics state mutation with explicit physical verification.
2. **0 Injected Operations / Contracts:** All production runs derive operations and contracts purely through GSR.
3. **0 Evaluator Capability Selections:** Capabilities are bound strictly through registry contract matching in the resolver.
4. **Inspected ResolutionProof:** Complete traceability from `CanonicalRequirement` $\rightarrow$ `SatisfactionObligation` $\rightarrow$ `CapabilityBinding` $\rightarrow$ `InducedOperation` $\rightarrow$ `ExecutionGraph`.
5. **Incompatible Same-OperatorType Rejection:** Proves that sharing `OperatorType.TRANSFORM` does not match incompatible schemas.
6. **Missing-Root-Input Rejection:** Proves that missing input variables (e.g. `force`) emit structured `INPUT_DEFICIT` rather than assuming existence.
7. **Permanent Oracle Anti-Cheating Rejection:** Correct answer rejected with `AntiCheatingViolation` if closure is open.
8. **Representation Deficit Behavior:** Unsupported domain effects emit structured `REPRESENTATION_DEFICIT`.
9. **True Task A $\rightarrow$ Foreign Task B Earned Reuse:** Task A provisions and verifies capability in sandbox; foreign Task B independently discovers, executes, and promotes it without manual test mutations.
10. **Physical Verifier Receipts:** Provisioned capabilities carry verified execution receipts from physical gates.
11. **Global Green Regression:** 100% pass rate across the entire repository test suite:
    ```powershell
    python -m pytest tests/test_grounded_satisfaction_resolution.py -v
    python -m pytest tests/test_forge_system_orchestration.py -v
    python -m pytest tests/test_zero_trust_hardened_kernel.py -v
    python -m pytest tests/test_adversarial_plan_auditor.py -v
    python -m pytest Forge/tests/ -v
    python -m pytest loop_engine/tests/ -v
    ```
