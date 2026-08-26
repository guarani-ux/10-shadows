# 10 SHADOWS: Master System Dashboard & Project Matrix

This document tracks all active domains, core infrastructure status, ongoing engineering projects, and prioritized technical debt across the `10 SHADOWS` architecture.

---

## 1. Master System & Domain Status (10/10 COMPLETE & VERIFIED)

| Shadow ID | Domain Name | Core Purpose | Infrastructure Status | Active Pipeline / Runner |
| :--- | :--- | :--- | :--- | :--- |
| **Shadow 1** | **The Forge** | Software & Tool Builder | ✅ Complete (`73/73` Tests) | [`ForgeDomainRunner`](file:///c:/10%20SHADOWS/loop_engine/runners/forge_runner.py) |
| **Shadow 2** | **svris** | Verification, Custody & Receipts | ✅ Complete (`73/73` Tests) | [`SvrisDomainRunner`](file:///c:/10%20SHADOWS/loop_engine/runners/svris_runner.py) |
| **Shadow 3** | **The Herald** | Intelligent AV Script Generation Engine | ✅ Complete (`73/73` Tests) | [`HeraldAVScriptDomainRunner`](file:///c:/10%20SHADOWS/loop_engine/runners/herald_runner.py) |
| **Shadow 4** | **The Scout** | Recon & YouTube Deconstruction | ✅ Complete (`73/73` Tests) | [`SovereignMediaEngine`](file:///c:/10%20SHADOWS/loop_engine/media/sovereign_media_engine.py) |
| **Shadow 5** | **The Inquisitor** | Adversarial Plan Auditor | ✅ Complete (Skill Grounded) | [`adversarial-plan-auditor`](file:///c:/10%20SHADOWS/.agents/skills/adversarial-plan-auditor/SKILL.md) |
| **Shadow 6** | **The Scribe** | Relational Memory & Knowledge Graph | ✅ Complete (`73/73` Tests) | [`ScribeDomainRunner`](file:///c:/10%20SHADOWS/loop_engine/runners/scribe_runner.py) |
| **Shadow 7** | **The Slicer** | DAG & Slice Decomposer | ✅ Complete (`73/73` Tests) | [`SlicerDomainRunner`](file:///c:/10%20SHADOWS/loop_engine/runners/slicer_runner.py) |
| **Shadow 8** | **The Warden** | Security, Sandboxing & Git Worktrees | ✅ Complete (`GitWorktreeHarness`) | [`GitWorktreeHarness`](file:///c:/10%20SHADOWS/loop_engine/harness/git_worktree.py) |
| **Shadow 9** | **The Alchemist** | Self-Healing & Crash Repair | ✅ Complete (`73/73` Tests) | [`AlchemistDomainRunner`](file:///c:/10%20SHADOWS/loop_engine/runners/alchemist_runner.py) |
| **Shadow 10**| **The Game Master**| Sovereign State Projection & CLI HUD | ✅ Complete (`73/73` Tests) | [`run_cli`](file:///c:/10%20SHADOWS/loop_engine/gamemaster/cli.py) |

---

## 2. Active Subsystems & Workstreams (ALL OPERATIONAL)

* **Shadow 3 (The Herald - AV Script Engine):**
  - [`input_contract.py`](file:///c:/10%20SHADOWS/loop_engine/herald/input_contract.py): `CanonicalMediaBrief` (evidence vs unknowns, goals, personas).
  - [`linguistics.py`](file:///c:/10%20SHADOWS/loop_engine/herald/linguistics.py): `AntiAILinguisticGuard` (deterministic ban on em-dashes and AI-speak buzzwords).
  - [`cinematography.py`](file:///c:/10%20SHADOWS/loop_engine/herald/cinematography.py): `CinematographyValidator` (focal lengths, lighting ratios, motivated B-roll).
  - [`schema.py`](file:///c:/10%20SHADOWS/loop_engine/herald/schema.py): `MasterAVScriptBlueprint` (Section 1 Goals, Section 2 Constraints, Section 3 Master Table).
  - [`generator.py`](file:///c:/10%20SHADOWS/loop_engine/herald/generator.py): `IntelligentAVScriptGenerator` (brief-to-AV synthesis).
  - [`cutdowns.py`](file:///c:/10%20SHADOWS/loop_engine/herald/cutdowns.py): `ModularCutDownExtractor` (15-30s Shorts/Reels derivatives).
  - [`renderer.py`](file:///c:/10%20SHADOWS/loop_engine/herald/renderer.py): `MasterAVMarkdownRenderer` (3-column production markdown).
  - [`herald_runner.py`](file:///c:/10%20SHADOWS/loop_engine/runners/herald_runner.py): `HeraldAVScriptDomainRunner` (`BaseLoop` runner with SQLite WAL receipts).

* **Shadow 4 (The Scout - Media Recon):**
  - [`sovereign_media_engine.py`](file:///c:/10%20SHADOWS/loop_engine/media/sovereign_media_engine.py) + [`semantic_chunker.py`](file:///c:/10%20SHADOWS/loop_engine/media/semantic_chunker.py) + [`visual_extractor.py`](file:///c:/10%20SHADOWS/loop_engine/media/visual_extractor.py).
