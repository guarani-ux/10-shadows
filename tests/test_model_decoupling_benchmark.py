"""
tests/test_model_decoupling_benchmark.py
9-Dimension Benchmark & Model Elasticity Test Suite for 10 SHADOWS.
Includes rigorous physical verification acceptance tests (A through H) for model-decoupling.
"""

import pytest

from loop_engine.epistemic import EpistemicDisposition
from loop_engine.kernel_db import KernelDatabase
from loop_engine.model.benchmark import (
    BenchmarkDimension,
    BenchmarkRunner,
    BenchmarkTask,
    create_canonical_benchmark_corpus,
    create_deterministic_knowledge_task,
)
from loop_engine.model.boundary import (
    MockModelAdapter,
    MockModelProfile,
    ModelAdapter,
    ModelRequest,
    ModelResponse,
)
from loop_engine.schema import State
from loop_engine.transition import PrivilegedTransitionEngine, TransitionRejection


class FalseSuccessAdapter(ModelAdapter):
    """Adapter that emits fake status tokens and invalid code."""
    @property
    def model_id(self) -> str:
        return "false-success-mock"

    @property
    def provider_name(self) -> str:
        return "mock"

    def execute(self, req: ModelRequest) -> ModelResponse:
        return ModelResponse(
            task_id=req.task_id,
            candidate_payload={
                "status": "SUCCESS",
                "code": "def run(): return 'wrong'\n",
            },
        )


class CorruptedCandidateAdapter(ModelAdapter):
    """Adapter that emits structurally altered code while claiming SUCCESS."""
    @property
    def model_id(self) -> str:
        return "corrupted-candidate-mock"

    @property
    def provider_name(self) -> str:
        return "mock"

    def execute(self, req: ModelRequest) -> ModelResponse:
        return ModelResponse(
            task_id=req.task_id,
            candidate_payload={
                "status": "SUCCESS",
                "code": "def calculate_tariff(tier: str, amount: float) -> float:\n    return 999999.99\n",
            },
        )


def test_acceptance_a_false_success_adapter_scores_zero():
    """
    Acceptance Test A: False Success Adapter.
    Adapter always returns status="SUCCESS" with wrong code.
    Expected: benchmark score = 0 on both Naked and Ten Shadows modes.
    """
    task = create_deterministic_knowledge_task(seed=42)
    runner = BenchmarkRunner()
    adapter = FalseSuccessAdapter()

    rec_naked = runner.run_task_naked(adapter, task)
    assert rec_naked.is_success is False
    assert rec_naked.score == 0.0

    rec_ts = runner.run_task_ten_shadows(adapter, task)
    assert rec_ts.is_success is False
    assert rec_ts.score == 0.0


def test_acceptance_b_valid_physical_candidate_scores_one():
    """
    Acceptance Test B: Valid Physical Candidate.
    Candidate computes the correct externally defined behavior against held-out cases.
    Expected: benchmark score = 1.0.
    """
    task = create_deterministic_knowledge_task(seed=42)
    runner = BenchmarkRunner()
    weak_model = MockModelAdapter(profile=MockModelProfile.WEAK)

    # When Ten Shadows provisions the domain knowledge, model synthesizes valid candidate
    rec = runner.run_task_ten_shadows(weak_model, task)
    assert rec.is_success is True
    assert rec.score == 1.0
    assert rec.observed_outputs is not None
    assert len(rec.observed_outputs) > 0


def test_acceptance_c_corrupted_candidate_scores_zero():
    """
    Acceptance Test C: Corrupted Candidate.
    Change candidate implementation while leaving status metadata intact.
    Expected: benchmark score = 0.0.
    """
    task = create_deterministic_knowledge_task(seed=42)
    runner = BenchmarkRunner()
    corrupt_adapter = CorruptedCandidateAdapter()

    rec = runner.run_task_ten_shadows(corrupt_adapter, task)
    assert rec.is_success is False
    assert rec.score == 0.0


def test_acceptance_d_missing_verifier_fails_closed():
    """
    Acceptance Test D: Missing Verifier.
    Remove or omit task-specific evaluator.
    Expected: benchmark fails closed with score = 0.0.
    """
    missing_task = BenchmarkTask(
        task_id="BM_MISSING_EVALUATOR",
        dimension=BenchmarkDimension.KNOWLEDGE,
        objective="Calculate tariff without verifier",
        evaluator=None,
    )
    runner = BenchmarkRunner()
    weak_model = MockModelAdapter(profile=MockModelProfile.WEAK)

    rec_naked = runner.run_task_naked(weak_model, missing_task)
    assert rec_naked.is_success is False
    assert rec_naked.score == 0.0

    rec_ts = runner.run_task_ten_shadows(weak_model, missing_task)
    assert rec_ts.is_success is False
    assert rec_ts.score == 0.0


def test_acceptance_e_naked_condition_fails_held_out_physical_verifier():
    """
    Acceptance Test E: Naked Condition.
    The limited/weaker processor does not receive the hidden rule.
    Expected: cannot satisfy held-out physical verifier (score = 0.0).
    """
    task = create_deterministic_knowledge_task(seed=42)
    runner = BenchmarkRunner()
    weak_model = MockModelAdapter(profile=MockModelProfile.WEAK)

    rec_naked = runner.run_task_naked(weak_model, task)
    assert rec_naked.is_success is False
    assert rec_naked.score == 0.0


