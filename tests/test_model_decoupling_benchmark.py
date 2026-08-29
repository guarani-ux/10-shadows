"""
tests/test_model_decoupling_benchmark.py
9-Dimension Benchmark & Model Elasticity Test Suite for 10 SHADOWS.
Includes rigorous physical verification acceptance tests (A through P) for model-decoupling.
"""

from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

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
    GeminiModelAdapter,
    MockModelAdapter,
    MockModelProfile,
    ModelAdapter,
    ModelRequest,
    ModelResponse,
    ProviderExecutionReceipt,
    compute_provider_payload_digest,
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

    def __init__(
        self,
        model_id: str = "test-knowledge-model",
        is_strong: bool = False,
        known_rules: Optional[Dict[str, Any]] = None,
    ):
        self._model_id = model_id
        self.is_strong = is_strong
        self.known_rules = known_rules

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
        rules_dict = domain_knowledge.get("tariff_rules") or self.known_rules
        if rules_dict:
            code = (
                "def calculate_tariff(tier: str, amount: float) -> float:\n"
                f"    rules = {repr(rules_dict)}\n"
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
    Unqualified tasks are recorded physically but excluded from elasticity numerator and denominator.
    """
    corpus = create_canonical_benchmark_corpus(seed=42)
    runner = BenchmarkRunner()
    tariff_rules = corpus[0].required_knowledge["tariff_rules"]

    strong_model = KnowledgeModelTestAdapter(model_id="strong-k", is_strong=True, known_rules=tariff_rules)
    weak_model = KnowledgeModelTestAdapter(model_id="weak-k", is_strong=False, known_rules=None)

    result = runner.run_comparative_benchmark(strong_model, weak_model, corpus=corpus)

    # Exactly 1 qualified task out of 9
    assert len(result.qualified_task_ids) == 1
    assert result.qualified_task_ids == ["BM_KNOWLEDGE_01"]
    assert len(result.unqualified_task_ids) == 8

    # All 9 tasks must be physically recorded across 4 execution combinations (9 * 4 = 36 records)
    assert len(result.records) == 36

    # Verify qualified task scored 1.0 on strong naked and 0.0 on weak naked
    assert result.naked_score_a == 1.0
    assert result.naked_score_b == 0.0

    # Under Ten Shadows, both achieve 1.0 on qualified tasks
    assert result.ten_shadows_score_a == 1.0
    assert result.ten_shadows_score_b == 1.0
    assert result.model_elasticity == 0.0


def test_acceptance_d_zero_qualified_tasks_returns_not_computable():
    """
    Acceptance Test D: Fail-Closed Metric Boundary.
    If zero qualified tasks exist or delta is zero, elasticity returns NOT_COMPUTABLE.
    """
    unqualified_corpus = [
        BenchmarkTask(
            task_id="BM_UNQ_01",
            dimension=BenchmarkDimension.PROCEDURAL,
            objective="Dummy task without verifier",
            evaluator=None,
        ),
        BenchmarkTask(
            task_id="BM_UNQ_02",
            dimension=BenchmarkDimension.DECOMPOSITION,
            objective="Second dummy task without verifier",
            evaluator=None,
        ),
    ]
    runner = BenchmarkRunner()
    strong_model = KnowledgeModelTestAdapter(model_id="strong-k", is_strong=True)
    weak_model = KnowledgeModelTestAdapter(model_id="weak-k", is_strong=False)

    result = runner.run_comparative_benchmark(strong_model, weak_model, corpus=unqualified_corpus)

    assert result.model_elasticity == "NOT_COMPUTABLE"
    assert result.attempt_elasticity == "NOT_COMPUTABLE"
    assert result.latency_elasticity == "NOT_COMPUTABLE"
    assert len(result.qualified_task_ids) == 0
    assert len(result.unqualified_task_ids) == 2

    # If naked_delta == 0 on a qualified corpus, model_elasticity is also NOT_COMPUTABLE
    qualified_task = create_deterministic_knowledge_task(seed=42)
    model_weak_1 = KnowledgeModelTestAdapter(model_id="w1", is_strong=False, known_rules=None)
    model_weak_2 = KnowledgeModelTestAdapter(model_id="w2", is_strong=False, known_rules=None)

    res_zero_delta = runner.run_comparative_benchmark(model_weak_1, model_weak_2, corpus=[qualified_task])
    assert res_zero_delta.naked_score_a == 0.0
    assert res_zero_delta.naked_score_b == 0.0
    assert res_zero_delta.model_elasticity == "NOT_COMPUTABLE"


def test_acceptance_e_mock_runs_cannot_be_labeled_empirical():
    """
    Acceptance Test E: Separation of Mock Evidence from Empirical Model Evidence.
    Mock runs through benchmark runner strictly produce STRUCTURAL_MOCK modality.
    Directly constructing empirical records with mock providers or missing receipts raises ValueError.
    """
    runner = BenchmarkRunner()
    task = create_deterministic_knowledge_task(seed=42)
    mock_adapter = MockModelAdapter(profile=MockModelProfile.STRONG)

    # 1. Running mock adapter produces STRUCTURAL_MOCK modality
    rec_naked = runner.run_task_naked(mock_adapter, task)
    assert rec_naked.evidence_modality == EvidenceModality.STRUCTURAL_MOCK

    # 2. Running mock adapter in Ten Shadows produces STRUCTURAL_MOCK modality
    rec_ts = runner.run_task_ten_shadows(mock_adapter, task)
    assert rec_ts.evidence_modality == EvidenceModality.STRUCTURAL_MOCK

    # 3. Running comparative benchmark on mock models produces STRUCTURAL_MOCK modality
    res = runner.run_comparative_benchmark(mock_adapter, mock_adapter, corpus=[task])
    assert res.evidence_modality == EvidenceModality.STRUCTURAL_MOCK

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


def test_acceptance_h_naked_weak_model_fails_qualified_task():
    """
    Acceptance Test H: Naked Weak Model Fails.
    Without compiled context or deficit loop, naked weak model scores 0.0 on qualified task.
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
    result = runner.run_comparative_benchmark(
        strong_model, weak_model, corpus=create_canonical_benchmark_corpus(seed=42)
    )

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


def test_acceptance_m_fake_gemini_key_without_provider_access_fails_closed_and_cannot_produce_empirical_record():
    """
    Acceptance Test 1 (from repair contract):
    At exact repaired HEAD: a fake Gemini key with provider access absent must return
    is_success=false and cannot produce any EMPIRICAL_MODEL record.
    """
    task = create_deterministic_knowledge_task(seed=42)
    runner = BenchmarkRunner()
    fake_gemini_adapter = GeminiModelAdapter(api_key="definitely-invalid-key-offline")

    req = ModelRequest(task_id=task.task_id, objective=task.objective)
    resp = fake_gemini_adapter.execute(req)
    assert resp.is_success is False
    assert resp.provider_receipt is None

    # Running through runner in naked mode
    rec_naked = runner.run_task_naked(fake_gemini_adapter, task)
    assert rec_naked.is_success is False
    assert rec_naked.score == 0.0
    assert rec_naked.is_qualified_success is False
    assert rec_naked.evidence_modality != EvidenceModality.EMPIRICAL_MODEL
    assert rec_naked.evidence_modality == EvidenceModality.STRUCTURAL_MOCK
    assert rec_naked.provider_receipt is None

    # Running through runner in Ten Shadows mode
    rec_ts = runner.run_task_ten_shadows(fake_gemini_adapter, task)
    assert rec_ts.is_success is False
    assert rec_ts.score == 0.0
    assert rec_ts.is_qualified_success is False
    assert rec_ts.evidence_modality != EvidenceModality.EMPIRICAL_MODEL
    assert rec_ts.evidence_modality == EvidenceModality.STRUCTURAL_MOCK


def test_acceptance_n_custom_adapter_claiming_provider_without_valid_receipt_recorded_as_non_empirical():
    """
    Acceptance Test 2 (from repair contract):
    A custom adapter declaring provider_name="google" but returning a local deterministic candidate
    must be rejected or recorded non-empirical even when the candidate passes its physical evaluator.
    """
    task = create_deterministic_knowledge_task(seed=42)
    rules = task.required_knowledge["tariff_rules"]

    class PretendGoogleAdapter(ModelAdapter):
        @property
        def model_id(self) -> str:
            return "pretend-gemini-3.7-flash"

        @property
        def provider_name(self) -> str:
            return "google"

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
                provider_receipt=None,  # No validated provider receipt
            )

    pretend_adapter = PretendGoogleAdapter()
    runner = BenchmarkRunner()

    rec_naked = runner.run_task_naked(pretend_adapter, task)
    # The candidate passes physical evaluation, but modality MUST fail closed to STRUCTURAL_MOCK
    assert rec_naked.is_success is True
    assert rec_naked.score == 1.0
    assert rec_naked.is_qualified_success is True
    assert rec_naked.evidence_modality == EvidenceModality.STRUCTURAL_MOCK
    assert rec_naked.evidence_modality != EvidenceModality.EMPIRICAL_MODEL
    assert rec_naked.provider_receipt is None

    rec_ts = runner.run_task_ten_shadows(pretend_adapter, task)
    assert rec_ts.is_success is True
    assert rec_ts.score == 1.0
    assert rec_ts.evidence_modality == EvidenceModality.STRUCTURAL_MOCK
    assert rec_ts.evidence_modality != EvidenceModality.EMPIRICAL_MODEL


