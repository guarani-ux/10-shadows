# CURRENT_OBJECTIVE: 10 SHADOWS Shared Kernel Closure & Milestone A

## 1. Active Mission
* **Milestone:** Milestone A — Executable Shared Kernel Route
* **Primary Objective:** Implement an integrated, stateful operating loop governed by a deterministic shared kernel (`CanonicalObjective`, `RunContext`, `kernel.db` transactional persistence, `ArtifactRegistry`, `StepGovernor`, `RouteGovernor`, `BoundedShadowRouter`), and prove an end-to-end 3-Shadow route (`Scribe` -> `Herald` -> `Slicer`) with validated typed handoffs, idempotent artifact lifecycle tracking, deterministic failure injection recovery, and reconstructable receipts.
* **Status:** In Progress

---

## 2. Milestone A Success Criteria & Verification Gates
1. **Deterministic RunContext:** Zero timestamp entropy in `canonical_input_hash`; physical Git commit SHA resolved dynamically via `git rev-parse HEAD`.
2. **Unified Transactional Persistence (`scratch/kernel.db`):** Atomic SQLite WAL database containing `runs`, `artifacts`, `artifact_events`, `receipts`, `escalations`, and `approvals`.
3. **Physical Artifact Idempotency & Lifecycle Ledger:** Deterministic idempotency key with a uniqueness constraint; append-only `artifact_events` ledger for state transitions.
4. **Typed Semantic Handoffs:** `StructuredSourceArtifact` (v1.0.0) -> `MasterAVScriptArtifact` (v1.0.0) -> `ProductionPlanDAGArtifact` (v1.0.0), preserving evidence, unknowns, provenance, and authority.
5. **Separation of Governance:** Step-level bounded attempts owned by `StepGovernor`; route-level lifecycle, budgets, and escalation owned by `RouteGovernor`.
6. **Failure Injection & Recovery:** Explicit tests for first-attempt failure recovery, oscillation abort, fatal policy abort, human pause/resume, and interrupted route resume.
7. **Zero Regression Gate:** The current Milestone A verification gates and the repository's current baseline test suites pass with zero known regressions. Historical test counts are not treated as permanent acceptance criteria.

---

## 3. Non-Goals for Milestone A
* Alchemist Git worktree commit-and-merge promotion (reserved for a later milestone unless reconciliation establishes that it is required sooner).
* Media-production golden-corpus expansion.
* Automated external publication or ungoverned learning-rule self-promotion.

---

## 4. Reconciliation Constraint

This objective is a target, not evidence of completion. `CAPABILITY_GROUND_TRUTH.md` is the present-tense capability ledger during reconciliation. If implementation, current verification, and this milestone description disagree, the narrower evidence-backed claim governs present capability.
