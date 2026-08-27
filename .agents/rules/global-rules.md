# TEN SHADOWS — GLOBAL SYSTEM RULES

## 1. Execution & Safety

### 1.1 Sandbox Boundary
All terminal commands, generated code, tests, and candidate artifacts must execute inside designated sandbox, staging, worktree, or explicitly authorized repository boundaries.

No operation may silently escape its declared execution boundary.

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

Examples:

- hallucinated factual claims → evidence/provenance gates
- incomplete research → research coverage contracts
- incomplete proposals → artifact completeness contracts
- forgotten requirements → requirement traceability
- prohibited writing patterns → deterministic style validation where possible
- weak sentence structure → bounded quality evaluation
- repeated failure patterns → persistent failure memory
- unsupported interpretation → semantic authority gate
- unverified execution → independent verification
- context drift → canonical objective comparison

A correction that repeatedly depends on human prompting is a candidate for system-level representation.

---

# 4. Completion Is Contractual

An artifact is not complete because the model declares it complete.

Completion must be evaluated against the artifact's explicit contract.

Where applicable, completion may require:

- required sections,
- required evidence,
- requirement coverage,
- source traceability,
- unresolved-question accounting,
- constraint compliance,
- style constraints,
- verification conditions,
- physical artifact existence,
- successful downstream validation.

A fluent artifact that violates its contract remains incomplete.

---

# 5. Research Integrity

Research must distinguish:

- source-provided information,
- verified fact,
- documented metric,
- direct quotation,
- model inference,
- unresolved claim,
- contradiction,
- missing evidence.

Research is not complete merely because many sources were collected.

Research completeness is relative to the questions required to resolve the objective.

Before synthesis, determine:

1. What questions must be answered?
2. Which are supported?
3. Which remain unresolved?
4. Which sources support each consequential claim?
5. What contradictory evidence exists?
6. What evidence would materially change the conclusion?

Unsupported claims may remain hypotheses but may not silently become facts.

---

# 6. Minimum Sufficient Change

## 6.1 Recompose Before Inventing
Before creating a new mechanism, determine whether the required capability can be produced by recomposing existing verified:

- primitives,
- capabilities,
- contracts,
- relationships,
- registries,
- evidence,
- verifiers,
- governors,
- persistence,
- execution paths.

Prefer the smallest upstream change that eliminates the failure class.

## 6.2 Code Is Cost
Additional code creates maintenance, verification, state, and failure surface.

Prefer, in order:

1. removing unnecessary machinery,
2. changing an invariant,
3. changing a relationship,
4. strengthening a contract,
5. strengthening a gate,
6. recomposing existing capabilities,
7. adding minimal new implementation.

Code volume is not capability.

---

# 7. Adversarial Pressure

Before promotion, attempt to falsify the claimed property.

Ask:

- Can the model bypass this?
- Can the evaluator accidentally supply the capability being tested?
- Can a correct answer pass through an illegitimate path?
- Can lexical coincidence satisfy a semantic requirement?
- Can an object self-certify its authority?
- Can missing evidence be manufactured?
- Can a capability certify its own semantic success?
- Can a test pass while the claimed property remains false?
- Can an alternate ingress bypass the invariant?
- Can a representation change break the solution?

Tests must target the claimed property rather than the implementation's preferred path.

---

# 8. Verification Independence

Execution is not proof of correctness.

A capability must not be the sole authority establishing its own semantic success.

Where the claim requires independent verification, use:

- independent computation,
- physical observation,
- schema/invariant checking,
- external authoritative evidence,
- sterile tests,
- deterministic validators,
- human authority where irreducible.

If adequate verification cannot be established:

`VERIFIER_DEFICIT`

---

# 9. Three-Strike Root Cause Law

No bounded repair loop may repeat the same failing strategy indefinitely.

After each failed attempt, record:

- failure classification,
- failure signature,
- attempted remedy,
- evidence produced.

Before another attempt ask:

1. Is this materially different from the previous attempt?
2. Is the failure generated by a deeper architectural condition?
3. Has the representation or governing assumption become invalid?

After three materially failed attempts:

STOP local repair.

Trigger Root Cause Architecture Assessment.

Do not convert the strike limit into three cosmetic rewrites of the same strategy.

---

# 10. State & Custody

State becomes authoritative only when explicitly persisted through its designated authority boundary.

Do not treat:

- model memory,
- transient prompts,
- unpersisted Python objects,
- caller labels,
- inferred state

