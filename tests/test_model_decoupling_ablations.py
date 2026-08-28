"""
tests/test_model_decoupling_ablations.py
Ablation Testing Suite for Model-Decoupling Interventions (10 SHADOWS).

Proves that each compensatory component (Context Compiler, Deficit Protocol,
Failure Feedback, Adaptive Search) measurably contributes to weak model recovery.
"""

from loop_engine.model.benchmark import BenchmarkRunner, create_canonical_benchmark_corpus
from loop_engine.model.boundary import MockModelAdapter, MockModelProfile


def test_ablation_without_context_compiler_reduces_recovery():
    weak_model = MockModelAdapter(profile=MockModelProfile.WEAK)
    runner = BenchmarkRunner()
    corpus = create_canonical_benchmark_corpus()
    task = [t for t in corpus if t.task_id == "BM_IMPLEMENTATION_01"][0]

    # Full Ten Shadows succeeds
    res_full = runner.run_task_ten_shadows(weak_model, task, enable_context_compiler=True)
    assert res_full.is_success is True

    # Ablating Context Compiler causes failure on first search attempt
    res_ablated = runner.run_task_ten_shadows(
        weak_model,
        task,
        enable_context_compiler=False,
        enable_repair_feedback=False,
    )
    assert res_ablated.is_success is False


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
    weak_model = MockModelAdapter(profile=MockModelProfile.WEAK)
    runner = BenchmarkRunner()
    corpus = create_canonical_benchmark_corpus()
    task = [t for t in corpus if t.task_id == "BM_MEMORY_01"][0]

    # With failure feedback, attempt 2 succeeds
    res_full = runner.run_task_ten_shadows(weak_model, task, enable_repair_feedback=True)
    assert res_full.is_success is True

    # Without failure feedback (max_repairs=1), weak model stays in initial flawed state
    res_ablated = runner.run_task_ten_shadows(weak_model, task, enable_repair_feedback=False)
    assert res_ablated.is_success is False
