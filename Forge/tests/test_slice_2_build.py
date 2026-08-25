from forge.core.build import build
from forge.core.route import compile_route
from forge.core.schema import validate_contract


def test_build_routing_trigger():
    task_spec = {
        "task_id": "task-201",
        "objective": "Build a reusable CSV normalizer script",
        "deliverable": {
            "kind": "CODE",
            "description": "Python script for CSV cleaning"
        },
        "constraints": [],
        "knowns": [],
        "unknowns": [],
        "assumptions": [],
        "success_conditions": ["Handles malformed rows"],
        "requires_external_action": False,
        "reversibility": "REVERSIBLE",
        "risk": "LOW"
    }

    route_decision = compile_route(task_spec)
    assert route_decision["route"] == "BUILD"
    assert validate_contract("RouteDecision", route_decision) is True


def test_build_capability_physical_smoke_test_pass(mock_model, temp_dir):
    artifacts_dir = temp_dir / "artifacts"
    task_spec = {
        "task_id": "task-202",
        "objective": "Create valid python script capability",
        "deliverable": {
            "kind": "CODE",
            "description": "Python data processor"
        },
        "constraints": [],
        "knowns": [],
        "unknowns": [],
        "assumptions": [],
        "success_conditions": ["Valid syntax"],
        "requires_external_action": False,
        "reversibility": "REVERSIBLE",
        "risk": "LOW"
    }

    mock_model.register_response("Forge Capability Synthesizer", {
        "artifact_type": "SCRIPT",
        "responsibility": "Process valid data",
        "artifact_code": "def run(x):\n    return x * 2\n"
    })

    build_spec, artifact = build(task_spec, mock_model, artifacts_dir=artifacts_dir)
    assert validate_contract("BuildSpec", build_spec) is True
    assert artifact["smoke_test_status"] == "PASSED"
    assert (artifacts_dir / f"script_{build_spec['build_id']}.py").exists()


def test_build_capability_physical_smoke_test_fail(mock_model, temp_dir):
    artifacts_dir = temp_dir / "artifacts"
    task_spec = {
        "task_id": "task-203",
        "objective": "Synthesize broken python script",
        "deliverable": {
            "kind": "CODE",
            "description": "Broken script"
        },
        "constraints": [],
        "knowns": [],
        "unknowns": [],
        "assumptions": [],
        "success_conditions": ["Should catch syntax error"],
        "requires_external_action": False,
        "reversibility": "REVERSIBLE",
        "risk": "LOW"
    }

    mock_model.register_response("Forge Capability Synthesizer", {
        "artifact_type": "SCRIPT",
        "responsibility": "Broken syntax processor",
        "artifact_code": "def broken_func(\n    return 123 -- INVALID PYTHON SYNTAX"
    })

    build_spec, artifact = build(task_spec, mock_model, artifacts_dir=artifacts_dir)
    assert artifact["smoke_test_status"] == "FAILED"
    assert "SyntaxError" in str(artifact["smoke_test_error"])
