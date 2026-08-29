# CAPABILITY GROUND TRUTH

This is the canonical present-tense capability ledger for the Ten Shadows reconciliation candidate.

Reconciliation baseline: `master` remained at `34fc01643d21d392d1ddb5fbbfc85ebecd0dfb94` while all changes were developed on `docs/ground-truth-capability-audit`.

Evidence anchor before this truth-surface update: GitHub Actions run #161 on candidate commit `a4fc49c8ac4cc19a399c2701ee86de1ec7b89032` completed successfully. It independently passed Python lint, Python formatting, Rust formatting/clippy, Rust authority tests, fresh-checkout reconstruction, capability-claim discipline, and the full Python ecosystem suite. The Python suite executed 537 tests with no failures and left the checkout clean.

A green suite is evidence for the behaviors it exercises. It is not universal proof of every architectural ambition.

## Evidence vocabulary

- **VERIFIED CAPABILITY** — current executable evidence demonstrates the stated behavior within the stated scope.
- **IMPLEMENTED BUT UNVERIFIED** — an executable path exists, but current evidence is insufficient for the broader claim.
- **PARTIAL / EXPERIMENTAL** — implementation exists while scope, reliability, integration, or usefulness remains under validation.
- **SCAFFOLDED / PLANNED** — interfaces, design structure, or an explicit target exists without a complete demonstrated path.
- **UNSUPPORTED CLAIM** — repository language exceeds implementation or evidence and is not a valid present-tense capability claim.

## VERIFIED CAPABILITY

| Capability | What current evidence establishes |
|---|---|
| Reconstructable repository setup | A fresh GitHub checkout can install documented dependencies, import the core packages, run preflight, load the public CLI, and execute the representative deterministic path without hidden local state. |
| Non-promoting public default | `ts_run.py run` leaves the target unchanged unless explicit promotion is requested. Clean-room CI checks this physically. |
| Kernel-established governed runs | The canonical Python path records a run before invoking a worker and seals a receipt afterward. |
| Bounded attempts | The canonical orchestrator accepts only 1–3 attempts and stops at that bound. This proves bounded retries, not a broader root-cause intelligence. |
| Worker result fidelity | Recorded worker invocation status reflects the worker's actual exit status rather than being automatically labelled successful. |
| Builder/verifier separation | Verification records reject identical builder/verifier identities, and the canonical deterministic builder no longer writes the tests used to qualify its own candidate. |
| Fail-closed unsupported objectives | Controlled objectives outside the implemented deterministic family are reported as capability/verifier deficits instead of being silently treated as success. |
| Narrow deterministic synthesis | The explicit temperature-conversion and hydraulic-transient fixture families can be built and checked by system-owned deterministic oracles. |
| Candidate-first capability status | Newly registered or re-registered capability candidates are UNQUALIFIED before evidence-based qualification. |
| Evidence-gated qualification | Qualification requires passing independent evidence, physical artifact presence, matching hashes, a falsification attempt, and a non-builder verification type. |
| Bounded persistent capability reuse | In the demonstrated temperature fixture, Ten Shadows creates a capability, independently verifies it, preserves its hash-bound artifact, finds it on a later compatible run against another empty target, reuses it, and retains it. |
| Receipt tamper detection anchored to persisted state | Recomputing the receipt's SHA-256 integrity digest after altering a receipt does not make the altered receipt valid; verification also requires equality with the authoritative persisted receipt record. This does not protect against an attacker who can rewrite the authoritative database itself. |
| Verification-scope discipline | Candidate-workspace evidence cannot be silently relabelled as proof that a target repository was behaviorally tested. |
| Dispatcher fail-closed boundaries | The alternate Rust/Python dispatcher rejects mismatched workspace declarations, the authoritative Ten Shadows source as a worker workspace, invalid binding digests, unregistered providers, and missing Gemini credentials. |
| Rust authority test route | The Rust workspace builds and its current authority/adversarial tests pass in CI with its required Python dispatcher dependencies installed. |
| Claim-inflation gate | CI runs `scripts/check_capability_claims.py`, and regression tests prevent known inflated current-state phrases from re-entering canonical truth surfaces. |

## IMPLEMENTED BUT UNVERIFIED

