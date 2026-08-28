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
    ProviderExecutionReceipt,
    compute_provider_payload_digest,
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


def test_gemini_adapter_fails_closed_with_invalid_key_or_offline():
    adapter = GeminiModelAdapter(api_key="definitely-invalid-key-offline")
    req = ModelRequest(task_id="task_gem_invalid", objective="Generate code")
    resp = adapter.execute(req)
    # Must fail closed with error message and cannot return a fabricated success stub
    assert resp.is_success is False
    assert resp.provider_receipt is None
    assert "Gemini API execution failure" in (resp.error_message or "")


def test_provider_execution_receipt_verification():
    candidate_payload = {"code": "def solve(): return 42\n"}
    objective = "Solve the equation"
    req = ModelRequest(task_id="task_rcpt_1", objective=objective)

    payload_digest = compute_provider_payload_digest(
        candidate_payload=candidate_payload,
        raw_response={"status": "ok"},
        objective=objective,
    )
    receipt = ProviderExecutionReceipt(
        request_id="req_123",
        response_id="resp_456",
        provider_name="google",
        model_id="gemini-3.7-flash",
        latency_seconds=0.45,
        tokens_prompt=50,
        tokens_completion=20,
        tokens_total=70,
        payload_digest=payload_digest,
    )
    assert receipt.receipt_digest != ""
    assert len(receipt.receipt_digest) == 64

    resp = ModelResponse(
        task_id="task_rcpt_1",
        candidate_payload=candidate_payload,
        model_identifier="gemini-3.7-flash",
        provider="google",
        raw_response={"status": "ok"},
        provider_receipt=receipt,
    )
    assert receipt.is_valid_for_response(resp, req) is True

    # Tampering with payload breaks validation
    corrupted_resp = resp.model_copy(deep=True)
    corrupted_resp.candidate_payload = {"code": "def solve(): return 'hacked'\n"}
    assert receipt.is_valid_for_response(corrupted_resp, req) is False

    # Tampering with receipt digest breaks validation
    corrupted_receipt = receipt.model_copy(deep=True)
    corrupted_receipt.receipt_digest = "0" * 64
    assert corrupted_receipt.is_valid_for_response(resp, req) is False
