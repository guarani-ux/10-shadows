---
name: zero-trust-loop
description: Standard Operating Procedure for coordinating isolated Proposer and Verifier subagents under the 3-Strike Governor runtime.
---

# ZERO-TRUST SUBAGENT EXECUTION PROTOCOL

This skill defines the strict procedure for executing software tasks without self-grading, collusion, or unverified production writes.

## The 3-Strike Governor State Machine

```
1. PREFLIGHT ADMISSION:
   - Validate staging boundary writability.
   - Seal canonical SHA-256 spec_hash.

2. FORGE PROPOSAL (Subagent 1: forge_proposer):
   - Proposer generates code into scratch/worktrees/<task_id>/ (or staging).
   - Proposer outputs candidate file path.

3. SVRIS VERIFICATION (Subagent 2: svris_verifier):
   - Verifier checks AST static gate (banned calls: eval, exec, os.system, raw sockets).
   - Verifier runs isolated pytest subprocess.
   - Verifier outputs structured receipt {status: PASS/FAIL, exit_code, trace}.

4. GOVERNOR DECISION:
   - IF PASS:
     * Fast-forward merge / atomic commit into master branch.
     * Record receipt to SQLite WAL and Git commit log.
     * Task Complete.
   - IF FAIL:
     * Record failure signature to negative_constraints_ledger.
     * Increment Strike Count (Strike N of 3).
     * IF Strike < 3: Re-invoke forge_proposer with compacted failure trace.
     * IF Strike == 3: Hard Abort, prune worktree sandbox, emit crash receipt.
```

## Anti-Collusion Rules
1. Never allow the Proposer to see test execution or run pytest.
2. Never allow the Verifier to modify source code.
3. The parent agent acts solely as the Governor routing context between subagents.
