import pytest
from forge.core.schema import validate_contract


def test_intent_request_schema():
    valid = {
        "request_id": "req-001",
        "intent": "Explain quantum computing",
        "context": [
            {
                "label": "user_context",
                "content": "Beginner level",
                "source": "USER",
                "authority": "AUTHORITATIVE"
            }
        ],
        "constraints": ["Keep under 200 words"],
        "requested_surface": "ANSWER"
    }
    assert validate_contract("IntentRequest", valid) is True

    # Missing required field
    invalid = {
        "request_id": "req-001",
        "intent": "Explain"
    }
    with pytest.raises(Exception):
        validate_contract("IntentRequest", invalid)


def test_task_spec_schema():
    valid = {
        "task_id": "task-001",
        "objective": "Analyze quarterly revenue report",
        "deliverable": {
            "kind": "ANALYSIS",
            "description": "Revenue breakdown"
        },
        "constraints": ["Use USD"],
        "knowns": ["Q1 was 10M"],
        "unknowns": ["Q4 projections"],
        "assumptions": ["Tax rate 21%"],
        "success_conditions": ["Highlight variance"],
        "requires_external_action": False,
        "reversibility": "REVERSIBLE",
        "risk": "LOW"
    }
    assert validate_contract("TaskSpec", valid) is True


def test_action_proposal_and_decision_schema():
    proposal = {
        "transaction_id": "tx-001",
        "attempt_id": "att-001",
        "task_id": "task-001",
        "operation": {
            "kind": "WRITE_FILE",
            "target": "report.txt",
            "payload": {"content": "data"}
        },
        "capability_required": "SANDBOX_FILE_WRITE",
        "idempotency_key": "idem-001",
        "reversible": True,
        "rollback": None
    }
    assert validate_contract("ActionProposal", proposal) is True

    auth_decision = {
        "transaction_id": "tx-001",
        "attempt_id": "att-001",
        "decision": "AUTHORIZED",
        "authorization_id": "auth-001",
        "operation_hash": "a1b2c3d4",
        "reason": "Approved"
    }
    assert validate_contract("AuthorizationDecision", auth_decision) is True

    denied_decision = {
        "transaction_id": "tx-001",
        "attempt_id": "att-001",
        "decision": "DENIED",
        "reason": "Target path not permitted"
    }
    assert validate_contract("AuthorizationDecision", denied_decision) is True
