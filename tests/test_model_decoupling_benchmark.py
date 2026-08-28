"""
tests/test_model_decoupling_benchmark.py
9-Dimension Benchmark & Model Elasticity Test Suite for 10 SHADOWS.
"""

from loop_engine.model.benchmark import (
    BenchmarkDimension,
    BenchmarkRunner,
    create_canonical_benchmark_corpus,
)
from loop_engine.model.boundary import (
    MockModelAdapter,
    MockModelProfile,
)


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
    assert result.naked_score_a == 1.0
    assert result.naked_score_b == 0.0  # Naked weak model fails unassisted

    # 2. Verify Ten Shadows absorbs model variance (Both reach 100% verified success)
    assert result.ten_shadows_score_a == 1.0
    assert result.ten_shadows_score_b == 1.0

    # 3. Model Elasticity must be 0.0 (|TS_A - TS_B| / |Naked_A - Naked_B| = 0.0 / 1.0 = 0.0)
    assert result.model_elasticity == 0.0

    # 4. Attempt Elasticity & Latency Elasticity > 1.0 (Weak model took more attempts/work to converge)
    assert result.attempt_elasticity >= 1.0
    assert result.latency_elasticity >= 1.0
