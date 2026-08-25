# ZERO-TRUST SUBAGENT GOVERNANCE (MC/MC PRINCIPLE)

## 1. Minimal Context, Maximum Constraint (MC/MC) Invariant
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
