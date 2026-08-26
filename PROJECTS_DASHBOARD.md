# 10 SHADOWS: Master System Dashboard & Project Matrix

This document tracks all active domains, core infrastructure status, ongoing engineering projects, and prioritized technical debt across the `10 SHADOWS` architecture.

---

## 1. Master System & Domain Status (10/10 COMPLETE & ADAPTIVE)

| Shadow ID | Domain Name | Core Purpose | Infrastructure Status | Active Pipeline / Runner |
| :--- | :--- | :--- | :--- | :--- |
| **Shadow 1** | **The Forge** | Software & Tool Builder | ✅ Complete (`82/82` Tests) | [`ForgeDomainRunner`](file:///c:/10%20SHADOWS/loop_engine/runners/forge_runner.py) |
| **Shadow 2** | **svris** | Verification, Custody & Receipts | ✅ Complete (`82/82` Tests) | [`SvrisDomainRunner`](file:///c:/10%20SHADOWS/loop_engine/runners/svris_runner.py) |
| **Shadow 3** | **The Herald** | Adaptive Constraint-Governed AV Script Engine | ✅ Complete (`82/82` Tests) | [`HeraldAVScriptDomainRunner`](file:///c:/10%20SHADOWS/loop_engine/runners/herald_runner.py) |
| **Shadow 4** | **The Scout** | Recon & YouTube Deconstruction | ✅ Complete (`82/82` Tests) | [`SovereignMediaEngine`](file:///c:/10%20SHADOWS/loop_engine/media/sovereign_media_engine.py) |
| **Shadow 5** | **The Inquisitor** | Adversarial Plan Auditor | ✅ Complete (Skill Grounded) | [`adversarial-plan-auditor`](file:///c:/10%20SHADOWS/.agents/skills/adversarial-plan-auditor/SKILL.md) |
| **Shadow 6** | **The Scribe** | Relational Memory & Knowledge Graph | ✅ Complete (`82/82` Tests) | [`ScribeDomainRunner`](file:///c:/10%20SHADOWS/loop_engine/runners/scribe_runner.py) |
| **Shadow 7** | **The Slicer** | DAG & Slice Decomposer | ✅ Complete (`82/82` Tests) | [`SlicerDomainRunner`](file:///c:/10%20SHADOWS/loop_engine/runners/slicer_runner.py) |
| **Shadow 8** | **The Warden** | Security, Sandboxing & Git Worktrees | ✅ Complete (`GitWorktreeHarness`) | [`GitWorktreeHarness`](file:///c:/10%20SHADOWS/loop_engine/harness/git_worktree.py) |
| **Shadow 9** | **The Alchemist** | Self-Healing & Crash Repair | ✅ Complete (`82/82` Tests) | [`AlchemistDomainRunner`](file:///c:/10%20SHADOWS/loop_engine/runners/alchemist_runner.py) |
| **Shadow 10**| **The Game Master**| Sovereign State Projection & CLI HUD | ✅ Complete (`82/82` Tests) | [`run_cli`](file:///c:/10%20SHADOWS/loop_engine/gamemaster/cli.py) |

---

## 2. Active Subsystems & Workstreams (ALL OPERATIONAL)

* **Shadow 3 (The Herald - Adaptive AV Script Engine):**
  - [`input_contract.py`](file:///c:/10%20SHADOWS/loop_engine/herald/input_contract.py): `CanonicalMediaBrief` (evidence vs unknowns, goals, personas).
  - [`feedback.py`](file:///c:/10%20SHADOWS/loop_engine/herald/feedback.py): `ScriptViolation` & `ValidationFeedback` (machine-actionable violation codes, suggested word budget adjustments, and explicit repair strategies).
  - [`validators.py`](file:///c:/10%20SHADOWS/loop_engine/herald/validators.py): `DeterministicScriptValidator` (`audit_blueprint_structured()` emitting structured feedback, binding target WPM bounds, timecode monotonicity, and cutdown validation).
  - [`linguistics.py`](file:///c:/10%20SHADOWS/loop_engine/herald/linguistics.py): `AntiAILinguisticGuard` (deterministic ban on em-dashes and AI buzzwords).
  - [`cinematography.py`](file:///c:/10%20SHADOWS/loop_engine/herald/cinematography.py): `CinematographyValidator` (focal lengths `24mm/85mm`, lighting ratios `2:1/4:1`, motivated B-roll).
  - [`schema.py`](file:///c:/10%20SHADOWS/loop_engine/herald/schema.py): `MasterAVScriptBlueprint` (evidence preservation, validated cut-down scripts, 3-column table).
  - [`generator.py`](file:///c:/10%20SHADOWS/loop_engine/herald/generator.py): `IntelligentAVScriptGenerator` (budget-first synthesis + dynamic feedback-driven sentence assembly).
  - [`cutdowns.py`](file:///c:/10%20SHADOWS/loop_engine/herald/cutdowns.py): `ModularCutDownExtractor` (complete standalone vertical 9:16 scripts).
  - [`renderer.py`](file:///c:/10%20SHADOWS/loop_engine/herald/renderer.py): `MasterAVMarkdownRenderer` (3-column production markdown + evidence ledger).
  - [`herald_runner.py`](file:///c:/10%20SHADOWS/loop_engine/runners/herald_runner.py): `HeraldAVScriptDomainRunner` (`BaseLoop` adaptive runner maintaining feedback state across Governor strikes).