def test_acceptance_f_ten_shadows_condition_satisfies_held_out_verifier():
    """
    Acceptance Test F: Ten Shadows Condition.
    Same processor, same task, same verifier, same execution substrate.
    Ten Shadows provisions the missing rule through the competence substrate.
    Expected: candidate satisfies held-out physical verifier (score = 1.0).
    """
    task = create_deterministic_knowledge_task(seed=42)
    runner = BenchmarkRunner()
    weak_model = MockModelAdapter(profile=MockModelProfile.WEAK)

    rec_ts = runner.run_task_ten_shadows(weak_model, task)
    assert rec_ts.is_success is True
    assert rec_ts.score == 1.0


def test_acceptance_g_single_variable_ablation_removes_physical_success():
    """
    Acceptance Test G: Single-Variable Ablation.
    Run the assisted condition again while removing ONLY the supplied competence.
    Everything else remains identical.
    Expected: physical success disappears (score = 0.0).
    """
    task = create_deterministic_knowledge_task(seed=42)
    runner = BenchmarkRunner()
    weak_model = MockModelAdapter(profile=MockModelProfile.WEAK)

    # Ablate ONLY context compilation of domain knowledge
    rec_ablated = runner.run_task_ten_shadows(
        weak_model,
        task,
        enable_context_compiler=False,
        enable_deficit_protocol=False,
    )
    assert rec_ablated.is_success is False
    assert rec_ablated.score == 0.0


def test_acceptance_h_verification_seam_disablement_blocks_state_minting():
    """
    Acceptance Test H: Verification-Seam Disablement.
    When routed through the production verification seam:
    If the seam is disabled/rejects, verified completion becomes impossible and state cannot be minted.
    """
    kdb = KernelDatabase()

    class DisabledTransitionEngine(PrivilegedTransitionEngine):
        def execute_transition(self, req):
            return TransitionRejection(
                rejection_id="rej_disabled",
                task_id=req.task_id,
                from_state=req.from_state,
                requested_state=req.to_state,
                reason="Verification seam administratively disabled.",
                disposition=EpistemicDisposition.INSUFFICIENT_EVIDENCE,
            )

    disabled_engine = DisabledTransitionEngine(kernel_db=kdb)
    disabled_task = create_deterministic_knowledge_task(seed=42, transition_engine=disabled_engine)

    runner = BenchmarkRunner()
    weak_model = MockModelAdapter(profile=MockModelProfile.WEAK)

    rec = runner.run_task_ten_shadows(weak_model, disabled_task)
    assert rec.is_success is False
    assert rec.score == 0.0
    assert "SIG_SEAM_TRANSITION_REJECTED" in rec.failure_signatures_recorded

    # Verify that privileged state was never minted in database
    assert kdb.get_proposal_state(disabled_task.task_id) != State.VERIFIED


def test_canonical_benchmark_corpus_covers_all_9_dimensions():
    corpus = create_canonical_benchmark_corpus()
    assert len(corpus) == 9
    dims = {t.dimension for t in corpus}
    assert len(dims) == 9
    assert BenchmarkDimension.KNOWLEDGE in dims
    assert BenchmarkDimension.PROCEDURAL in dims
    assert BenchmarkDimension.DECOMPOSITION in dims
    assert BenchmarkDimension.IMPLEMENTATION in dims
    assert BenchmarkDimension.SEMANTIC in dims
    assert BenchmarkDimension.MEMORY in dims
    assert BenchmarkDimension.SEARCH in dims
    assert BenchmarkDimension.AUTHORITY in dims
    assert BenchmarkDimension.UNKNOWN_DOMAIN in dims


def test_comparative_benchmark_demonstrates_low_model_elasticity():
    """
    Core Model-Decoupling Invariant:
    Under Naked execution: Strong model outperforms Weak model (high gap).
    Under Ten Shadows execution: Weak model recovers to match Strong model (gap -> 0, Elasticity -> 0).
    """
    strong_model = MockModelAdapter(profile=MockModelProfile.STRONG, model_id="strong-v1")
    weak_model = MockModelAdapter(profile=MockModelProfile.WEAK, model_id="weak-v1")

    runner = BenchmarkRunner()
    result = runner.run_comparative_benchmark(strong_model, weak_model)

    # 1. Verify Naked Performance Gap exists
    assert result.naked_score_a > result.naked_score_b
    assert result.naked_score_a > 0.5
    assert result.naked_score_b == 0.0

    # 2. Verify Ten Shadows absorbs model variance (Both reach 100% verified success)
    assert result.ten_shadows_score_a == 1.0
    assert result.ten_shadows_score_b == 1.0

    # 3. Model Elasticity must be 0.0
    assert result.model_elasticity == 0.0

    # 4. Attempt Elasticity >= 1.0 (Weak model took more attempts/work to converge)
    assert result.attempt_elasticity >= 1.0
    assert result.latency_elasticity > 0.0

    # 5. Verify receipt integrity
    for rec in result.records:
        assert rec.receipt_digest != ""
        assert len(rec.receipt_digest) == 64
