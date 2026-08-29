"""
tests/test_candidate_search.py
Tests for Adaptive Candidate Search & Structured Failure Feedback (10 SHADOWS).
"""

from loop_engine.model.boundary import (
    InferenceEffort,
    MockModelAdapter,
    MockModelProfile,
    ModelRequest,
    ModelResponse,
)
from loop_engine.model.candidate_search import (
    CandidateEvaluation,
    SearchEngine,
    SearchPolicy,
    TaskDifficulty,
)
from loop_engine.model.context_compiler import ContextCompiler


def test_search_policy_determination():
    compiler = ContextCompiler()
    engine = SearchEngine(context_compiler=compiler)

    assert engine.determine_search_policy(TaskDifficulty.LOW, has_prior_failures=False) == SearchPolicy.SINGLE
    assert (
        engine.determine_search_policy(TaskDifficulty.MEDIUM, has_prior_failures=False) == SearchPolicy.CRITIQUE_REPAIR
    )
    assert engine.determine_search_policy(TaskDifficulty.HIGH, has_prior_failures=False) == SearchPolicy.MULTI_CANDIDATE
    assert engine.determine_search_policy(TaskDifficulty.LOW, has_prior_failures=True) == SearchPolicy.MULTI_CANDIDATE


def test_adaptive_search_weak_model_recovers_via_failure_feedback():
    compiler = ContextCompiler()
    engine = SearchEngine(context_compiler=compiler)
    weak_adapter = MockModelAdapter(profile=MockModelProfile.WEAK)

    base_req = ModelRequest(task_id="task_srch_01", objective="Build calculator module")

    winning_eval, all_evals, total_calls = engine.execute_search(
        adapter=weak_adapter,
        base_request=base_req,
        objective="Build calculator module",
        difficulty=TaskDifficulty.MEDIUM,
        max_repair_attempts=3,
        initial_context_kwargs={"constraints": ["Must return valid result"]},
    )

    # First attempt produced flawed code; second attempt received failure feedback and succeeded!
    assert winning_eval.is_valid is True
    assert len(all_evals) == 2
    assert total_calls == 2
    assert "repaired_weak" in winning_eval.payload.get("code", "")


def test_adversarial_model_falsified_and_rejected():
    compiler = ContextCompiler()
    engine = SearchEngine(context_compiler=compiler)
    adv_adapter = MockModelAdapter(profile=MockModelProfile.ADVERSARIAL)

    base_req = ModelRequest(task_id="task_adv_01", objective="Secure kernel operation")

    winning_eval, all_evals, total_calls = engine.execute_search(
        adapter=adv_adapter,
        base_request=base_req,
        objective="Secure kernel operation",
        difficulty=TaskDifficulty.LOW,
        max_repair_attempts=2,
    )

    # Adversarial code raises RuntimeError and is rejected by physical evaluation
    assert winning_eval.is_valid is False
    assert winning_eval.failure_signature == "SIG_RUNTIME_EXCEPTION"
