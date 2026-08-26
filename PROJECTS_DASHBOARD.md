# 10 SHADOWS: Master System Dashboard & Project Matrix

This document tracks all active domains, core infrastructure status, ongoing engineering projects, and prioritized technical debt across the `10 SHADOWS` architecture.

---

## 1. Master System & Domain Status (10/10 COMPLETE)

| Shadow ID | Domain Name | Core Purpose | Infrastructure Status | Active Pipeline / Runner |
| :--- | :--- | :--- | :--- | :--- |
| **Shadow 1** | **The Forge** | Software & Tool Builder | ✅ Complete (`64/64` Tests) | [`ForgeDomainRunner`](file:///c:/10%20SHADOWS/loop_engine/runners/forge_runner.py) |
| **Shadow 2** | **svris** | Verification, Custody & Receipts | ✅ Complete (`64/64` Tests) | [`SvrisDomainRunner`](file:///c:/10%20SHADOWS/loop_engine/runners/svris_runner.py) |
| **Shadow 3** | **The Herald** | Media & AV Script Engine | ✅ Complete (`64/64` Tests) | [`HeraldMediaRunner`](file:///c:/10%20SHADOWS/loop_engine/runners/media_runner.py) |
| **Shadow 4** | **The Scout** | Recon & YouTube Deconstruction | ✅ Complete (`64/64` Tests) | [`SovereignMediaEngine`](file:///c:/10%20SHADOWS/loop_engine/media/sovereign_media_engine.py) |
| **Shadow 5** | **The Inquisitor** | Adversarial Plan Auditor | ✅ Complete (Skill Grounded) | [`adversarial-plan-auditor`](file:///c:/10%20SHADOWS/.agents/skills/adversarial-plan-auditor/SKILL.md) |
| **Shadow 6** | **The Scribe** | Relational Memory & Knowledge Graph | ✅ Complete (`64/64` Tests) | [`ScribeDomainRunner`](file:///c:/10%20SHADOWS/loop_engine/runners/scribe_runner.py) |
| **Shadow 7** | **The Slicer** | DAG & Slice Decomposer | ✅ Complete (`64/64` Tests) | [`SlicerDomainRunner`](file:///c:/10%20SHADOWS/loop_engine/runners/slicer_runner.py) |
| **Shadow 8** | **The Warden** | Security, Sandboxing & Git Worktrees | ✅ Complete (`GitWorktreeHarness`) | [`GitWorktreeHarness`](file:///c:/10%20SHADOWS/loop_engine/harness/git_worktree.py) |
| **Shadow 9** | **The Alchemist** | Self-Healing & Crash Repair | ✅ Complete (`64/64` Tests) | [`AlchemistDomainRunner`](file:///c:/10%20SHADOWS/loop_engine/runners/alchemist_runner.py) |
| **Shadow 10**| **The Game Master**| Sovereign State Projection & CLI HUD | ✅ Complete (`64/64` Tests) | [`run_cli`](file:///c:/10%20SHADOWS/loop_engine/gamemaster/cli.py) |

---

## 2. Active Projects & Workstreams (ALL OPERATIONAL)

* **Project A (YouTube Deconstructor):** `sovereign_media_engine.py` + `semantic_chunker.py` + `visual_extractor.py` + `renderer.py`.
* **Project B (Zero-Trust Governance):** `zero_trust_hook.py` + `.agents/` Proposer/Verifier separation.
* **Project C (Git Worktree Sandboxing):** `git_worktree.py` ephemeral branches.
* **Project D (The Scribe Relational Memory):** `memory_store.py` + `pattern_miner.py`.
* **Project E (The Slicer Goal-to-DAG):** `slicer_engine.py` + `schema.py`.
* **Project F (The Alchemist Self-Healing):** `trace_parser.py` + `repair_strategy.py`.
* **Project G (The Game Master HUD & CLI):** `state_projector.py` + `hud_view.py` + `cli.py`.
