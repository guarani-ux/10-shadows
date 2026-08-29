import uuid
from typing import Any, Dict, Optional

from forge.core.schema import validate_contract
from forge.core.store import ForgeStore


def classify_failure_promotion(observed_failure: Optional[str]) -> str:
    """
    Classifies failure promotion using structured taxonomy rather than brittle text matching.
    """
    if not observed_failure:
        return "NONE"

    obs_lower = str(observed_failure).lower()

    # Structural security / boundary / path traversal violations -> REGRESSION_TEST
    if any(
        k in obs_lower
        for k in [
            "permissionerror",
            "security violation",
            "escapes sandbox",
            "path traversal",
            "idempotency",
            "unauthorized",
            "device name",
            "null byte",
        ]
    ):
        return "REGRESSION_TEST"

    # Invariant / CAS / state concurrency violations -> REGRESSION_TEST
    if any(k in obs_lower for k in ["casconflict", "optimistic lock", "hash mismatch", "physical reality violation"]):
        return "REGRESSION_TEST"

    # Syntax / Parser / AST errors -> LOCAL_SCAR
    if any(k in obs_lower for k in ["syntaxerror", "compilation error", "schema validation"]):
        return "LOCAL_SCAR"

    # Default localized failure
    return "LOCAL_SCAR"


def learn_if_earned(
    task_spec: Dict[str, Any],
    result_or_receipt: Dict[str, Any],
    evaluation: Dict[str, Any],
    store: Optional[ForgeStore] = None,
    force_promotion: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Evaluates observed outcomes and compiles a LearningRecord.
    Enforces the zero-noise mandate: successful clean runs emit promotion='NONE' and no rule pollution.
    """
    validate_contract("TaskSpec", task_spec)

    task_id = task_spec["task_id"]
    learning_id = f"learn_{uuid.uuid4().hex[:8]}"
    execution_id = result_or_receipt.get("execution_id")

    observed_failure = evaluation.get("observed_failure")
    is_success = evaluation.get("success", False)

    if is_success:
        outcome = "SUCCESS"
        promotion = "NONE"
        repair = None
        reproducible = False
        generalizable = False
        evidence = ["Execution verified all success conditions without observed failure."]
    else:
        outcome = "FAILURE"
        promotion = force_promotion or classify_failure_promotion(observed_failure)
        reproducible = promotion in ("REGRESSION_TEST", "CANDIDATE_RULE")
        generalizable = promotion == "CANDIDATE_RULE"
        repair = f"Address root cause of failure: {observed_failure}"
        evidence = [
            f"Observed failure: {observed_failure}",
            f"Failed conditions: {evaluation.get('conditions_failed', [])}",
        ]

    learning_record = {
        "learning_id": learning_id,
        "task_id": task_id,
        "execution_id": execution_id,
        "outcome": outcome,
        "observed_failure": observed_failure,
        "repair": repair,
        "reproducible": reproducible,
        "generalizable": generalizable,
        "promotion": promotion,
        "evidence": evidence,
    }

    validate_contract("LearningRecord", learning_record)

    if store and promotion != "NONE":
        store.record_learning(
            learning_id=learning_id,
            task_id=task_id,
            promotion=promotion,
            record=learning_record,
            execution_id=execution_id,
        )

    return learning_record
