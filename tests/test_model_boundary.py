"""
tests/test_model_boundary.py
Tests for the Canonical Provider-Agnostic Model Boundary (10 SHADOWS).
"""

from loop_engine.model.boundary import (
    DeficitDeclaration,
    DeficitType,
    EvidenceModality,
    GeminiModelAdapter,
    InferenceEffort,
    MockModelAdapter,
    MockModelProfile,
    ModelRequest,
    ModelResponse,
)


def test_model_request_and_response_schema():
    req = ModelRequest(
        task_id="task_req_01",
        operation_type="SYNTHESIZE",
        objective="Implement rate limiter",
        allowed_tools=["ast_guard", "pytest_runner"],
        inference_effort=InferenceEffort.DEEP,
        candidate_count=3,
    )
    assert req.task_id == "task_req_01"
    assert req.inference_effort == InferenceEffort.DEEP
    assert req.candidate_count == 3

    resp = ModelResponse(
        task_id="task_req_01",
        candidate_payload={"code": "class RateLimiter: pass"},
        model_identifier="test-model",
        provider="test-provider",
        inference_effort=InferenceEffort.DEEP,
    )
    assert resp.is_success is True
    assert resp.model_identifier == "test-model"


def test_mock_model_strong_profile():
    adapter = MockModelAdapter(profile=MockModelProfile.STRONG)
    req = ModelRequest(task_id="task_s", objective="Build arithmetic calculator")
    resp = adapter.execute(req)
    assert resp.is_success is True
    assert "strong_verified" in resp.candidate_payload.get("code", "")


def test_mock_model_weak_profile_naked_vs_compensated():
    adapter = MockModelAdapter(profile=MockModelProfile.WEAK)

    # 1. Naked Weak Model (fails, emits flawed code)
    req_naked = ModelRequest(task_id="task_w1", objective="Build arithmetic calculator")
    resp_naked = adapter.execute(req_naked)
    assert "flawed" in resp_naked.candidate_payload.get("code", "")

    # 2. Compensated Weak Model (receives compiled context/repair, succeeds)
    req_compensated = ModelRequest(
        task_id="task_w2",
        objective="Build arithmetic calculator",
        compiled_context={
            "AUTHORITATIVE": {"constraints": ["Must return sum"]},
            "PROCEDURE": {"name": "tdd_protocol"},
        },
    )
    resp_comp = adapter.execute(req_compensated)
    assert "repaired_weak" in resp_comp.candidate_payload.get("code", "")
    assert resp_comp.tokens_consumed > resp_naked.tokens_consumed


def test_mock_model_adversarial_profile():
    adapter = MockModelAdapter(profile=MockModelProfile.ADVERSARIAL)
    req = ModelRequest(task_id="task_adv", objective="Perform secure operation")
    resp = adapter.execute(req)
    assert "raise RuntimeError" in resp.candidate_payload.get("code", "")


def test_deficit_declaration_in_model_response():
    declaration = DeficitDeclaration(
        deficit_type=DeficitType.MISSING_KNOWLEDGE,
        description="Section 179D tax formula unknown.",
        required_provision="section_179d",
    )
    resp = ModelResponse(
        task_id="task_def",
        declared_deficits=[declaration],
        model_identifier="mock-weak",
        provider="mock",
    )
    assert len(resp.declared_deficits) == 1
    assert resp.declared_deficits[0].deficit_type == DeficitType.MISSING_KNOWLEDGE


def test_gemini_adapter_fails_closed_without_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    adapter = GeminiModelAdapter()
    req = ModelRequest(task_id="task_gem", objective="Generate code")
    resp = adapter.execute(req)
    assert resp.is_success is False
    assert "GEMINI_API_KEY not configured" in resp.error_message


def test_evidence_modality_separation():
    mock_adapter = MockModelAdapter()
    assert mock_adapter.evidence_modality == EvidenceModality.STRUCTURAL_MOCK

    gemini_adapter = GeminiModelAdapter(api_key="test-key")
    assert gemini_adapter.evidence_modality == EvidenceModality.EMPIRICAL_MODEL

