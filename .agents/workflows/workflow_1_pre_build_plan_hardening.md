# WORKFLOW 1 — PRE-BUILD PLAN HARDENING

## Purpose
Prevent weak plans from reaching implementation.

## Steps
1. Draft implementation plan.

2. BEFORE ANY CODE:
   Load:
   - current repository state
   - current objective
   - global rules
   - failure ledger
   - proposed plan

3. Run the existing `adversarial-plan-auditor`.

4. The auditor must actively attempt to falsify the plan:
   - production-path bypasses
   - hidden model/evaluator capability
   - unsupported authority
   - incomplete closure
   - weak verification
   - self-certification
   - missing negative tests
   - stale assumptions about current code
   - dead/unwired implementation paths
   - regression risk
   - failure/recovery paths
   - alternative representations that break the design

5. NO IMPLEMENTATION if:
   - PLAN AUDIT RESULT = `REVISE` or `BLOCK`
   - any unresolved `CRITICAL` exists
   - any unresolved `HIGH` exists
   - required acceptance evidence is unspecified

6. If findings exist:
   Revise the PLAN, not the code.

7. Re-audit the revised plan from scratch.

8. Maximum 3 plan-hardening iterations.
   If it still fails:
   Stop and perform Root Cause Architecture Assessment.

9. Once the plan passes:
   Freeze the exact approved plan and record its hash.

10. Only then may implementation begin.

The implementing agent may not silently reinterpret or expand the frozen plan.
