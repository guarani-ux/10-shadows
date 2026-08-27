---
name: workflow-2-claim-verification
description: "Enforces post-build claim verification, independent verifier handoff, and claim ledger reconciliation before promotion."
---

# WORKFLOW 2 — POST-BUILD CLAIM VERIFICATION

## Purpose
Prevent "implementation complete, looks good" from becoming false closure.

## Steps
1. Implementation finishes.

2. A verifier that did NOT author the implementation receives:
   - frozen approved plan
   - exact git diff
   - current repository
   - acceptance tests
   - CI results

3. Build a claim ledger:

   ```
   PLAN CLAIM
   → IMPLEMENTATION LOCATION
   → TEST THAT PROVES IT
   → PHYSICAL RESULT
   → VERIFIED / UNVERIFIED / FALSE
   ```

4. Check specifically:
   - every required plan change actually exists
   - code is wired into the production path
   - no alternate path bypasses the new invariant
   - tests prove behavior rather than existence
   - negative tests demonstrate defect detection
   - no `assert True`, trivial validators, or self-certification
   - exact tested artifact equals exact candidate being promoted
   - existing regression suite still passes

5. If any material claim is `UNVERIFIED`:
   Do not report "complete."

6. If implementation reveals a new architectural weakness:
   Classify whether it was:
   - missed by the plan audit
   - implementation deviation
   - implementation-dependent discovery
   - genuinely new information

7. Feed missed plan-level weaknesses back into the `adversarial-plan-auditor` so that class of omission is tested automatically in future plans.

8. Promotion requires:
   - approved plan
   - zero unresolved CRITICAL/HIGH findings
   - required acceptance tests physically passed
   - CI green
   - claim ledger closed
