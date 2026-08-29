import uuid
from typing import Any, Dict, Optional

from forge.adapters.actions import ActionAdapter
from forge.core.authorize import compute_operation_hash
from forge.core.schema import validate_contract
from forge.core.store import ForgeStore


def execute_action(
    authorization_decision: Dict[str, Any],
    operation: Dict[str, Any],
    action_adapter: ActionAdapter,
    store: Optional[ForgeStore] = None,
) -> Dict[str, Any]:
    """
    Executes an authorized action through the ActionAdapter and generates an ExecutionReceipt.
    Enforces payload integrity matching, authorization verification, and failure recording.
    """
    execution_id = f"exec_{uuid.uuid4().hex[:8]}"
    transaction_id = authorization_decision.get("transaction_id", "unknown_tx")
    attempt_id = authorization_decision.get("attempt_id", "unknown_attempt")

    # Step 1: Check authorization decision
    if authorization_decision.get("decision") != "AUTHORIZED":
        receipt = {
            "execution_id": execution_id,
            "transaction_id": transaction_id,
            "attempt_id": attempt_id,
            "authorization_id": authorization_decision.get("authorization_id", "none"),
            "operation_hash": authorization_decision.get("operation_hash", "none"),
            "outcome": "FAILED",
            "side_effect_committed": False,
            "output": {},
            "error": f"Execution rejected: Decision was {authorization_decision.get('decision')} ({authorization_decision.get('reason')})",
        }
        validate_contract("ExecutionReceipt", receipt)
        return receipt

    authorization_id = authorization_decision["authorization_id"]
    authorized_hash = authorization_decision["operation_hash"]

    # Step 2: Predicate 5 - Payload substitution guard (operation must match authorized hash)
    actual_hash = compute_operation_hash(operation)
    if actual_hash != authorized_hash:
        receipt = {
            "execution_id": execution_id,
            "transaction_id": transaction_id,
            "attempt_id": attempt_id,
            "authorization_id": authorization_id,
            "operation_hash": authorized_hash,
            "outcome": "FAILED",
            "side_effect_committed": False,
            "output": {},
            "error": f"Security Violation: Executing operation hash '{actual_hash}' does not match authorized hash '{authorized_hash}'",
        }
        validate_contract("ExecutionReceipt", receipt)
        return receipt

    # Step 3: Consume authorization to prevent token reuse
    if store:
        consumed = store.consume_authorization(authorization_id)
        if not consumed:
            receipt = {
                "execution_id": execution_id,
                "transaction_id": transaction_id,
                "attempt_id": attempt_id,
                "authorization_id": authorization_id,
                "operation_hash": authorized_hash,
                "outcome": "FAILED",
                "side_effect_committed": False,
                "output": {},
                "error": "Authorization token has already been consumed or is invalid.",
            }
            validate_contract("ExecutionReceipt", receipt)
            return receipt

    # Step 4: Execute side effect through adapter
    try:
        output = action_adapter.execute(authorization_id=authorization_id, operation=operation)
        receipt = {
            "execution_id": execution_id,
            "transaction_id": transaction_id,
            "attempt_id": attempt_id,
            "authorization_id": authorization_id,
            "operation_hash": authorized_hash,
            "outcome": "SUCCESS",
            "side_effect_committed": True,
            "output": output,
            "error": None,
        }
    except Exception as e:
        receipt = {
            "execution_id": execution_id,
            "transaction_id": transaction_id,
            "attempt_id": attempt_id,
            "authorization_id": authorization_id,
            "operation_hash": authorized_hash,
            "outcome": "FAILED",
            "side_effect_committed": False,
            "output": {},
            "error": str(e),
        }

    validate_contract("ExecutionReceipt", receipt)
    return receipt
