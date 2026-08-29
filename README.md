# 10 SHADOWS

> Experimental governed execution environment for AI-assisted and deterministic work.

## What Ten Shadows is today

10 SHADOWS is a Python/Rust prototype for executing objectives under explicit authority, isolation, verification, provenance, and capability-reuse rules.

The repository is designed around a separation between **workers that attempt work** and **mechanisms that decide whether the result may be treated as successful or reusable**. Its strongest implemented path is software-oriented governed execution. It is not currently demonstrated as a general-purpose autonomous intelligence or a universally reliable self-extending system.

The canonical Python entrypoint is `ts_run.py`. It can:

- accept an objective string or objective file;
- establish a governed run before invoking a worker;
- query a persistent capability registry for previously qualified matches;
- determine a route and required capabilities;
- create a governed workspace and bind worker authorization to the run;
- invoke a selected builder provider;
- snapshot filesystem state and record created, modified, and deleted artifacts;
- register proposed capabilities initially as `UNQUALIFIED`;
- run an independent verification step;
- retry failed attempts up to a configured bound;
- qualify candidate capabilities after successful verification;
- emit and independently verify execution receipts;
- list capabilities recorded in the capability registry;
- run with `--no-promote` when target mutation is not desired.

These are implementation claims, not claims that every path is currently passing CI.

## Current verification status

**Repository qualification is currently RED on `master`.**

At commit `34fc01643d21d392d1ddb5fbbfc85ebecd0dfb94`, GitHub Actions run #37 failed.

Observed CI state:

- the Rust workspace builds successfully;
- 25 Rust adversarial authority tests are collected;
- 22 pass and 3 fail in the current CI environment;
- the three failing Rust tests are dispatcher-related and fail because the Rust test job invokes Python code without `pydantic` installed;
- the Python/Ruff quality gate also fails;
- because the Python ecosystem job depends on that quality gate, the full Python ecosystem suite is skipped in this run.

Therefore this README does **not** describe the repository as fully qualified, production-ready, or universally verified.

## Capability status vocabulary

Descriptions in this repository should use these meanings:

- **VERIFIED**: the behavior has a current passing verification path relevant to the claim.
- **IMPLEMENTED**: an executable path exists, but current evidence is insufficient to call the broader claim verified.
- **EXPERIMENTAL**: implementation exists but its reliability, integration, or scope remains under active validation.
- **SCAFFOLDED**: interfaces, schemas, adapters, or design structure exist without a complete demonstrated execution path.
- **PLANNED**: described as a target or milestone but not yet implemented as a complete path.

A module name, type definition, Markdown specification, model output, or candidate capability record is not by itself evidence that the capability is verified.

## Major implemented components

### Canonical execution CLI

`ts_run.py` exposes three public command families:

```bash
python ts_run.py run "<objective>"
python ts_run.py verify <receipt.json>
python ts_run.py capabilities list [--status ...]
```

The run command supports target selection, domain labels, builder/verifier selection, bounded attempts, JSON output, and `--no-promote`.

### Master orchestrator

`loop_engine/orchestrator.py` implements a governed attempt loop. It establishes kernel state, queries reusable capabilities, determines routing, creates a workspace, issues worker authorization, records filesystem effects and worker invocations, registers candidate capabilities, invokes independent verification, and conditionally qualifies candidates.

This is a substantial implemented orchestration path. Its existence does not establish successful operation for arbitrary objectives.

### Capability registry

The repository contains a persistent capability registry with explicit epistemic status. The orchestrator searches for qualified reusable capabilities and registers new candidate capabilities as unqualified before verification.

This is an implemented capability-management mechanism. General autonomous capability discovery/acquisition across arbitrary domains is **not** claimed as verified.

### Builder providers

The current canonical orchestrator resolves three provider names:

- `deterministic`
- `gemini`
- `antigravity`

Their present behavior differs materially:

**Deterministic provider:** implemented for a small hard-coded objective family. It can synthesize/test Celsius/Fahrenheit conversion and hydraulic-transient examples and fails closed with `CAPABILITY_DEFICIT` for unsupported objectives.

**Gemini provider:** adapter/scaffold only in the current canonical provider path. It validates authorization and configuration but intentionally returns `CAPABILITY_PROVIDER_UNAVAILABLE`; its live network generation path is not enabled in the sterile sandbox.

**Antigravity provider:** adapter exists and checks for an `ANTIGRAVITY_CLI` bridge. Without that bridge it fails closed. When configured, the current adapter reports execution completion but this alone should not be interpreted as verified general-purpose agent execution.

### Rust trusted kernel

`crates/ten_shadows_kernel` contains the Rust authority/kernel implementation and adversarial authority tests. Current CI proves that the workspace builds and that 22 of 25 adversarial tests pass in run #37. Three dispatcher integration tests currently fail because the Rust CI job lacks a Python runtime dependency required by the dispatcher import path.

The kernel is therefore **implemented and substantially tested, but not currently fully green in CI**.

### Broader cognitive/domain substrate

The repository also contains `loop_engine`, `Forge`, `svris`, `zero_trust_engine`, domain runners, schemas, relational planning, constitutional/evidence machinery, artifact handling, governors, and agent/skill definitions.

These components vary in maturity. Their presence should not be collapsed into a single claim that all Shadows form a fully integrated autonomous operating system. `CURRENT_OBJECTIVE.md` explicitly describes the shared-kernel integrated route as an in-progress milestone.

## Current development objective

`CURRENT_OBJECTIVE.md` is the authoritative human-readable milestone description at present. It identifies **Milestone A: Executable Shared Kernel Route** as in progress and seeks to prove an integrated Scribe -> Herald -> Slicer route with shared state, typed handoffs, recovery, and reconstructable receipts.

That wording is important: this route is a **current objective to prove**, not a completed capability that this README claims already exists end-to-end.

## Intended governing principles

The codebase is being developed around these intended constraints:

1. isolate worker execution from authoritative state;
2. require explicit authority for material mutation;
3. prevent builders from self-certifying success;
4. avoid upgrading epistemic status without evidence;
5. bound repeated failed attempts;
6. require objective/evidence sufficiency before claiming accomplishment.

Where implementation and principle diverge, implementation and current verification evidence take precedence in descriptions of present capability.

## Development checks

The repository provides preflight, fast-check, full-check, Ruff, Rust formatting/clippy, Rust tests, Python tests, and GitHub Actions infrastructure.

```bash
python scripts/preflight.py
python scripts/check_fast.py
python scripts/check_full.py
```

These commands are verification mechanisms. Their existence does not mean the current branch passes them.

## Claim discipline

For Ten Shadows, documentation is part of the epistemic boundary.

Do not describe a capability as current merely because it is:

- named in the architecture;
- represented by a class or schema;
- present in an agent prompt;
- planned in a milestone;
- emitted by a model;
- registered as an unqualified candidate;
- covered only by stale or currently failing evidence.

Prefer the narrowest statement supported by executable code and current evidence. When current CI is red, say so.
