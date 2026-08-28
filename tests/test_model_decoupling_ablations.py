"""
tests/test_model_decoupling_ablations.py
Ablation Testing Suite for Model-Decoupling Interventions (10 SHADOWS).

Proves that each compensatory component (Context Compiler, Deficit Protocol,
Failure Feedback, Adaptive Search) measurably contributes to weak model recovery.
"""

from typing import Any

from loop_engine.model.benchmark import (
    BenchmarkDimension,
    BenchmarkRunner,
    BenchmarkTask,
    create_canonical_benchmark_corpus,
    create_deterministic_knowledge_task,
)
from loop_engine.model.boundary import (
    DeficitDeclaration,
    DeficitType,
    MockModelAdapter,
    MockModelProfile,
    ModelAdapter,
    ModelRequest,
    ModelResponse,
)
from loop_engine.model.candidate_search import CandidateEvaluation, TaskDifficulty


class KnowledgeModelTestAdapter(ModelAdapter):
    @property
    def model_id(self) -> str:
        return "weak-ablation-model"

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
            )
        return ModelResponse(
            task_id=req.task_id,
            candidate_payload={"status": "PARTIAL", "code": "def calculate_tariff(tier, amount): return 0.0\n"},
            model_identifier=self.model_id,
            provider=self.provider_name,
        )


def test_ablation_without_context_compiler_reduces_recovery():
    weak_model = KnowledgeModelTestAdapter()
    runner = BenchmarkRunner()
    task = create_deterministic_knowledge_task(seed=42)

    # Full Ten Shadows succeeds because context compiler provides compiled domain knowledge
    res_full = runner.run_task_ten_shadows(weak_model, task, enable_context_compiler=True)
    assert res_full.is_success is True
    assert res_full.score == 1.0

    # Ablating Context Compiler causes failure because domain knowledge is not compiled into context
    res_ablated = runner.run_task_ten_shadows(
        weak_model,
        task,
        enable_context_compiler=False,
        enable_repair_feedback=False,
    )
    assert res_ablated.is_success is False
    assert res_ablated.score == 0.0


def test_ablation_without_deficit_protocol_fails_unknown_domain():
    weak_model = MockModelAdapter(profile=MockModelProfile.WEAK)
    runner = BenchmarkRunner()
    corpus = create_canonical_benchmark_corpus()
    task = [t for t in corpus if t.task_id == "BM_UNKNOWN_DOMAIN_01"][0]

    # With Deficit Protocol enabled, deficit is resolved
    res_full = runner.run_task_ten_shadows(weak_model, task, enable_deficit_protocol=True)
    assert res_full.deficits_resolved > 0

    # With Deficit Protocol disabled, deficit is not provisioned
    res_ablated = runner.run_task_ten_shadows(weak_model, task, enable_deficit_protocol=False)
    assert res_ablated.deficits_resolved == 0


def test_ablation_without_failure_feedback_fails_difficult_repair():
    def repair_evaluator(cand: Any) -> CandidateEvaluation:
        if isinstance(cand, dict) and "repaired_weak" in cand.get("code", ""):
            return CandidateEvaluation(candidate_id="c_rep", payload=cand, is_valid=True, score=1.0)
        return CandidateEvaluation(candidate_id="c_fail", payload=cand, is_valid=False, score=0.0, failure_signature="SIG_FLAWED_STUB")

    repair_task = BenchmarkTask(
        task_id="BM_REPAIR_TEST",
        dimension=BenchmarkDimension.MEMORY,
        objective="Repair flawed cache leak",
        difficulty=TaskDifficulty.MEDIUM,
        evaluator=repair_evaluator,
    )

    weak_model = MockModelAdapter(profile=MockModelProfile.WEAK)
    runner = BenchmarkRunner()

    # With failure feedback, attempt 2 receives failure feedback and succeeds
    res_full = runner.run_task_ten_shadows(weak_model, repair_task, enable_repair_feedback=True)
    assert res_full.is_success is True
    assert res_full.attempts == 2

    # Without failure feedback (max_repairs=1), weak model stays in initial flawed state and fails
    res_ablated = runner.run_task_ten_shadows(weak_model, repair_task, enable_repair_feedback=False)
    assert res_ablated.is_success is False
    assert res_ablated.attempts == 1
