from forge.forge import ForgeEngine


def test_acceptance_test_a_direct(test_store, mock_model, temp_dir):
    engine = ForgeEngine(
        store=test_store,
        model_adapter=mock_model,
        sandbox_dir=temp_dir / "sandbox",
        artifacts_dir=temp_dir / "artifacts",
    )

    request = {
        "request_id": "req-acceptance-a",
        "intent": "Explain an unfamiliar concept and give me the decision-relevant implications.",
        "context": [],
        "constraints": ["Keep concise"],
        "requested_surface": "ANSWER",
    }

    result = engine.run_legacy(request)

    assert result["route"] == "DIRECT"
    assert result["evaluation"]["success"] is True
    assert result["learning"]["promotion"] == "NONE"
    assert "result" in result["result"]


def test_acceptance_test_b_build(test_store, mock_model, temp_dir):
    engine = ForgeEngine(
        store=test_store,
        model_adapter=mock_model,
        sandbox_dir=temp_dir / "sandbox",
        artifacts_dir=temp_dir / "artifacts",
    )

    request = {
        "request_id": "req-acceptance-b",
        "intent": "Make a reusable processor that turns this recurring input into this recurring output.",
        "context": [],
        "constraints": ["Single processor"],
        "requested_surface": "SYSTEM",
    }

    result = engine.run_legacy(request)

    assert result["route"] == "BUILD"
    assert result["evaluation"]["success"] is True
    build_spec = result["result"]["build_spec"]
    artifact = result["result"]["artifact"]

    assert len(build_spec["components"]) >= 1
    assert artifact["smoke_test_status"] == "PASSED"

    stored_artifact = test_store.get_artifact(artifact["artifact_id"])
    assert stored_artifact is not None


def test_acceptance_test_c_act(test_store, mock_model, sandbox_adapter, temp_dir):
    engine = ForgeEngine(
        store=test_store,
        model_adapter=mock_model,
        action_adapter=sandbox_adapter,
        sandbox_dir=temp_dir / "sandbox",
        artifacts_dir=temp_dir / "artifacts",
    )

    # Preprogram mock model to signal external mutation needed
    mock_model.register_response(
        "normalize",
        {
            "objective": "Write the generated result to a controlled external target.",
            "deliverable": {"kind": "ACTION", "description": "Write target file"},
            "constraints": [],
            "knowns": [],
            "unknowns": [],
            "assumptions": [],
            "success_conditions": ["Side effect committed and physical file exists"],
            "requires_external_action": True,
            "reversibility": "REVERSIBLE",
            "risk": "LOW",
        },
    )

    request = {
        "request_id": "req-acceptance-c",
        "intent": "Write the generated result to a controlled external target.",
        "context": [],
        "constraints": [],
        "requested_surface": "ACTION",
    }

    result = engine.run_legacy(request)

    assert result["route"] == "ACT"
    receipt = result["result"]
    assert receipt["outcome"] == "SUCCESS"
    assert receipt["side_effect_committed"] is True
    assert result["evaluation"]["success"] is True


def test_acceptance_test_d_learn(test_store, mock_model, temp_dir):
    class CrashingSandboxAdapter:
        def execute(self, **kwargs):
            raise PermissionError("PermissionError: Target path escapes sandbox root")

    engine = ForgeEngine(
        store=test_store,
        model_adapter=mock_model,
        action_adapter=CrashingSandboxAdapter(),
        sandbox_dir=temp_dir / "sandbox",
        artifacts_dir=temp_dir / "artifacts",
    )

    mock_model.register_response(
        "normalize",
        {
            "objective": "Controlled failure action",
            "deliverable": {"kind": "ACTION", "description": "Trigger failure"},
            "constraints": [],
            "knowns": [],
            "unknowns": [],
            "assumptions": [],
            "success_conditions": ["Must execute"],
            "requires_external_action": True,
            "reversibility": "REVERSIBLE",
            "risk": "LOW",
        },
    )

    request = {
        "request_id": "req-acceptance-d",
        "intent": "Controlled failure action",
        "context": [],
        "constraints": [],
        "requested_surface": "ACTION",
    }

    result = engine.run_legacy(request)

    assert result["route"] == "ACT"
    assert result["evaluation"]["success"] is False
    assert result["learning"]["promotion"] == "REGRESSION_TEST"

    # Verify that the regression record is persistently logged
    persisted_learnings = test_store.get_learnings_for_task(result["task_id"])
    assert len(persisted_learnings) == 1
    assert persisted_learnings[0]["promotion"] == "REGRESSION_TEST"
