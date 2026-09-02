# TEN SHADOWS — GLOBAL SYSTEM RULES & WORKFLOW PROTOCOLS

> **Authority note:** this file defines governance rules and desired operating constraints. It is not evidence that every current code path mechanically enforces every rule. Present capability status belongs in `CAPABILITY_GROUND_TRUTH.md`; current verification evidence determines what is actually proven. Where implementation falls short of a rule, the implementation must be fixed or the shortfall must remain explicit.

## 1. Execution & Safety

### 1.1 Execution Boundary Policy
All terminal commands, generated code, tests, and candidate artifacts must execute inside a designated sandbox, staging area, worktree, or explicitly authorized repository boundary.

No operation may silently escape its declared execution boundary. A staging-directory boundary is not to be described as an operating-system sandbox unless OS-level isolation is actually present and verified.

### 1.2 Human Authorization for Material Actions
Do not perform material external mutations without explicit authorization when the active execution mode requires human approval.

Planning, inspection, reasoning, static analysis, and non-mutating verification do not require artificial pauses unless policy explicitly requires them.

### 1.3 Destructive Action Gate
Potentially destructive actions must be explicitly identified before execution.

Examples include:
- deletion
- irreversible replacement
- destructive migration
- branch destruction
- state reset
- bulk overwrite

Use:

`WARNING: POTENTIALLY DESTRUCTIVE ACTION`

and require the appropriate authorization gate.

### 1.4 Scope Lock
Implement only changes required to satisfy the active objective and its verified dependencies.

Do not introduce unrelated:
- refactors
- optimizations
- abstractions
- cleanup
- architecture changes

A discovered improvement outside scope becomes a recorded candidate, not an automatic mutation.

### 1.5 Supported Governed Execution Entrypoint (`ts run`)
For the current Python governed-execution path, the supported public entrypoint is:
`python ts_run.py run "<objective>"` or an installed equivalent.

`start_ten_shadows.py` is a compatibility launcher and delegates governed execution to `ts_run.py`.

Direct invocation of `Forge`, `Gemini`, `Antigravity`, raw worker scripts, or verifier scripts does **not** by itself constitute the canonical governed execution path.

**INVARIANT:**
`NO VALID KERNEL-ISSUED EXECUTION RECEIPT = TEN SHADOWS DID NOT RECORD A GOVERNED EXECUTION.`

A valid execution receipt establishes only the claims explicitly supported by that receipt. It does not automatically prove semantic objective satisfaction, target promotion, or general capability acquisition.

---

# 2. Governing Cognitive Law

## 2.1 Reconstruct Before Solving
Do not inherit the presented framing without testing it.

Before committing to a solution trajectory:

1. identify the actual objective,
2. preserve explicit requirements,
3. identify unknowns and contradictions,
4. determine what must become true,
5. identify required capabilities, evidence, inputs, and verification,
6. determine whether the current representation is sufficient.

The smallest generative structure that explains the problem takes priority over the first apparent decomposition.

## 2.2 Proposal Is Not Authority
AI/model output may propose:

- interpretations,
- decompositions,
- hypotheses,
- candidate capabilities,
- candidate artifacts,
- research directions,
- verification strategies.

Model output does not establish:

- factual truth,
- semantic authority,
- capability authority,
- evidence authority,
- verification authority,
- execution legitimacy.

Correctness of an answer does not retroactively establish legitimacy of the process that produced it.

## 2.3 No Silent Closure
The system must never silently replace a missing element with model inference.

If any required closure is absent, represent the deficit explicitly.

Examples:

- `SEMANTIC_BINDING_DEFICIT`
- `DOMAIN_AUTHORITY_REQUIRED`
- `REPRESENTATION_DEFICIT`
- `CAPABILITY_DEFICIT`
- `INPUT_DEFICIT`
- `EVIDENCE_DEFICIT`
- `VERIFIER_DEFICIT`
- `AMBIGUOUS`

Explicit ignorance is preferable to fabricated competence.

---

# 3. AI Amplification Law

Ten Shadows exists to improve the effective behavior of AI by preserving useful capability while reducing recurrent failure.

The system should progressively convert repeated corrections into persistent environmental pressure.

This is an architectural aim. General autonomous capability growth must not be claimed until demonstrated beyond the narrow capability families currently proven.

---

# 4. Completion Is Contractual

An artifact is not complete because the model declares it complete.
Completion must be evaluated against the artifact's explicit contract.

---

# 5. Research Integrity

Research must distinguish verified facts from model inferences, unresolved claims, and missing evidence.

---

# 6. Minimum Sufficient Change

## 6.1 Recompose Before Inventing
Prefer the smallest upstream change that eliminates the failure class.

## 6.2 Code Is Cost
Code volume is not capability. Prefer deleting unnecessary machinery.

---

# 7. Adversarial Pressure

Before promotion, attempt to falsify the claimed property.

---

# 8. Verification Independence

Execution is not proof of correctness. Capabilities cannot self-certify semantic success.

---

# 9. Three-Strike Root Cause Law

No governed repair loop may exceed 3 attempts before requiring root-cause reassessment or a blocked outcome. A code path that does not mechanically implement that behavior cannot claim this law as verified.

---

# 10. State & Custody

State is authoritative only when explicitly persisted across designated boundaries.

---

# 11. Mutation & Promotion Policy

Material mutations should follow a staged pattern:

`intent/authorization → stage → verify → explicit promotion → receipt`

Do not describe a promotion mechanism as atomic, transactional, Git-based, or rollback-safe unless the specific implementation and evidence establish those properties. The current canonical Python path uses an explicit, verified copy-promotion mechanism and therefore must not inherit stronger labels from earlier architecture documents.

---

# 12. Structural Enforcement

Prefer typed schemas, AST topology, and hashes over fragile textual heuristics.

---

# 13. Failure Must Improve the Environment

Convert verified failures into regression tests, invariants, and stronger verifiers where that change closes a recurrent failure class.

---

# 14. Capability Promotion

Capability authority must be earned through independent evidence appropriate to the claimed scope. Registration is not qualification; qualification is not generality.

---

# 15. Communication Standard

Maximum signal, zero filler, explicit statements of uncertainty or failure.

---

# 16. Auto-Boot

Load physical current-state artifacts for the active repository. Generate planning artifacts only when the active objective requires planning.

---

# 17. Legacy Synthesis

Inspect actual architecture and derive minimal synthesis without persona substitution.

Historical design documents remain useful as provenance but do not override current executable evidence.

---

# 18. Stop Condition

Stop expanding once the target failure class is closed and mechanically tested under adversarial constraints.

---

# WORKFLOWS

- **Workflow 1**: [workflow-1-plan-hardening](file:///c:/10%20SHADOWS/.agents/skills/workflow-1-plan-hardening/SKILL.md)
- **Workflow 2**: [workflow-2-claim-verification](file:///c:/10%20SHADOWS/.agents/skills/workflow-2-claim-verification/SKILL.md)
