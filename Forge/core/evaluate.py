from pathlib import Path
from typing import Any, Dict, List, Optional
from forge.core.schema import validate_contract


def evaluate(task_spec: Dict[str, Any], outcome_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluates whether the requested deliverable and success conditions were physically satisfied in reality.
    Inspects on-disk files, exit codes, receipts, and artifact compilation statuses.
    """
    validate_contract("TaskSpec", task_spec)

    success_conditions = task_spec.get("success_conditions", [])
    conditions_passed: List[str] = []
    conditions_failed: List[str] = []
    observed_failure: Optional[str] = None

    # Step 1: Direct Error & Status Checks
    if "error" in outcome_result and outcome_result["error"]:
        observed_failure = str(outcome_result["error"])
        conditions_failed.extend(success_conditions)
    elif outcome_result.get("status") in ("FAILED", "CONFLICT"):
        observed_failure = f"Task terminated with status {outcome_result.get('status')}"
        conditions_failed.extend(success_conditions)
    elif outcome_result.get("outcome") == "FAILED":
        observed_failure = f"Execution failed: {outcome_result.get('error', 'Unknown execution error')}"
        conditions_failed.extend(success_conditions)

    # Step 2: Physical Inspection for ACT route
    elif outcome_result.get("side_effect_committed") is True:
        output_payload = outcome_result.get("output", {})
        disk_path_str = output_payload.get("path")
        if disk_path_str:
            disk_path = Path(disk_path_str)
            if not disk_path.exists():
                observed_failure = f"Physical Reality Violation: Promised output file '{disk_path}' does not exist on disk."
                conditions_failed.extend(success_conditions)
            elif disk_path.stat().st_size == 0:
                observed_failure = f"Physical Reality Violation: File '{disk_path}' is empty (0 bytes)."
                conditions_failed.extend(success_conditions)
            else:
                conditions_passed.extend(success_conditions)
        else:
            conditions_passed.extend(success_conditions)

    # Step 3: Physical Inspection for BUILD route
    elif "artifact" in outcome_result:
        artifact = outcome_result["artifact"]
        smoke_status = artifact.get("smoke_test_status")
        if smoke_status == "FAILED":
            observed_failure = f"Physical Reality Violation: Synthesized capability failed physical smoke test: {artifact.get('smoke_test_error')}"
            conditions_failed.extend(success_conditions)
        else:
            # Check content path if written
            content_path = artifact.get("content_path")
            if content_path and not Path(content_path).exists():
                observed_failure = f"Physical Reality Violation: Synthesized artifact file '{content_path}' missing from disk."
                conditions_failed.extend(success_conditions)
            else:
                conditions_passed.extend(success_conditions)

    # Step 4: DIRECT route verification
    else:
        unresolved = outcome_result.get("unresolved", [])
        if unresolved:
            observed_failure = f"Direct execution has unresolved blockers: {unresolved}"
            conditions_failed.extend(success_conditions)
        else:
            conditions_passed.extend(success_conditions)

    is_success = len(conditions_failed) == 0 and observed_failure is None

    return {
        "success": is_success,
        "conditions_passed": conditions_passed,
        "conditions_failed": conditions_failed,
        "observed_failure": observed_failure
    }
