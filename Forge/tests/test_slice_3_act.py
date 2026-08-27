import pytest
from pathlib import Path
from forge.adapters.actions import SandboxFileAdapter
from forge.core.authorize import AuthorizationGate
from forge.core.execute import execute_action
from forge.core.schema import validate_contract


def test_authorized_execution_happy_path(test_store, sandbox_adapter):
    gate = AuthorizationGate(test_store)
    proposal = {
        "transaction_id": "tx-301",
        "attempt_id": "att-301",
        "task_id": "task-301",
        "operation": {
            "kind": "WRITE_FILE",
            "target": "valid_output.txt",
            "payload": {"content": "Physical verification test"}
        },
        "capability_required": "SANDBOX_FILE_WRITE",
        "idempotency_key": "idem-301",
        "reversible": True,
        "rollback": None
    }

    auth = gate.evaluate_proposal(proposal)
    assert auth["decision"] == "AUTHORIZED"

    receipt = execute_action(auth, proposal["operation"], sandbox_adapter, test_store)
    assert validate_contract("ExecutionReceipt", receipt) is True
    assert receipt["outcome"] == "SUCCESS"
    assert receipt["side_effect_committed"] is True

    written_file = sandbox_adapter.sandbox_root / "valid_output.txt"
    assert written_file.exists()
    assert written_file.read_text(encoding="utf-8") == "Physical verification test"


def test_denial_test_no_side_effect(test_store, sandbox_adapter):
    gate = AuthorizationGate(test_store, allowed_capabilities={"RESTRICTED_ONLY"})
    proposal = {
        "transaction_id": "tx-302",
        "attempt_id": "att-302",
        "task_id": "task-302",
        "operation": {
            "kind": "WRITE_FILE",
            "target": "forbidden.txt",
            "payload": {"content": "Should not exist"}
        },
        "capability_required": "SANDBOX_FILE_WRITE",
        "idempotency_key": "idem-302",
        "reversible": True,
        "rollback": None
    }

    auth = gate.evaluate_proposal(proposal)
    assert auth["decision"] == "DENIED"

    receipt = execute_action(auth, proposal["operation"], sandbox_adapter, test_store)
    assert receipt["outcome"] == "FAILED"
    assert receipt["side_effect_committed"] is False

    forbidden_file = sandbox_adapter.sandbox_root / "forbidden.txt"
    assert not forbidden_file.exists()


def test_replay_idempotency_test(test_store, sandbox_adapter):
    gate = AuthorizationGate(test_store)
    proposal = {
        "transaction_id": "tx-303",
        "attempt_id": "att-303",
        "task_id": "task-303",
        "operation": {
            "kind": "WRITE_FILE",
            "target": "idempotent.txt",
            "payload": {"content": "Run once"}
        },
        "capability_required": "SANDBOX_FILE_WRITE",
        "idempotency_key": "idem-unique-303",
        "reversible": True,
        "rollback": None
    }

    auth1 = gate.evaluate_proposal(proposal)
    assert auth1["decision"] == "AUTHORIZED"

    receipt1 = execute_action(auth1, proposal["operation"], sandbox_adapter, test_store)
    assert receipt1["outcome"] == "SUCCESS"

    # Second attempt with duplicate idempotency key must be DENIED
    proposal_replay = dict(proposal, attempt_id="att-303-b")
    auth2 = gate.evaluate_proposal(proposal_replay)
    assert auth2["decision"] == "DENIED"
    assert "already been issued" in auth2["reason"]


def test_payload_substitution_attack(test_store, sandbox_adapter):
    gate = AuthorizationGate(test_store)
    proposal = {
        "transaction_id": "tx-304",
        "attempt_id": "att-304",
        "task_id": "task-304",
        "operation": {
            "kind": "WRITE_FILE",
            "target": "original.txt",
            "payload": {"content": "Authorized payload"}
        },
        "capability_required": "SANDBOX_FILE_WRITE",
        "idempotency_key": "idem-304",
        "reversible": True,
        "rollback": None
    }

    auth = gate.evaluate_proposal(proposal)
    assert auth["decision"] == "AUTHORIZED"

    # Attacker tries to execute tampered operation with same authorization token
    tampered_operation = {
        "kind": "WRITE_FILE",
        "target": "original.txt",
        "payload": {"content": "MALICIOUS INJECTED PAYLOAD"}
    }

    receipt = execute_action(auth, tampered_operation, sandbox_adapter, test_store)
    assert receipt["outcome"] == "FAILED"
    assert receipt["side_effect_committed"] is False
    assert "Security Violation" in receipt["error"]


def test_target_substitution_path_traversal(test_store, sandbox_adapter):
    gate = AuthorizationGate(test_store)
    proposal = {
        "transaction_id": "tx-305",
        "attempt_id": "att-305",
        "task_id": "task-305",
        "operation": {
            "kind": "WRITE_FILE",
            "target": "../../../etc/passwd",
            "payload": {"content": "evil"}
        },
        "capability_required": "SANDBOX_FILE_WRITE",
        "idempotency_key": "idem-305",
        "reversible": False,
        "rollback": None
    }

    auth = gate.evaluate_proposal(proposal)
    assert auth["decision"] == "DENIED"
    assert "traversal" in auth["reason"].lower()


def test_target_substitution_windows_drive(test_store):
    gate = AuthorizationGate(test_store)
    proposal = {
        "transaction_id": "tx-305-win",
        "attempt_id": "att-305-win",
        "task_id": "task-305",
        "operation": {
            "kind": "WRITE_FILE",
            "target": "C:\\Windows\\System32\\cmd.exe",
            "payload": {"content": "evil"}
        },
        "capability_required": "SANDBOX_FILE_WRITE",
        "idempotency_key": "idem-305-win",
        "reversible": False,
        "rollback": None
    }

    auth = gate.evaluate_proposal(proposal)
    assert auth["decision"] == "DENIED"
    assert "drive" in auth["reason"].lower() or "absolute" in auth["reason"].lower()


def test_sandbox_prefix_sibling_escape(temp_dir):
    sandbox_dir = temp_dir / "sandbox"
    adapter = SandboxFileAdapter(sandbox_dir)

    # Attempt to target sibling folder starting with prefix
    with pytest.raises(PermissionError) as exc_info:
        adapter.execute(
            authorization_id="auth-test",
            operation={
                "kind": "WRITE_FILE",
                "target": "../sandbox_escape/pwn.txt",
                "payload": {"content": "breach"}
            }
        )
    assert "escapes sandbox root" in str(exc_info.value)


def test_failure_receipt_integrity(test_store):
    class BrokenAdapter:
        def execute(self, **kwargs):
            raise RuntimeError("Underlying storage failure")

    gate = AuthorizationGate(test_store)
    proposal = {
        "transaction_id": "tx-306",
        "attempt_id": "att-306",
        "task_id": "task-306",
        "operation": {
            "kind": "WRITE_FILE",
            "target": "broken.txt",
            "payload": {"content": "crash"}
        },
        "capability_required": "SANDBOX_FILE_WRITE",
        "idempotency_key": "idem-306",
        "reversible": True,
        "rollback": None
    }

    auth = gate.evaluate_proposal(proposal)
    assert auth["decision"] == "AUTHORIZED"

    receipt = execute_action(auth, proposal["operation"], BrokenAdapter(), test_store)
    assert validate_contract("ExecutionReceipt", receipt) is True
    assert receipt["outcome"] == "FAILED"
    assert receipt["side_effect_committed"] is False
    assert "Underlying storage failure" in receipt["error"]
