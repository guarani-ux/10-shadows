# 10 SHADOWS

> Experimental governed execution environment for AI-assisted and deterministic work.

For the current evidence-backed capability ledger, see `CAPABILITY_GROUND_TRUTH.md`. For the active development target, see `CURRENT_OBJECTIVE.md`.

## What Ten Shadows is now

Ten Shadows is a Python/Rust prototype for attempting work under explicit rules about authority, evidence, verification, persistence, and reuse. Its central design separates **workers that attempt work** from **mechanisms that decide what may be treated as successful, verified, or reusable**.

The strongest currently demonstrated path is a narrow governed execution loop. It is not demonstrated as a general-purpose autonomous intelligence, a universally self-extending system, or a production-ready platform.

## Canonical Python path

`ts_run.py` is the current public Python entrypoint. It can:

- establish a recorded run before a worker is invoked;
- choose among explicitly supported worker adapters;
- create a governed staging workspace;
- bind a worker invocation to the declared workspace and run;
- observe physical file changes;
- use a system-owned verification oracle for the narrow deterministic objective family;
- reject unsupported objectives and missing verifier/provider capability rather than fabricate success;
- register candidate capabilities as unqualified first;
- qualify candidates only after passing evidence checks;
- preserve hash-bound qualified artifacts in a capability store;
- retrieve and reuse a preserved qualified capability on a later compatible run;
- seal and re-check execution receipts;
- leave the target unchanged by default;
- promote verified copy-based changes only when `--promote` is explicitly supplied.

The demonstrated capability-learning loop is deliberately narrow. It proves persistence and reuse for an explicit deterministic fixture family; it does not prove open-ended autonomous capability expansion.

## Other implemented architecture

The repository also contains a Rust kernel/dispatcher route, domain runners for the named Shadows, verification and epistemic machinery, worktree infrastructure, relational components, repair experiments, media/AV components, and provider adapters. These components have different maturity levels. Their presence does not mean they are all part of one proven end-to-end runtime.

In particular:

- the Rust kernel is a separately implemented and tested authority route; the canonical Python CLI is not merely a thin wrapper around the Rust kernel;
- the canonical Python Gemini and Antigravity providers are not currently proven operational external workers;
- a separate Rust/Python dispatcher path contains a Gemini adapter capable of making a real network request when configured, but that alternate route is not the canonical Python `ts_run.py` provider path and must be evaluated on its own evidence;
- the governed Python workspace is a staging boundary, not an operating-system security sandbox;
- current copy-based promotion is not atomic Git promotion and does not support deletion semantics.

## Evidence vocabulary

Use these terms narrowly:

- **VERIFIED CAPABILITY** — current evidence demonstrates the stated behavior within the stated scope.
- **IMPLEMENTED BUT UNVERIFIED** — executable implementation exists, but evidence is insufficient for the broader claim.
- **PARTIAL / EXPERIMENTAL** — some behavior exists while scope, reliability, or integration remains under validation.
- **SCAFFOLDED / PLANNED** — structure or intent exists without a complete demonstrated path.
- **UNSUPPORTED CLAIM** — repository language exceeds implementation or evidence and must be removed or corrected.

A filename, architecture label, passing unit test, historical receipt, model statement, or registry record does not by itself establish a capability.

## Verification

The repository uses GitHub Actions to independently run Python lint/format checks, Rust format/clippy, Rust authority tests, the Python ecosystem suite, capability-claim discipline, and a fresh-checkout reconstruction path. A green run is evidence for the checks it actually executes; it is not universal proof of every architectural claim.

The reconciliation branch remains a candidate until its final evidence is recorded in `CAPABILITY_GROUND_TRUTH.md` and explicitly approved for merge.

## Current objective

`CURRENT_OBJECTIVE.md` is the active milestone description. It is a target, not evidence that the target has already been completed.