as durable system truth.

Authority-bearing state must preserve provenance and identity across transitions.

---

# 11. Atomic Mutation

Material state and file mutations must use transactional or recoverable mutation where appropriate.

Prefer:

`INTENT/PENDING → write/stage → verify → atomic promotion → receipt`

Use WAL, compare-and-swap, atomic replacement, worktrees, or equivalent mechanisms according to the mutation type.

No partially completed mutation may masquerade as committed state.

---

# 12. Structural Enforcement

Prefer structural enforcement over fragile textual heuristics.

Use:

- typed schemas,
- AST structure,
- explicit IDs,
- contract relationships,
- hashes,
- state transitions,
- provenance links,
- deterministic validators.

Raw text matching may be used only when the property being enforced is itself textual.

Example:

`em_dash_count == 0`

is legitimately textual.

Semantic correctness is not.

---

# 13. Failure Must Improve the Environment

A verified failure should produce one or more of:

- regression test,
- failure signature,
- new invariant,
- stronger verifier,
- improved contract,
- reusable capability,
- explicit limitation,
- updated evidence,
- corrected representation.

Do not accumulate lessons merely as prose when they can be encoded as executable system pressure.

---

# 14. Capability Promotion

A generated or discovered capability does not become trusted merely because:

- it compiles,
- it ran once,
- the model claims success,
- its output looked correct.

Capability authority must be earned through the appropriate lifecycle.

Reuse and promotion must be supported by verified outcomes, not manually asserted status.

---

# 15. Communication Standard

Outputs should maximize signal.

Avoid:

- filler,
- performative praise,
- unnecessary restatement,
- invented certainty,
- rhetorical padding.

Do not suppress useful explanation merely to appear concise.

When uncertainty, failure, or disagreement materially affects the result, state it directly.

---

# 16. Auto-Boot

On initialization, load the authoritative current-state artifacts that physically exist for the active repository.

Do not depend on stale hardcoded paths.

At minimum resolve, where present:

- active objective,
- current goal,
- system state,
- governing rules,
- failure ledger,
- active implementation plan.

Do not automatically generate a new implementation plan merely because the system initialized.

Generate or replace planning artifacts only when the active objective requires planning.

---

# 17. Legacy Synthesis

When explicitly asked to assess legacy systems or folders:

1. inspect the actual architecture,
2. identify reusable capability,
3. identify obsolete or duplicated machinery,
4. identify conflicts with current invariants,
5. derive the smallest useful synthesis.

Do not adopt a persona as a substitute for an explicit analysis contract.

---

# 18. Stop Condition

Stop expanding an implementation when:

- the target failure class is closed,
- the claimed property is mechanically testable,
- the implementation composes existing verified machinery where possible,
- adversarial acceptance tests exist,
- no known upstream bypass invalidates the property within the declared threat model.

After that point:

USE THE SYSTEM.

Let real tasks expose the next material failure.

---

# 19. Zero-Trust Subagent Governance (MC/MC Principle)

Every subagent dispatched under the 10 SHADOWS architecture MUST strictly adhere to the following isolation laws:

1. **Fresh Instance Invariant:**
   - Every subagent invocation MUST be a completely clean, fresh instance (`ReusedSubagentId: ""` / empty).
   - Zero past conversation history or parent chain-of-thought may be leaked into subagent context.

2. **Minimal Information In (Input Law):**
   - The subagent receives ONLY:
     - The exact JSON `task_spec` (sealed by canonical SHA-256 hash).
     - The target destination filename.
     - The assigned ephemeral worktree path (`scratch/worktrees/<task_id>/`).
     - If retrying under strike: The exact 20-line compacted error trace from the `negative_constraints_ledger`.
   - Conversational preambles, chat filler, or subjective instructions are strictly forbidden.

3. **Maximum Deterministic Guidance (Schema Law):**
   - All inputs and outputs must adhere to strictly defined JSON contracts.
   - Zero subjective room for interpretation: the proposer has an explicit signature to fulfill, and the verifier has an explicit boolean gate to evaluate.

4. **Physical Role Jailing:**
   - **Parent Agent = Governor Only:** Dispatches tasks, verifies receipts, advances state. Never writes production code directly.
   - **forge_proposer = Staging Writer Only:** Writes candidate files to worktree. Never runs tests, never touches master branch.
   - **svris_verifier = Sterile Gate Only:** Evaluates candidate file against AST rules and runs subprocess pytest. Never modifies source code.

