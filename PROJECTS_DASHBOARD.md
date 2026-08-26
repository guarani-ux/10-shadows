# 10 SHADOWS: Master System Dashboard & Project Matrix

This document tracks all active domains, core infrastructure status, ongoing engineering projects, and prioritized technical debt across the `10 SHADOWS` architecture.

---

## 1. Physical Master Domain Status & Runtime Truth

Status is strictly defined by physical runtime evidence:
- **Production-Ready**: End-to-end runner, deterministic verification, feedback-driven adaptation, worktree isolation, SQLite WAL receipts, and rollback proven.
- **Runtime-Proven**: BaseLoop runner paths executing under Governor and passing automated test gates.
- **Implemented & Unit-Tested**: Architecture code and unit tests verified.

| Shadow ID | Domain Name | Classification | Core Capability | Runtime Proof Suite |
| :--- | :--- | :--- | :--- | :--- |
| **Shadow 1** | **The Forge** | Runtime-Proven | Software & Tool Synthesis | [`test_domain_runners_integration.py`](file:///c:/10%20SHADOWS/loop_engine/tests/test_domain_runners_integration.py) |
| **Shadow 2** | **svris** | Production-Ready | AST Static Security & Verification Gate | [`test_slice_4_ast_security.py`](file:///c:/10%20SHADOWS/loop_engine/tests/test_slice_4_ast_security.py), [`test_verifier_daemon.py`](file:///c:/10%20SHADOWS/loop_engine/tests/test_verifier_daemon.py) |
| **Shadow 3** | **The Herald** | Production-Ready | Adaptive Constraint-Governed AV Script Engine | [`test_cross_shadow_integration_e2e.py`](file:///c:/10%20SHADOWS/loop_engine/tests/test_cross_shadow_integration_e2e.py), [`test_slice4_herald_adaptation_proof.py`](file:///c:/10%20SHADOWS/loop_engine/tests/test_slice4_herald_adaptation_proof.py) |
| **Shadow 4** | **The Scout** | Runtime-Proven | Sovereign Media Recon & Semantic Chunking | [`test_slice3_media_runner_e2e.py`](file:///c:/10%20SHADOWS/loop_engine/tests/test_slice3_media_runner_e2e.py) |
| **Shadow 5** | **The Inquisitor** | Implemented | 10-Dimension Adversarial Plan Auditor | [`adversarial-plan-auditor`](file:///c:/10%20SHADOWS/.agents/skills/adversarial-plan-auditor/SKILL.md) |
| **Shadow 6** | **The Scribe** | Runtime-Proven | Relational SQLite WAL & Memory Mining | [`test_slice3_scribe_runner_e2e.py`](file:///c:/10%20SHADOWS/loop_engine/tests/test_slice3_scribe_runner_e2e.py) |
| **Shadow 7** | **The Slicer** | Runtime-Proven | DAG & Task Decomposer Engine | [`test_slice3_slicer_runner_e2e.py`](file:///c:/10%20SHADOWS/loop_engine/tests/test_slice3_slicer_runner_e2e.py) |
| **Shadow 8** | **The Warden** | Production-Ready | Git Worktree Sandboxing & Lifecycle | [`test_git_worktree_harness.py`](file:///c:/10%20SHADOWS/loop_engine/tests/test_git_worktree_harness.py) |
| **Shadow 9** | **The Alchemist** | Production-Ready | Active Closed-Loop Self-Healing & Rollback | [`test_slice3_alchemist_runner_e2e.py`](file:///c:/10%20SHADOWS/loop_engine/tests/test_slice3_alchemist_runner_e2e.py) |
| **Shadow 10**| **The Game Master**| Production-Ready | Dynamic Telemetry HUD & CLI Projector | [`test_slice1_gamemaster_projector.py`](file:///c:/10%20SHADOWS/loop_engine/tests/test_slice1_gamemaster_projector.py), [`cli.py`](file:///c:/10%20SHADOWS/loop_engine/gamemaster/cli.py) |

---

## 2. Integrated Cross-Shadow Vertical Slice (Verified)

* **Integrated Closed Loop (`Herald + Warden + Alchemist + Game Master`):**
  - **Herald AV Synthesis:** Consumes `CanonicalMediaBrief`, enforces binding target WPM budgets, preserves verified evidence/unknowns, rejects AI markers, and emits 9:16 vertical cutdown scripts.
  - **Alchemist Active Self-Healing:** Ingests crash tracebacks, parses `CrashDiagnostic`, generates minimal `SurgicalPatch` preserving indentation, executes isolated pytest verification, commits on success, and executes automatic rollback on test failure.
  - **Truthful Game Master HUD:** Inspects Git branch, commit SHA, working-tree cleanliness, discovered test suites, and SQLite WAL receipt distributions dynamically without hardcoded constants.
  - **Master Test Proof:** `87/87` physical automated tests passing across the entire repository.
