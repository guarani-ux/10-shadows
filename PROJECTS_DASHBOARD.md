# 10 SHADOWS: Project Dashboard

This dashboard is a navigation aid for the current repository. It is not an independent source of capability authority.

For present-tense capability claims, use `CAPABILITY_GROUND_TRUTH.md`. For the active milestone, use `CURRENT_OBJECTIVE.md`. Current CI evidence takes precedence over historical test counts or earlier status labels.

---

## Current repository position

Ten Shadows contains substantial implementations across ten named domains plus shared Python/Rust execution, authority, verification, persistence, routing, and provider infrastructure.

The repository is currently under full reconciliation. During this process, domain presence must not be translated automatically into labels such as `Production-Ready`, `Runtime-Proven`, `Operationally proven`, or `Verified`.

The previous version of this dashboard made that mistake. It classified multiple Shadows as production-ready and cited a historical `89/89` test count as repository-wide proof. Those statements are retired because they exceeded the evidence available to this dashboard.

---

## Domain inventory

| Shadow | Domain | Repository role currently represented |
| :--- | :--- | :--- |
| **1** | **The Forge** | Software/tool synthesis structures and runner paths |
| **2** | **svris** | Static/AST verification and related verifier paths |
| **3** | **The Herald** | Structured AV-script generation and validation paths |
| **4** | **The Scout** | Media/reconnaissance and semantic-processing paths |
| **5** | **The Inquisitor** | Adversarial plan-audit skill/rule machinery |
| **6** | **The Scribe** | Structured source, persistence, and memory-oriented paths |
| **7** | **The Slicer** | Task/DAG decomposition and production-planning paths |
| **8** | **The Warden** | Git worktree/sandbox infrastructure |
| **9** | **The Alchemist** | Repair/self-healing experiment paths |
| **10** | **The Game Master** | Local telemetry and status-projection machinery |

These are structural descriptions only. They do not certify end-to-end operational status.

---

## Shared-system reconciliation

The active milestone seeks to prove an integrated Scribe -> Herald -> Slicer route under shared kernel state. That route remains an objective, not a completed repository-wide capability claim.

The current reconciliation is also testing several broader architectural promises that older dashboard language treated as already settled, including:

- whether canonical work really executes inside the isolation mechanism that the architecture describes;
- whether material promotion requires explicit authority rather than happening by default;
- whether builders can ever self-certify or indirectly launder weak evidence into qualification;
- whether receipt claims accurately describe what was actually tested and promoted;
- whether registered capabilities are genuinely reused in later work;
- whether provider labels correspond to executable governed provider routes;
- whether failed attempts, recovery, and promotion are physically consistent with their governing rules.

Until those questions are closed by current evidence, this dashboard does not promote them to verified claims.

---

## Status vocabulary

Use the repository-wide vocabulary defined in `CAPABILITY_GROUND_TRUTH.md`:

- **VERIFIED** — current relevant evidence passes for the stated scope.
- **IMPLEMENTED** — executable implementation exists, but broader proof is insufficient.
- **EXPERIMENTAL** — implementation exists while reliability/integration/scope remains under validation.
- **SCAFFOLDED** — interfaces or structure exist without a complete demonstrated path.
- **PLANNED** — target/milestone, not completed capability.
- **BLOCKED** — a known current failure prevents an otherwise implemented path from completing.

No dashboard, generated HUD, historical receipt count, filename, or test-file count may upgrade a capability status by itself.

---

## Active source of truth

1. `CAPABILITY_GROUND_TRUTH.md` — present capability ledger.
2. Current GitHub verification evidence — current executable evidence.
3. `CURRENT_OBJECTIVE.md` — active target, explicitly not proof of completion.
4. `SYSTEM_STATE.md` and `FAILURE_LEDGER.md` — scoped local telemetry only.

If these disagree, the narrowest claim supported by current executable evidence governs.
