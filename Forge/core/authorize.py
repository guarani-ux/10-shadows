import hashlib
import json
import uuid
from pathlib import Path
from typing import Any, Dict, Optional
from forge.core.schema import validate_contract
from forge.core.store import ForgeStore


def canonical_json(data: Any) -> str:
    """
    Computes deterministic canonical JSON string with sorted keys and no unnecessary whitespace.
    """
    return json.dumps(data, sort_keys=True, separators=(',', ':'))


def compute_operation_hash(operation: Dict[str, Any]) -> str:
    """
    Computes deterministic SHA256 hex digest of the canonical JSON representation of an operation.
    """
    canon = canonical_json(operation)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


class AuthorizationGate:
    """
    Enforces deterministic authorization boundaries before external side effects can be executed.
    """
    def __init__(self, store: Optional[ForgeStore] = None, allowed_capabilities: Optional[set[str]] = None):
        self.store = store
        self.allowed_capabilities = allowed_capabilities or {"SANDBOX_FILE_WRITE", "FILE_WRITE", "LOCAL_IO"}

    def evaluate_proposal(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        validate_contract("ActionProposal", proposal)

        transaction_id = proposal["transaction_id"]
        attempt_id = proposal["attempt_id"]
        capability_required = proposal["capability_required"]
        idempotency_key = proposal["idempotency_key"]
        operation = proposal["operation"]

        # Predicate 1 & 3: Check capability
        if capability_required not in self.allowed_capabilities:
            decision = {
                "transaction_id": transaction_id,
                "attempt_id": attempt_id,
                "decision": "DENIED",
                "reason": f"Required capability '{capability_required}' is not permitted."
            }
            validate_contract("AuthorizationDecision", decision)
            return decision

        # Predicate 2: Cross-platform target path inspection
        target = operation.get("target", "")
        target_obj = Path(target)

        if (
            target_obj.is_absolute()
            or target_obj.drive != ""
            or ".." in target_obj.parts
            or target.startswith("/")
            or target.startswith("\\")
            or ":" in target
            or "\x00" in target
        ):
            decision = {
                "transaction_id": transaction_id,
                "attempt_id": attempt_id,
                "decision": "DENIED",
                "reason": f"Target path '{target}' contains invalid path traversal, drive letter, or absolute path sequences."
            }
            validate_contract("AuthorizationDecision", decision)
            return decision

        # Predicate 4: Idempotency check (Has this exact operation already been authorized/consumed?)
        if self.store:
            existing = self.store.get_authorization_by_idempotency_key(idempotency_key)
            if existing:
                decision = {
                    "transaction_id": transaction_id,
                    "attempt_id": attempt_id,
                    "decision": "DENIED",
                    "reason": f"Idempotency key '{idempotency_key}' has already been issued or consumed."
                }
                validate_contract("AuthorizationDecision", decision)
                return decision

        operation_hash = compute_operation_hash(operation)
        authorization_id = f"auth_{uuid.uuid4().hex[:8]}"

        decision = {
            "transaction_id": transaction_id,
            "attempt_id": attempt_id,
            "decision": "AUTHORIZED",
            "authorization_id": authorization_id,
            "operation_hash": operation_hash,
            "reason": "All authorization predicates and idempotency checks passed."
        }

        validate_contract("AuthorizationDecision", decision)

        if self.store:
            self.store.record_authorization(
                authorization_id=authorization_id,
                transaction_id=transaction_id,
                attempt_id=attempt_id,
                operation_hash=operation_hash,
                idempotency_key=idempotency_key,
                state="AUTHORIZED"
            )

        return decision