def test_acceptance_o_corrupted_or_deleted_provider_receipt_fails_closed_on_record_construction():
    """
    Acceptance Test 3 (from repair contract):
    Deleting or corrupting the provider-execution receipt must make record construction fail closed.
    """
    # 1. Attempting to construct EMPIRICAL_MODEL TaskRunRecord with missing receipt must raise ValueError
    with pytest.raises(ValueError, match="EMPIRICAL_MODEL requires a valid ProviderExecutionReceipt"):
        TaskRunRecord(
            task_id="BM_TASK_TEST",
            dimension=BenchmarkDimension.KNOWLEDGE,
            model_id="gemini-3.7-flash",
            provider="google",
            execution_mode="NAKED",
            is_success=True,
            score=1.0,
            evidence_modality=EvidenceModality.EMPIRICAL_MODEL,
            provider_receipt=None,
            attempts=1,
            total_model_calls=1,
            latency_seconds=0.5,
            tokens_consumed=200,
        )

    valid_receipt = ProviderExecutionReceipt(
        request_id="req_001",
        response_id="resp_001",
        provider_name="google",
        model_id="gemini-3.7-flash",
        latency_seconds=0.2,
        tokens_prompt=10,
        tokens_completion=20,
        tokens_total=30,
        payload_digest="abcd" * 16,
    )

    # 2. Attempting to construct EMPIRICAL_MODEL TaskRunRecord with corrupted receipt digest must fail
    corrupted_receipt = valid_receipt.model_copy(deep=True)
    corrupted_receipt.receipt_digest = "deadbeef" * 8
    with pytest.raises(ValueError, match="Corrupted ProviderExecutionReceipt digest"):
        TaskRunRecord(
            task_id="BM_TASK_TEST",
            dimension=BenchmarkDimension.KNOWLEDGE,
            model_id="gemini-3.7-flash",
            provider="google",
            execution_mode="NAKED",
            is_success=True,
            score=1.0,
            evidence_modality=EvidenceModality.EMPIRICAL_MODEL,
            provider_receipt=corrupted_receipt,
            attempts=1,
            total_model_calls=1,
            latency_seconds=0.5,
            tokens_consumed=200,
        )

    # 3. Attempting to construct EMPIRICAL_MODEL TaskRunRecord with mismatched model/provider identity must fail
    mismatched_receipt = valid_receipt.model_copy(deep=True)
    with pytest.raises(ValueError, match="ProviderExecutionReceipt does not match"):
        TaskRunRecord(
            task_id="BM_TASK_TEST",
            dimension=BenchmarkDimension.KNOWLEDGE,
            model_id="gemini-3.7-flash",
            provider="anthropic",  # Mismatch with receipt provider 'google'
            execution_mode="NAKED",
            is_success=True,
            score=1.0,
            evidence_modality=EvidenceModality.EMPIRICAL_MODEL,
            provider_receipt=mismatched_receipt,
            attempts=1,
            total_model_calls=1,
            latency_seconds=0.5,
            tokens_consumed=200,
        )