| Capability | Current boundary |
|---|---|
| Explicit copy-based target promotion | An opt-in verified-copy path exists. It is not atomic Git promotion, does not support deletion semantics, and is not promoted here to a stronger guarantee than its tests establish. |
| Alternate Gemini network adapter | The Rust/Python dispatcher has code capable of making a Gemini network request when configured. No live credential-backed canonical evidence currently proves successful external execution through the complete governed route. |
| Git worktree harness | Worktree creation, teardown, source-protection, and merge infrastructure exists separately. The canonical Python `ts_run.py` path does not currently use this harness as its execution workspace. |
| Numerous Shadow-specific runners and engines | Forge, svris, Herald, Scout/media, Scribe, Slicer, Warden, Alchemist, and Game Master components contain executable code and tests, but repository presence does not establish one unified ten-Shadow runtime. |

## PARTIAL / EXPERIMENTAL

| Capability | Current boundary |
|---|---|
| Capability relevance selection | Persistent retrieval affects future execution, but current matching is lexical/keyword-based, not demonstrated semantic understanding. |
| Recovery and repair | Retry, failure evidence, repair fixtures, governors, and Alchemist-related machinery exist, but broad autonomous root-cause repair is not demonstrated through the canonical path. |
| Workspace isolation | Canonical Python execution is confined by declared paths, authorization bindings, and controlled adapters. This is a governed staging boundary, not an operating-system security sandbox against arbitrary hostile code. |
| Cross-Shadow integration | Multiple integration paths exist, but the active shared-kernel Scribe -> Herald -> Slicer route is not yet established as the canonical fully proven runtime. |
| Local telemetry/HUD | Game Master telemetry can observe local Git/filesystem/receipt structure, but it is intentionally not allowed to translate module presence or historical receipts into capability proof. |

## SCAFFOLDED / PLANNED

| Capability | Current boundary |
|---|---|
| Canonical live Gemini builder | The canonical `loop_engine/providers/gemini_provider.py` path fails closed; live generation is not enabled there. |
| Canonical Antigravity worker bridge | The adapter fails closed without a real bridge and does not count as an operational provider merely because a configuration hook exists. |
| General autonomous capability acquisition | Ten Shadows has pieces of the loop, but it has not demonstrated open-ended recognition, construction/acquisition, verification, preservation, and reuse across unfamiliar domains. |
| Shared-kernel Scribe -> Herald -> Slicer closure | This remains a development target after reconciliation, not a completed capability. |
| Atomic Git promotion in the canonical execution path | Worktree/promotion infrastructure exists elsewhere, but canonical atomic promotion remains future work. |

## UNSUPPORTED CLAIM

The following are not valid present-tense descriptions of Ten Shadows:

- general-purpose autonomous cognitive operating system;
- production-ready universal execution platform;
- universally self-expanding or self-improving intelligence;
- every Shadow is operational or production-ready because its module, runner, tests, or historical receipts exist;
- canonical Python workspaces provide OS-level sandbox security;
- the SHA-256 authorization binding digest is an unforgeable authorization credential;
- the SHA-256 receipt digest is a cryptographic identity signature;
- behavioral tests automatically prove semantic satisfaction of an open-ended objective;
- broad autonomous self-healing has been demonstrated;
- external providers are operational merely because adapters or configuration variables exist.

## Canonical system truth

Ten Shadows is currently best described as an **experimental governed execution environment for AI-assisted and deterministic work**.

Its demonstrated core is not “an AI that can do anything.” Its demonstrated core is a set of mechanisms that make a bounded worker's activity more accountable: establish the run, constrain the declared work boundary, record what happened, separate candidate work from verification authority, fail closed when capability or evidence is missing, preserve qualified capability artifacts, reuse a demonstrated capability later, and keep claims narrower than the evidence.

The strongest learning claim supported today is **bounded persistent capability reuse for an explicit deterministic fixture family**. General capability expansion remains unproven.

## Claim policy

Implementation outranks description. Current executable evidence outranks implementation intent. The narrowest defensible claim wins.

A module name, architecture diagram, test filename, passing test, local receipt count, generated status file, model statement, or historical milestone may contribute evidence but may not independently upgrade a major capability to VERIFIED.

If current evidence is removed or stops passing, the corresponding VERIFIED label must be downgraded until evidence is restored.
