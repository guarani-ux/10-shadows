"""
tests/test_model_decoupling_benchmark.py
9-Dimension Benchmark & Model Elasticity Test Suite for 10 SHADOWS.
Includes rigorous physical verification acceptance tests (A through L) for model-decoupling.
"""

import pytest

from loop_engine.epistemic import EpistemicDisposition
from loop_engine.kernel_db import KernelDatabase
from loop_engine.model.benchmark import (
    BenchmarkDimension,
    BenchmarkResult,
    BenchmarkRunner,
    BenchmarkTask,
    EvidenceQualification,
    TaskRunRecord,
    create_canonical_benchmark_corpus,
    create_deterministic_knowledge_task,
)
from loop_engine.model.boundary import (
    DeficitDeclaration,
    DeficitType,
    EvidenceModality,
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


class KnowledgeModelTestAdapter(ModelAdapter):
    """
    Test model adapter for evaluating knowledge tasks in unit tests.
    Does not pollute production ModelAdapter with domain-specific logic.
    """
    def __init__(self, model_id: str = "test-knowledge-model", is_strong: bool = False, knows_naked: bool = False):
        self._model_id = model_id
        self.is_strong = is_strong
        self.knows_naked = knows_naked

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def provider_name(self) -> str:
        return "mock"

    def execute(self, req: ModelRequest) -> ModelResponse:
        domain_knowledge = (
            req.compiled_context.get("AUTHORITATIVE", {}).get("knowledge")
            or req.compiled_context.get("domain_knowledge")
            or {}
        )
        rules_dict = domain_knowledge.get("tariff_rules")
        if rules_dict or self.knows_naked:
            active_rules = rules_dict or {
                "TIER_ALPHA": {"base": 50.0, "rate": 1.5, "threshold": 200.0, "surcharge": 5.0},
                "TIER_BETA": {"base": 30.0, "rate": 2.0, "threshold": 100.0, "surcharge": 10.0},
            }
            code = (
                "def calculate_tariff(tier: str, amount: float) -> float:\n"
                f"    rules = {repr(active_rules)}\n"
                "    if tier not in rules:\n"
                "        return 0.0\n"
                "    r = rules[tier]\n"
                "    base = r['base']\n"
                "    rate = r['rate']\n"
                "    thresh = r['threshold']\n"
                "    surcharge = r['surcharge']\n"
                "    if amount > thresh:\n"
                "        val = base + (amount - thresh) * rate + surcharge\n"
                "    else:\n"
                "        val = base + amount * (rate * 0.5)\n"
                "    return round(val, 4)\n"
            )
            return ModelResponse(
                task_id=req.task_id,
                candidate_payload={"status": "SUCCESS", "code": code},
                model_identifier=self.model_id,
                provider=self.provider_name,
                tokens_consumed=300 if self.is_strong else 600,
            )
        else:
            if self.is_strong:
                return ModelResponse(
                    task_id=req.task_id,
                    declared_deficits=[
                        DeficitDeclaration(
                            deficit_type=DeficitType.MISSING_KNOWLEDGE,
                            description="Specialized tariff rules not present in context.",
                            required_provision="tariff_rules",
                        )
                    ],
                    model_identifier=self.model_id,
                    provider=self.provider_name,
                    tokens_consumed=150,
                )
            else:
                return ModelResponse(
                    task_id=req.task_id,
                    candidate_payload={
                        "status": "PARTIAL",
                        "code": "def calculate_tariff(tier: str, amount: float) -> float:\n    return round(amount * 0.1, 4)\n",
                    },
                    explicit_uncertainties=["Unsure about specialized tariff rates."],
                    model_identifier=self.model_id,
                    provider=self.provider_name,
                    tokens_consumed=150,
                )


def test_acceptance_a_false_success_adapter_across_corpus_yields_zero_qualified_successes():
    """
    Acceptance Test A: FalseSuccessAdapter across the complete corpus.
    Adapter emits fake status tokens and invalid code across all 9 benchmark dimensions.
    Expected: zero qualified successes across both Naked and Ten Shadows modes.
    """
    corpus = create_canonical_benchmark_corpus(seed=42)
    runner = BenchmarkRunner()
    adapter = FalseSuccessAdapter()

    for task in corpus:
        rec_naked = runner.run_task_naked(adapter, task)
        assert rec_naked.is_qualified_success is False
        assert rec_naked.score == 0.0

        rec_ts = runner.run_task_ten_shadows(adapter, task)
        assert rec_ts.is_qualified_success is False
        assert rec_ts.score == 0.0


def test_acceptance_b_semantically_wrong_executable_candidates_yield_zero_qualified_successes():
    """
    Acceptance Test B: Semantically wrong executable candidates.
    Candidate produces syntactically valid Python code that is semantically wrong.
    Expected: zero qualified successes across all tasks.
    """
    corpus = create_canonical_benchmark_corpus(seed=42)
    runner = BenchmarkRunner()
    corrupt_adapter = CorruptedCandidateAdapter()

    for task in corpus:
        rec_naked = runner.run_task_naked(corrupt_adapter, task)
        assert rec_naked.is_qualified_success is False
        assert rec_naked.score == 0.0

        rec_ts = runner.run_task_ten_shadows(corrupt_adapter, task)
        assert rec_ts.is_qualified_success is False
        assert rec_ts.score == 0.0


def test_acceptance_c_only_qualified_task_ids_enter_elasticity_calculations():
    """
    Acceptance Test C: Evidence Qualification Isolation.
    Only tasks with independent task-specific behavioral verifiers enter elasticity calculations.
    Tasks without verifiers are marked UNQUALIFIED and excluded from elasticity numerator and denominator.
    """
    corpus = create_canonical_benchmark_corpus(seed=42)
    runner = BenchmarkRunner()

    strong_model = KnowledgeModelTestAdapter(model_id="strong-v1", is_strong=True)
    weak_model = KnowledgeModelTestAdapter(model_id="weak-v1", is_strong=False)

    result = runner.run_comparative_benchmark(strong_model, weak_model, corpus=corpus)

    # 1. Qualified vs Unqualified partitioning
    assert len(result.qualified_task_ids) == 1
    assert "BM_KNOWLEDGE_01" in result.qualified_task_ids
    assert len(result.unqualified_task_ids) == 8
    for unq_id in [
        "BM_PROCEDURAL_01",
        "BM_DECOMPOSITION_01",
        "BM_IMPLEMENTATION_01",
        "BM_SEMANTIC_01",
        "BM_MEMORY_01",
        "BM_SEARCH_01",
        "BM_AUTHORITY_01",
        "BM_UNKNOWN_DOMAIN_01",
    ]:
        assert unq_id in result.unqualified_task_ids

    # 2. Scores are computed exclusively over qualified tasks
    assert result.ten_shadows_score_a == 1.0
    assert result.ten_shadows_score_b == 1.0


def test_acceptance_d_zero_denominator_returns_not_computable():
    """
    Acceptance Test D: Zero Denominator Returns NOT_COMPUTABLE.
    When no qualified tasks exist or when naked_delta is zero, elasticity returns 'NOT_COMPUTABLE'.
    """
    runner = BenchmarkRunner()

    # Case 1: Corpus with ONLY unqualified tasks
    unqualified_corpus = [
        BenchmarkTask(
            task_id="BM_UNQ_01",
            dimension=BenchmarkDimension.PROCEDURAL,
            objective="Unverified procedural task",
            evaluator=None,
            qualification=EvidenceQualification.UNQUALIFIED,
        ),
        BenchmarkTask(
            task_id="BM_UNQ_02",
            dimension=BenchmarkDimension.DECOMPOSITION,
            objective="Unverified decomposition task",
            evaluator=None,
            qualification=EvidenceQualification.UNQUALIFIED,
        ),
    ]
    model_a = KnowledgeModelTestAdapter(model_id="model-a")
    model_b = KnowledgeModelTestAdapter(model_id="model-b")

    res_zero_qualified = runner.run_comparative_benchmark(model_a, model_b, corpus=unqualified_corpus)
    assert res_zero_qualified.model_elasticity == "NOT_COMPUTABLE"
    assert res_zero_qualified.attempt_elasticity == "NOT_COMPUTABLE"
    assert res_zero_qualified.latency_elasticity == "NOT_COMPUTABLE"
    assert len(res_zero_qualified.qualified_task_ids) == 0

    # Case 2: Qualified task where naked_delta is zero (both models score 0.0 naked)
    qualified_task = create_deterministic_knowledge_task(seed=42)
    model_weak_1 = KnowledgeModelTestAdapter(model_id="weak-1", is_strong=False)
    model_weak_2 = KnowledgeModelTestAdapter(model_id="weak-2", is_strong=False)

    res_zero_delta = runner.run_comparative_benchmark(model_weak_1, model_weak_2, corpus=[qualified_task])
    assert res_zero_delta.naked_score_a == 0.0
    assert res_zero_delta.naked_score_b == 0.0
    assert res_zero_delta.model_elasticity == "NOT_COMPUTABLE"


def test_acceptance_e_mock_runs_cannot_be_labeled_empirical():
    """
    Acceptance Test E: Separation of Mock Evidence from Empirical Model Evidence.
    Mock runs cannot be labeled empirical; any attempt to do so raises ValueError.
    """
    runner = BenchmarkRunner()
    task = create_deterministic_knowledge_task(seed=42)
    mock_adapter = MockModelAdapter(profile=MockModelProfile.STRONG)

    # 1. Attempting to run task naked with EMPIRICAL_MODEL modality on a mock adapter must fail
    with pytest.raises(ValueError, match="Mock runs cannot be labeled empirical"):
        runner.run_task_naked(mock_adapter, task, evidence_modality=EvidenceModality.EMPIRICAL_MODEL)

    # 2. Attempting to run task Ten Shadows with EMPIRICAL_MODEL modality on a mock adapter must fail
    with pytest.raises(ValueError, match="Mock runs cannot be labeled empirical"):
        runner.run_task_ten_shadows(mock_adapter, task, evidence_modality=EvidenceModality.EMPIRICAL_MODEL)

    # 3. Attempting to run comparative benchmark with EMPIRICAL_MODEL on mock models must fail
    with pytest.raises(ValueError, match="Mock runs cannot be labeled empirical"):
        runner.run_comparative_benchmark(mock_adapter, mock_adapter, corpus=[task], evidence_modality=EvidenceModality.EMPIRICAL_MODEL)

    # 4. Constructing TaskRunRecord directly with mock provider and empirical modality must fail
    with pytest.raises(ValueError, match="Mock runs cannot be labeled empirical"):
        TaskRunRecord(
            task_id="BM_MOCK_TEST",
            dimension=BenchmarkDimension.KNOWLEDGE,
            model_id="mock-strong",
            provider="mock",
            execution_mode="NAKED",
            is_success=True,
            score=1.0,
            evidence_modality=EvidenceModality.EMPIRICAL_MODEL,
            attempts=1,
            total_model_calls=1,
            latency_seconds=0.1,
            tokens_consumed=100,
        )

    # 5. Constructing BenchmarkResult with mock models and empirical modality must fail
    with pytest.raises(ValueError, match="Mock runs cannot be labeled empirical"):
        BenchmarkResult(
            model_a_id="mock-model-a",
            model_b_id="mock-model-b",
            naked_score_a=1.0,
            naked_score_b=0.0,
            ten_shadows_score_a=1.0,
            ten_shadows_score_b=1.0,
            model_elasticity=0.0,
            attempt_elasticity=1.0,
            latency_elasticity=1.0,
            evidence_modality=EvidenceModality.EMPIRICAL_MODEL,
        )


def test_acceptance_f_valid_physical_candidate_scores_one_and_is_qualified():
    """
    Acceptance Test F: Valid physical candidate scores 1.0 against held-out verifier and is QUALIFIED.
    """
    task = create_deterministic_knowledge_task(seed=42)
    runner = BenchmarkRunner()
    weak_model = KnowledgeModelTestAdapter(model_id="weak-knowledge", is_strong=False)

    # When Ten Shadows provisions the domain knowledge, model synthesizes valid candidate
    rec = runner.run_task_ten_shadows(weak_model, task)
    assert rec.is_success is True
    assert rec.score == 1.0
    assert rec.qualification == EvidenceQualification.QUALIFIED
    assert rec.is_qualified_success is True
    assert rec.observed_outputs is not None
    assert len(rec.observed_outputs) > 0


def test_acceptance_g_missing_verifier_marked_unqualified_fails_closed():
    """
    Acceptance Test G: Missing Verifier is marked UNQUALIFIED and fails closed.
    """
    missing_task = BenchmarkTask(
        task_id="BM_MISSING_EVALUATOR",
        dimension=BenchmarkDimension.KNOWLEDGE,
        objective="Calculate tariff without verifier",
        evaluator=None,
    )
    assert missing_task.qualification == EvidenceQualification.UNQUALIFIED
    assert missing_task.is_qualified is False

    runner = BenchmarkRunner()
    weak_model = KnowledgeModelTestAdapter(model_id="weak-model", is_strong=False)

    rec_naked = runner.run_task_naked(weak_model, missing_task)
    assert rec_naked.is_success is False
    assert rec_naked.score == 0.0
    assert rec_naked.qualification == EvidenceQualification.UNQUALIFIED
    assert rec_naked.is_qualified_success is False

    rec_ts = runner.run_task_ten_shadows(weak_model, missing_task)
    assert rec_ts.is_success is False
    assert rec_ts.score == 0.0
    assert rec_ts.qualification == EvidenceQualification.UNQUALIFIED
    assert rec_ts.is_qualified_success is False


def test_acceptance_h_naked_condition_fails_held_out_physical_verifier():
    """
    Acceptance Test H: Naked Condition fails held-out physical verifier.
    """
    task = create_deterministic_knowledge_task(seed=42)
    runner = BenchmarkRunner()
    weak_model = KnowledgeModelTestAdapter(model_id="weak-model", is_strong=False)

    rec_naked = runner.run_task_naked(weak_model, task)
    assert rec_naked.is_success is False
    assert rec_naked.score == 0.0
    assert rec_naked.is_qualified_success is False


def test_acceptance_i_single_variable_ablation_removes_physical_success():
    """
    Acceptance Test I: Single-Variable Ablation.
    Removing ONLY supplied competence eliminates physical success on qualified task.
    """
    task = create_deterministic_knowledge_task(seed=42)
    runner = BenchmarkRunner()
    weak_model = KnowledgeModelTestAdapter(model_id="weak-model", is_strong=False)

    rec_ablated = runner.run_task_ten_shadows(
        weak_model,
        task,
        enable_context_compiler=False,
        enable_deficit_protocol=False,
    )
    assert rec_ablated.is_success is False
    assert rec_ablated.score == 0.0
    assert rec_ablated.is_qualified_success is False


def test_acceptance_j_verification_seam_disablement_blocks_state_minting():
    """
    Acceptance Test J: Verification-Seam Disablement.
    When routed through the production verification seam, disabling the seam blocks state minting.
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
    weak_model = KnowledgeModelTestAdapter(model_id="weak-model", is_strong=False)

    rec = runner.run_task_ten_shadows(weak_model, disabled_task)
    assert rec.is_success is False
    assert rec.score == 0.0
    assert "SIG_SEAM_TRANSITION_REJECTED" in rec.failure_signatures_recorded

    assert kdb.get_proposal_state(disabled_task.task_id) != State.VERIFIED


def test_acceptance_k_canonical_benchmark_corpus_covers_all_9_dimensions():
    """
    Acceptance Test K: Canonical Corpus Covers All 9 Dimensions.
    Exactly 1 task is QUALIFIED with a task-specific verifier; 8 tasks are UNQUALIFIED.
    """
    corpus = create_canonical_benchmark_corpus()
    assert len(corpus) == 9
    dims = {t.dimension for t in corpus}
    assert len(dims) == 9

    qualified = [t for t in corpus if t.is_qualified]
    unqualified = [t for t in corpus if not t.is_qualified]

    assert len(qualified) == 1
    assert qualified[0].task_id == "BM_KNOWLEDGE_01"
    assert len(unqualified) == 8


def test_acceptance_l_comparative_benchmark_demonstrates_low_model_elasticity():
    """
    Acceptance Test L: Model-Decoupling Invariant.
    Under Naked execution: Strong model outperforms Weak model.
    Under Ten Shadows: Weak model recovers to match Strong model (Elasticity = 0.0).
    """
    task = create_deterministic_knowledge_task(seed=42)
    rules = task.required_knowledge["tariff_rules"]

    class PreTrainedStrongModel(ModelAdapter):
        @property
        def model_id(self) -> str:
            return "strong-v1"

        @property
        def provider_name(self) -> str:
            return "mock"

        def execute(self, req: ModelRequest) -> ModelResponse:
            code = (
                "def calculate_tariff(tier: str, amount: float) -> float:\n"
                f"    rules = {repr(rules)}\n"
                "    if tier not in rules:\n"
                "        return 0.0\n"
                "    r = rules[tier]\n"
                "    base = r['base']\n"
                "    rate = r['rate']\n"
                "    thresh = r['threshold']\n"
                "    surcharge = r['surcharge']\n"
                "    if amount > thresh:\n"
                "        val = base + (amount - thresh) * rate + surcharge\n"
                "    else:\n"
                "        val = base + amount * (rate * 0.5)\n"
                "    return round(val, 4)\n"
            )
            return ModelResponse(
                task_id=req.task_id,
                candidate_payload={"status": "SUCCESS", "code": code},
                model_identifier=self.model_id,
                provider=self.provider_name,
                tokens_consumed=300,
            )

    strong_model = PreTrainedStrongModel()
    weak_model = KnowledgeModelTestAdapter(model_id="weak-v1", is_strong=False)

    runner = BenchmarkRunner()
    result = runner.run_comparative_benchmark(strong_model, weak_model, corpus=create_canonical_benchmark_corpus(seed=42))

    # 1. Verify Naked Performance Gap exists on qualified tasks
    assert result.naked_score_a == 1.0
    assert result.naked_score_b == 0.0

    # 2. Verify Ten Shadows absorbs model variance (Both reach 100% verified success)
    assert result.ten_shadows_score_a == 1.0
    assert result.ten_shadows_score_b == 1.0

    # 3. Model Elasticity must be 0.0
    assert result.model_elasticity == 0.0

    # 4. Attempt Elasticity >= 1.0
    assert result.attempt_elasticity >= 1.0
    assert result.latency_elasticity > 0.0

    # 5. Verify receipt integrity
    for rec in result.records:
        assert rec.receipt_digest != ""
        assert len(rec.receipt_digest) == 64