def test_acceptance_p_validated_response_bound_provider_receipt_produces_qualified_empirical_record():
    """
    Acceptance Test 4 (from repair contract):
    Only an integration fixture carrying a validated, response-bound provider receipt
    may produce a QUALIFIED EMPIRICAL_MODEL record.
    """
    task = create_deterministic_knowledge_task(seed=42)
    rules = task.required_knowledge["tariff_rules"]

    class VerifiedProviderIntegrationFixture(ModelAdapter):
        @property
        def model_id(self) -> str:
            return "gemini-3.7-flash"

        @property
        def provider_name(self) -> str:
            return "google"

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
            candidate_payload = {"status": "SUCCESS", "code": code}
            raw_response = {
                "responseId": "resp_live_google_123",
                "candidates": [{"content": {"parts": [{"text": code}]}}],
            }
            payload_digest = compute_provider_payload_digest(
                candidate_payload=candidate_payload,
                raw_response=raw_response,
                objective=req.objective,
            )
            receipt = ProviderExecutionReceipt(
                request_id="req_google_int_001",
                response_id="resp_live_google_123",
                provider_name=self.provider_name,
                model_id=self.model_id,
                latency_seconds=0.42,
                tokens_prompt=150,
                tokens_completion=280,
                tokens_total=430,
                payload_digest=payload_digest,
            )
            return ModelResponse(
                task_id=req.task_id,
                candidate_payload=candidate_payload,
                model_identifier=self.model_id,
                provider=self.provider_name,
                tokens_consumed=430,
                latency_seconds=0.42,
                is_success=True,
                raw_response=raw_response,
                provider_receipt=receipt,
            )

    runner = BenchmarkRunner()
    strong_fixture = VerifiedProviderIntegrationFixture()

    class WeakVerifiedProviderIntegrationFixture(ModelAdapter):
        @property
        def model_id(self) -> str:
            return "gemini-3.7-flash-weak"

        @property
        def provider_name(self) -> str:
            return "google"

        def execute(self, req: ModelRequest) -> ModelResponse:
            domain_knowledge = (
                req.compiled_context.get("AUTHORITATIVE", {}).get("knowledge")
                or req.compiled_context.get("domain_knowledge")
                or {}
            )
            has_knowledge = bool(domain_knowledge.get("tariff_rules"))
            if has_knowledge:
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
                cand = {"status": "SUCCESS", "code": code}
            else:
                cand = {"status": "PARTIAL", "code": "def calculate_tariff(tier: str, amount: float): return 0.0\n"}

            raw_resp = {"responseId": "resp_live_google_weak_456"}
            p_digest = compute_provider_payload_digest(
                candidate_payload=cand,
                raw_response=raw_resp,
                objective=req.objective,
            )
            rcpt = ProviderExecutionReceipt(
                request_id="req_google_weak_002",
                response_id="resp_live_google_weak_456",
                provider_name=self.provider_name,
                model_id=self.model_id,
                latency_seconds=0.55,
                tokens_prompt=100,
                tokens_completion=200,
                tokens_total=300,
                payload_digest=p_digest,
            )
            return ModelResponse(
                task_id=req.task_id,
                candidate_payload=cand,
                model_identifier=self.model_id,
                provider=self.provider_name,
                tokens_consumed=300,
                latency_seconds=0.55,
                is_success=True,
                raw_response=raw_resp,
                provider_receipt=rcpt,
            )

    weak_fixture = WeakVerifiedProviderIntegrationFixture()

    # 1. In Naked mode: Produces QUALIFIED EMPIRICAL_MODEL record
    rec_naked = runner.run_task_naked(strong_fixture, task)
    assert rec_naked.is_success is True
    assert rec_naked.score == 1.0
    assert rec_naked.qualification == EvidenceQualification.QUALIFIED
    assert rec_naked.is_qualified_success is True
    assert rec_naked.evidence_modality == EvidenceModality.EMPIRICAL_MODEL
    assert rec_naked.provider_receipt is not None
    assert rec_naked.provider_receipt.provider_name == "google"
    assert rec_naked.provider_receipt.receipt_digest != ""

    # 2. In Ten Shadows mode: Produces QUALIFIED EMPIRICAL_MODEL record
    rec_ts = runner.run_task_ten_shadows(strong_fixture, task)
    assert rec_ts.is_success is True
    assert rec_ts.score == 1.0
    assert rec_ts.qualification == EvidenceQualification.QUALIFIED
    assert rec_ts.is_qualified_success is True
    assert rec_ts.evidence_modality == EvidenceModality.EMPIRICAL_MODEL
    assert rec_ts.provider_receipt is not None

    # 3. In Comparative Benchmark between two verified provider adapters:
    res = runner.run_comparative_benchmark(strong_fixture, weak_fixture, corpus=[task])
    assert res.evidence_modality == EvidenceModality.EMPIRICAL_MODEL
    assert res.naked_score_a == 1.0
    assert res.naked_score_b == 0.0
    assert res.ten_shadows_score_a == 1.0
    assert res.ten_shadows_score_b == 1.0
    assert res.model_elasticity == 0.0
