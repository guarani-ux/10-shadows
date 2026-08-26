# CURRENT_OBJECTIVE: 10 SHADOWS Shared Kernel Closure & Milestone A

## 1. Active Mission
* **Milestone:** Milestone A — Executable Shared Kernel Route
* **Primary Objective:** Implement an integrated, stateful operating loop governed by a deterministic shared kernel (`CanonicalObjective`, `RunContext`, `kernel.db` transactional persistence, `ArtifactRegistry`, `StepGovernor`, `RouteGovernor`, `BoundedShadowRouter`), and prove an end-to-end 3-Shadow route (`Scribe` -> `Herald` -> `Slicer`) with validated typed handoffs, idempotent artifact lifecycle tracking, deterministic failure injection recovery, and reconstructable receipts.
* **Status:** In Progress (Slice 1 Execution)

---

## 2. Milestone A Success Criteria & Verification Gates
1. **Deterministic RunContext:** Zero timestamp entropy in `canonical_input_hash`; physical Git commit SHA resolved dynamically via `git rev-parse HEAD`.
2. **Unified Transactional Persistence (`scratch/kernel.db`):** Atomic SQLite WAL database containing `runs`, `artifacts`, `artifact_events`, `receipts`, `escalations`, and `approvals`.
3. **Physical Artifact Idempotency & Lifecycle Ledger:** Deterministic 8-tuple idempotency key with unique constraint; append-only `artifact_events` ledger for all state transitions.
4. **Typed Semantic Handoffs:** `StructuredSourceArtifact` (v1.0.0) -> `MasterAVScriptArtifact` (v1.0.0) -> `ProductionPlanDAGArtifact` (v1.0.0) preserving evidence, unknowns, provenance, and authority.
5. **Separation of Governance:** Step-level attempts (1..3 strikes) owned by `StepGovernor`; route-level lifecycle, budgets, and escalation owned by `RouteGovernor`.
6. **Failure Injection & Recovery:** Explicit test seams proving first-attempt failure recovery, oscillation abort, fatal policy abort, human pause/resume, and interrupted route resume.
7. **Zero Regression Gate:** Every Milestone A test passes and all 89 baseline repository tests pass with zero regressions.

---

## 3. Non-Goals for Milestone A
* Alchemist Git worktree commit-and-merge promotion (Reserved for Milestone D).
* Media production golden corpus 5-fixture expansion (Reserved for Milestone B).
* Automated external publication or un-governed learning rule self-promotion.

---

## 4. Current Blocker / Active Step
* **Active Slice:** Slice 1 — Canonical Objective, Transactional Kernel Database, and Deterministic RunContext.
