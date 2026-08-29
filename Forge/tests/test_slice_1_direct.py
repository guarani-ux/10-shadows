from forge.core.direct import direct
from forge.core.normalize import normalize
from forge.core.route import compile_route
from forge.core.schema import validate_contract


def test_normalize_intent(mock_model):
    intent_req = {
        "request_id": "req-101",
        "intent": "Summarize the key architectural principles of Forge",
        "context": [],
        "constraints": ["Be concise"],
        "requested_surface": "ANSWER",
    }

    task_spec = normalize(intent_req, mock_model)
    assert validate_contract("TaskSpec", task_spec) is True
    assert task_spec["objective"] == intent_req["intent"]
    assert "Be concise" in task_spec["constraints"]


def test_route_direct_decision():
    task_spec = {
        "task_id": "task-102",
        "objective": "Explain photosynthesis to a child",
        "deliverable": {"kind": "ANSWER", "description": "Simple explanation"},
        "constraints": [],
        "knowns": [],
        "unknowns": [],
        "assumptions": [],
        "success_conditions": ["Clear explanation"],
        "requires_external_action": False,
        "reversibility": "REVERSIBLE",
        "risk": "LOW",
    }

    route_decision = compile_route(task_spec)
    assert route_decision["route"] == "DIRECT"
    assert validate_contract("RouteDecision", route_decision) is True


def test_direct_execution(mock_model):
    task_spec = {
        "task_id": "task-103",
        "objective": "Compare Postgres and SQLite",
        "deliverable": {"kind": "ANALYSIS", "description": "Database comparison"},
        "constraints": [],
        "knowns": [],
        "unknowns": [],
        "assumptions": [],
        "success_conditions": ["List trade-offs"],
        "requires_external_action": False,
        "reversibility": "REVERSIBLE",
        "risk": "LOW",
    }

    result = direct(task_spec, mock_model)
    assert validate_contract("DirectResult", result) is True
    assert result["status"] == "COMPLETE"
    assert result["task_id"] == "task-103"
