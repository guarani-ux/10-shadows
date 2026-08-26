# 10 SHADOWS: Master System Dashboard & Project Matrix

This document tracks all active domains, core infrastructure status, ongoing engineering projects, and prioritized technical debt across the `10 SHADOWS` architecture.

---

## 1. Master System & Domain Status (10/10 COMPLETE & VERIFIED)

| Shadow ID | Domain Name | Core Purpose | Infrastructure Status | Active Pipeline / Runner |
| :--- | :--- | :--- | :--- | :--- |
| **Shadow 1** | **The Forge** | Software & Tool Builder | ✅ Complete (`78/78` Tests) | [`ForgeDomainRunner`](file:///c:/10%20SHADOWS/loop_engine/runners/forge_runner.py) |
| **Shadow 2** | **svris** | Verification, Custody & Receipts | ✅ Complete (`78/78` Tests) | [`SvrisDomainRunner`](file:///c:/10%20SHADOWS/loop_engine/runners/svris_runner.py) |
| **Shadow 3** | **The Herald** | Production-Grade AV Script Engine | ✅ Complete (`78/78` Tests) | [`HeraldAVScriptDomainRunner`](file:///c:/10%20SHADOWS/loop_engine/runners/herald_runner.py) |
| **Shadow 4** | **The Scout** | Recon & YouTube Deconstruction | ✅ Complete (`78/78` Tests) | [`SovereignMediaEngine`](file:///c:/10%20SHADOWS/loop_engine/media/sovereign_media_engine.py) |
| **Shadow 5** | **The Inquisitor** | Adversarial Plan Auditor | ✅ Complete (Skill Grounded) | [`adversarial-plan-auditor`](file:///c:/10%20SHADOWS/.agents/skills/adversarial-plan-auditor/SKILL.md) |
| **Shadow 6** | **The Scribe** | Relational Memory & Knowledge Graph | ✅ Complete (`78/78` Tests) | [`ScribeDomainRunner`](file:///c:/10%20SHADOWS/loop_engine/runners/scribe_runner.py) |
| **Shadow 7** | **The Slicer** | DAG & Slice Decomposer | ✅ Complete (`78/78` Tests) | [`SlicerDomainRunner`](file:///c:/10%20SHADOWS/loop_engine/runners/slicer_runner.py) |
| **Shadow 8** | **The Warden** | Security, Sandboxing & Git Worktrees | ✅ Complete (`GitWorktreeHarness`) | [`GitWorktreeHarness`](file:///c:/10%20SHADOWS/loop_engine/harness/git_worktree.py) |
| **Shadow 9** | **The Alchemist** | Self-Healing & Crash Repair | ✅ Complete (`78/78` Tests) | [`AlchemistDomainRunner`](file:///c:/10%20SHADOWS/loop_engine/runners/alchemist_runner.py) |
| **Shadow 10**| **The Game Master**| Sovereign State Projection & CLI HUD | ✅ Complete (`78/78` Tests) | [`run_cli`](file:///c:/10%20SHADOWS/loop_engine/gamemaster/cli.py) |

---

## 2. Active Subsystems & Workstreams (ALL OPERATIONAL)

* **Shadow 3 (The Herald - Production-Grade AV Script Engine):**
  - [`input_contract.py`](file:///c:/10%20SHADOWS/loop_engine/herald/input_contract.py): `CanonicalMediaBrief` (binding contract distinguishing verified evidence, assumptions requiring approval, creative proposals, and explicit unknowns).
  - [`validators.py`](file:///c:/10%20SHADOWS/loop_engine/herald/validators.py): `DeterministicScriptValidator` (binding target WPM enforcement, timecode monotonicity, CTA alignment, and cutdown validation).
  - [`linguistics.py`](file:///c:/10%20SHADOWS/loop_engine/herald/linguistics.py): `AntiAILinguisticGuard` (deterministic ban on em-dashes and AI buzzwords).
  - [`cinematography.py`](file:///c:/10%20SHADOWS/loop_engine/herald/cinematography.py): `CinematographyValidator` (focal lengths `24mm/85mm`, lighting ratios `2:1/4:1`, motivated B-roll).
  - [`schema.py`](file:///c:/10%20SHADOWS/loop_engine/herald/schema.py): `MasterAVScriptBlueprint` (evidence preservation, validated cut-down scripts, 3-column table).
  - [`generator.py`](file:///c:/10%20SHADOWS/loop_engine/herald/generator.py): `IntelligentAVScriptGenerator` (synthesizes brief into synchronized dialogue & cinematography).
  - [`cutdowns.py`](file:///c:/10%20SHADOWS/loop_engine/herald/cutdowns.py): `ModularCutDownExtractor` (complete standalone vertical 9:16 scripts).
  - [`renderer.py`](file:///c:/10%20SHADOWS/loop_engine/herald/renderer.py): `MasterAVMarkdownRenderer` (3-column production markdown + evidence ledger).
  - [`herald_runner.py`](file:///c:/10%20SHADOWS/loop_engine/runners/herald_runner.py): `HeraldAVScriptDomainRunner` (`BaseLoop` runner with full deterministic verification gate and SQLite WAL receipts).

* **Shadow 4 (The Scout - Media Recon):**
  - [`sovereign_media_engine.py`](file:///c:/10%20SHADOWS/loop_engine/media/sovereign_media_engine.py) + [`semantic_chunker.py`](file:///c:/10%20SHADOWS/loop_engine/media/semantic_chunker.py) + [`visual_extractor.py`](file:///c:/10%20SHADOWS/loop_engine/media/visual_extractor.py).
