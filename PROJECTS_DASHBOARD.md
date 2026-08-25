# 10 SHADOWS: Master System Dashboard & Project Matrix

This document tracks all active domains, core infrastructure status, ongoing engineering projects, and prioritized technical debt across the `10 SHADOWS` architecture.

---

## 1. Master System & Domain Status

| Shadow ID | Domain Name | Core Purpose | Infrastructure Status | Active Pipeline / Runner |
| :--- | :--- | :--- | :--- | :--- |
| **Shadow 1** | **The Forge** | Software & Tool Builder | ✅ Complete (`41/41` Tests) | [`ForgeDomainRunner`](file:///c:/10%20SHADOWS/loop_engine/runners/forge_runner.py) |
| **Shadow 2** | **svris** | Verification, Custody & Receipts | ✅ Complete (`41/41` Tests) | [`SvrisDomainRunner`](file:///c:/10%20SHADOWS/loop_engine/runners/svris_runner.py) |
| **Shadow 3** | **The Herald** | Media & Document Engine | ⏳ In Active Development | [`SovereignMediaEngine`](file:///c:/10%20SHADOWS/loop_engine/media/sovereign_media_engine.py) |
| **Shadow 4** | **The Scout** | Recon & YouTube Deconstruction | ⏳ In Active Development | [`YouTubeDeconstructor`](file:///c:/10%20SHADOWS/loop_engine/media/youtube_deconstructor.py) |
| **Shadow 5** | **The Inquisitor** | Adversarial Plan Auditor | ✅ Complete (Skill Grounded) | [`adversarial-plan-auditor`](file:///c:/10%20SHADOWS/.agents/skills/adversarial-plan-auditor/SKILL.md) |
| **Shadow 6** | **The Scribe** | Knowledge Graph & Memory | 📋 Planned | TBD |
| **Shadow 7** | **The Slicer** | DAG & Slice Decomposer | 📋 Planned | TBD |
| **Shadow 8** | **The Warden** | Security, Sandboxing & Git Worktrees | ✅ Complete (`GitWorktreeHarness`) | [`GitWorktreeHarness`](file:///c:/10%20SHADOWS/loop_engine/harness/git_worktree.py) |
| **Shadow 9** | **The Alchemist** | Self-Healing & System Repair | 📋 Planned | TBD |
| **Shadow 10**| **The Game Master**| Sovereign State Projection & HUD | 📋 Planned | Master System Board |

---

## 2. Active Projects & Workstreams

### 🔴 Project A: The Semantic YouTube Deconstructor & Narrative Engine (Shadow 3 & 4)
* **Goal:** Turn raw YouTube video URLs into industrial-grade, reverse-engineered story blueprints, pacing curves, and anomaly-audited chapter breakdowns.
* **Current State:** Basic ingestion via `yt-dlp` and `youtube-transcript-api` is functional.
* **Identified Technical Debt / Flaws:**
  - ❌ Naive silence-gap detection ($>3.0s$) collapses dialogue into a single monolithic scene.
  - ❌ Missing semantic sentence embedding / LLM topic boundary clustering.
  - ❌ Lacks multi-tier fallback (captions $\rightarrow$ audio download $\rightarrow$ local Whisper).
* **Target Deliverables:**
  1. `loop_engine/media/semantic_chunker.py`: Semantic sliding-window topic shift detector.
  2. `loop_engine/media/schema.py`: Rigid Pydantic contract with `known_blindspots` and verbatim evidence quotes.
  3. `loop_engine/tests/test_semantic_media_deconstructor.py`: Test suite verifying multi-topic segmentation on real-world long-form video.

---

### 🟢 Project B: Zero-Trust Governor & Subagent Governance (Shadow 8 - The Warden)
* **Goal:** Enforce strict separation of powers (Proposer vs. Verifier) and eliminate self-grading.
* **Status:** ✅ Complete & Sealed.
* **Artifacts:**
  - Skill: [`zero-trust-architect`](file:///C:/Users/flowe/.gemini/config/skills/zero-trust-architect/SKILL.md)
  - Proposer: [`.agents/agents/forge_proposer.md`](file:///c:/10%20SHADOWS/.agents/agents/forge_proposer.md)
  - Verifier: [`.agents/agents/svris_verifier.md`](file:///c:/10%20SHADOWS/.agents/agents/svris_verifier.md)
  - Blocker Hook: [`loop_engine/harness/zero_trust_hook.py`](file:///c:/10%20SHADOWS/loop_engine/harness/zero_trust_hook.py)
  - Git Commit: [`5c60284`](file:///c:/10%20SHADOWS)

---

### 🟢 Project C: Industrial Git Worktree Sandboxing (Shadow 8 - The Warden)
* **Goal:** Replace brittle `.bak` and staging swaps with kernel-level ephemeral Git branches.
* **Status:** ✅ Complete (`38/38` pytest passing).
* **Artifacts:**
  - Harness: [`loop_engine/harness/git_worktree.py`](file:///c:/10%20SHADOWS/loop_engine/harness/git_worktree.py)
  - Test Suite: [`loop_engine/tests/test_git_worktree_harness.py`](file:///c:/10%20SHADOWS/loop_engine/tests/test_git_worktree_harness.py)

---

## 3. Immediate Action Backlog

1. **Step 1:** Implement Semantic Sentence Windowing & Topic Shift Detection in `loop_engine/media/semantic_chunker.py` to fix the single-scene collapse.
2. **Step 2:** Integrate Pydantic schema contracts enforcing grounded quotes and explicit anomaly reporting.
3. **Step 3:** Run verification test suite across 3 distinct video genres (Spotlight, Tutorial, Essay).
