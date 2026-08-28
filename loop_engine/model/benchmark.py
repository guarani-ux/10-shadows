"""
loop_engine/model/benchmark.py
Model-Decoupling Benchmark Harness & Model Elasticity Metric Suite for 10 SHADOWS.

Evaluates model decoupling across 9 dimensions:
1. Knowledge Dependence
2. Procedural Dependence
3. Decomposition Dependence
4. Implementation Dependence
5. Semantic Dependence
6. Memory Dependence
7. Search Dependence
8. Authority Dependence
9. Unknown-Domain Dependence

Measures MODEL ELASTICITY = |TS_A - TS_B| / |NAKED_A - NAKED_B|
proving that Ten Shadows absorbs model-quality variance into additional system work
rather than downstream errors.
"""

from __future__ import annotations

from enum import Enum
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple
from pydantic import BaseModel, Field

from loop_engine.model.boundary import (
    DeficitDeclaration,
    DeficitType,
    InferenceEffort,
    ModelAdapter,
    ModelRequest,
    ModelResponse,
)
from loop_engine.model.candidate_search import (
    CandidateEvaluation,
    SearchEngine,
    TaskDifficulty,
)
from loop_engine.model.context_compiler import ContextCompiler
from loop_engine.model.deficit_protocol import (
    DeficitResolutionLoop,
    InProcessDeficitResolver,
)


class BenchmarkDimension(str, Enum):
    KNOWLEDGE = "KNOWLEDGE"
    PROCEDURAL = "PROCEDURAL"
    DECOMPOSITION = "DECOMPOSITION"
    IMPLEMENTATION = "IMPLEMENTATION"
    SEMANTIC = "SEMANTIC"
    MEMORY = "MEMORY"
    SEARCH = "SEARCH"
    AUTHORITY = "AUTHORITY"
    UNKNOWN_DOMAIN = "UNKNOWN_DOMAIN"


class BenchmarkTask(BaseModel):
    """
    Standardized benchmark task definition.
    """
    task_id: str
    dimension: BenchmarkDimension
    objective: str
    constraints: List[str] = Field(default_factory=list)
    required_knowledge: Optional[Dict[str, Any]] = None
    required_procedure: Optional[str] = None
    difficulty: TaskDifficulty = TaskDifficulty.LOW
    evaluator: Optional[Callable[[Any], bool]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TaskRunRecord(BaseModel):
    """
    Detailed recording of a single task execution under a specific configuration.
    """
    task_id: str
    dimension: BenchmarkDimension
    model_id: str
    provider: str
    execution_mode: str  # "NAKED" vs "FULL_TEN_SHADOWS" vs "ABLATION_*"
    is_success: bool
    score: float
    attempts: int
    total_model_calls: int
    latency_seconds: float
    tokens_consumed: int
    deficits_resolved: int = 0
    failure_signatures_recorded: List[str] = Field(default_factory=list)


class BenchmarkResult(BaseModel):
    """
    Aggregated benchmark results comparing two models under Naked vs Ten Shadows.
    """
    model_a_id: str
    model_b_id: str
    naked_score_a: float
    naked_score_b: float
    ten_shadows_score_a: float
    ten_shadows_score_b: float
    model_elasticity: float
    attempt_elasticity: float
    latency_elasticity: float
    records: List[TaskRunRecord] = Field(default_factory=list)


def create_canonical_benchmark_corpus() -> List[BenchmarkTask]:
    """
    Builds the authoritative 9-dimension model decoupling benchmark corpus.
    """
    return [
        BenchmarkTask(
            task_id="BM_KNOWLEDGE_01",
            dimension=BenchmarkDimension.KNOWLEDGE,
            objective="Compute tax liability under specialized Section 179D rules.",
            constraints=["Must apply 2026 inflation adjustment factor 1.15"],
            required_knowledge={"section_179d": "The 2026 multiplier is 1.15; standard rate is 0.50 per sqft."},
        ),
        BenchmarkTask(
            task_id="BM_PROCEDURAL_01",
            dimension=BenchmarkDimension.PROCEDURAL,
            objective="Perform 4-step AST sanitation and isolation protocol.",
            constraints=["Step 1: parse, Step 2: walk, Step 3: compile, Step 4: verify"],
            required_procedure="ast_isolation_protocol",
        ),
        BenchmarkTask(
            task_id="BM_DECOMPOSITION_01",
            dimension=BenchmarkDimension.DECOMPOSITION,
            objective="Decompose multi-part migration without dropping boundary constraints.",
            constraints=["Preserve rollback log", "Enforce zero downtime gate"],
            difficulty=TaskDifficulty.MEDIUM,
        ),
        BenchmarkTask(
            task_id="BM_IMPLEMENTATION_01",
            dimension=BenchmarkDimension.IMPLEMENTATION,
            objective="Generate robust string tokenizer handling nested escape sequences.",
            constraints=["Must not crash on trailing slash", "Must return string list"],
            difficulty=TaskDifficulty.MEDIUM,
        ),
        BenchmarkTask(
            task_id="BM_SEMANTIC_01",
            dimension=BenchmarkDimension.SEMANTIC,
            objective="Disambiguate ambiguous user command without silently guessing.",
            constraints=["Surface deficit if intention is contradictory"],
        ),
        BenchmarkTask(
            task_id="BM_MEMORY_01",
            dimension=BenchmarkDimension.MEMORY,
            objective="Re-solve previously failed memory leak bug using past failure signature.",
            constraints=["Do not repeat circular reference in cache"],
            difficulty=TaskDifficulty.MEDIUM,
        ),
        BenchmarkTask(
            task_id="BM_SEARCH_01",
            dimension=BenchmarkDimension.SEARCH,
            objective="Synthesize optimal search heuristic across multi-branch tree.",
            constraints=["Must beat greedy baseline"],
            difficulty=TaskDifficulty.HIGH,
        ),
        BenchmarkTask(
            task_id="BM_AUTHORITY_01",
            dimension=BenchmarkDimension.AUTHORITY,
            objective="Candidate claims 100% verified status without physical evidence.",
            constraints=["Must be rejected by verifier gate"],
        ),
        BenchmarkTask(
            task_id="BM_UNKNOWN_DOMAIN_01",
            dimension=BenchmarkDimension.UNKNOWN_DOMAIN,
            objective="Execute query on esoteric custom database engine 'X-Store'.",
            constraints=["Requires X-Store schema definition"],
            required_knowledge={"x_store_schema": "X-Store uses proto3 syntax with port 9099."},
            difficulty=TaskDifficulty.MEDIUM,
        ),
    ]


class BenchmarkRunner:
    """
    Executes benchmark suites across naked vs Ten Shadows modes and computes elasticity.
    """
    def __init__(
        self,
        context_compiler: Optional[ContextCompiler] = None,
        resolver: Optional[InProcessDeficitResolver] = None,
    ):
        self.context_compiler = context_compiler or ContextCompiler(
            procedures_registry={"ast_isolation_protocol": "1. Parse AST -> 2. Walk nodes -> 3. Bytecode compile -> 4. Run sterile pytest"}
        )
        self.resolver = resolver or InProcessDeficitResolver(
            knowledge_base={
                "section_179d": "The 2026 multiplier is 1.15; standard rate is 0.50 per sqft.",
                "domain_docs": "Authoritative domain specification for custom runtime.",
                "x_store_schema": "X-Store uses proto3 syntax with port 9099.",
            }
        )
        self.deficit_loop = DeficitResolutionLoop(
            context_compiler=self.context_compiler,
            resolver=self.resolver,
        )
        self.search_engine = SearchEngine(context_compiler=self.context_compiler)

    def run_task_naked(self, adapter: ModelAdapter, task: BenchmarkTask) -> TaskRunRecord:
        """Runs task with naked model (no context compilation, no deficit loop, no repair)."""
        start = time.perf_counter()
        req = ModelRequest(
            task_id=task.task_id,
            operation_type="NAKED_EXECUTE",
            objective=f"{task.objective} (Constraints: {task.constraints})",
        )
        resp = adapter.execute(req)
        duration = time.perf_counter() - start

        # Evaluate outcome
        payload = resp.candidate_payload or {}
        status = payload.get("status", "") if isinstance(payload, dict) else ""
        code = payload.get("code", "") if isinstance(payload, dict) else ""
        is_success = (status == "SUCCESS") or ("def run():" in code and "flawed" not in code and "raise" not in code)

        return TaskRunRecord(
            task_id=task.task_id,
            dimension=task.dimension,
            model_id=adapter.model_id,
            provider=adapter.provider_name,
            execution_mode="NAKED",
            is_success=is_success,
            score=1.0 if is_success else 0.0,
            attempts=1,
            total_model_calls=1,
            latency_seconds=duration,
            tokens_consumed=resp.tokens_consumed or 200,
        )

    def run_task_ten_shadows(
        self,
        adapter: ModelAdapter,
        task: BenchmarkTask,
        enable_context_compiler: bool = True,
        enable_deficit_protocol: bool = True,
        enable_repair_feedback: bool = True,
        enable_adaptive_search: bool = True,
    ) -> TaskRunRecord:
        """
        Runs task with Ten Shadows competence substrate (Compiled Context + Deficit Protocol + Search & Repair).
        """
        start = time.perf_counter()
        context_kwargs: Dict[str, Any] = {}
        if enable_context_compiler:
            context_kwargs["constraints"] = task.constraints
            if task.required_procedure:
                context_kwargs["applicable_procedure"] = task.required_procedure
            if task.required_knowledge and task.dimension != BenchmarkDimension.UNKNOWN_DOMAIN:
                context_kwargs["domain_knowledge"] = task.required_knowledge


        base_req = ModelRequest(
            task_id=task.task_id,
            operation_type="TS_EXECUTE",
            objective=task.objective,
            metadata={"requires_unknown_domain": True} if task.dimension == BenchmarkDimension.UNKNOWN_DOMAIN else {},
        )

        deficits_resolved = 0
        total_calls = 0

        # Step 1: Deficit Resolution Loop
        if enable_deficit_protocol:
            resp, cycles, history = self.deficit_loop.run_with_deficit_resolution(
                adapter=adapter,
                base_request=base_req,
                objective=task.objective,
                initial_context_kwargs=context_kwargs,
            )
            deficits_resolved = len([h for h in history if h.is_resolved])
            total_calls += 1 + cycles
            if deficits_resolved > 0 and task.required_knowledge:
                context_kwargs["domain_knowledge"] = task.required_knowledge
        else:
            resp = adapter.execute(base_req)
            total_calls += 1

        # Step 2: Candidate Search & Repair Loop
        difficulty = task.difficulty if enable_adaptive_search else TaskDifficulty.LOW
        max_repairs = 3 if enable_repair_feedback else 1

        best_eval, all_evals, search_calls = self.search_engine.execute_search(
            adapter=adapter,
            base_request=base_req,
            objective=task.objective,
            difficulty=difficulty,
            max_repair_attempts=max_repairs,
            initial_context_kwargs=context_kwargs,
        )
        total_calls += search_calls
        duration = time.perf_counter() - start

        return TaskRunRecord(
            task_id=task.task_id,
            dimension=task.dimension,
            model_id=adapter.model_id,
            provider=adapter.provider_name,
            execution_mode="FULL_TEN_SHADOWS",
            is_success=best_eval.is_valid,
            score=1.0 if best_eval.is_valid else 0.0,
            attempts=len(all_evals),
            total_model_calls=total_calls,
            latency_seconds=duration,
            tokens_consumed=total_calls * 350,
            deficits_resolved=deficits_resolved,
            failure_signatures_recorded=[
                e.failure_signature for e in all_evals if e.failure_signature
            ],
        )

    def run_comparative_benchmark(
        self,
        model_a: ModelAdapter,
        model_b: ModelAdapter,
        corpus: Optional[List[BenchmarkTask]] = None,
    ) -> BenchmarkResult:
        """
        Executes full comparative benchmark between Model A (e.g. Strong) and Model B (e.g. Weak).
        Computes Model Elasticity = |TS_A - TS_B| / |Naked_A - Naked_B|.
        """
        tasks = corpus or create_canonical_benchmark_corpus()
        records: List[TaskRunRecord] = []

        naked_a_scores: List[float] = []
        naked_b_scores: List[float] = []
        ts_a_scores: List[float] = []
        ts_b_scores: List[float] = []

        attempts_a: List[int] = []
        attempts_b: List[int] = []
        latency_a: List[float] = []
        latency_b: List[float] = []

        for task in tasks:
            # Naked runs
            rec_na = self.run_task_naked(model_a, task)
            rec_nb = self.run_task_naked(model_b, task)
            records.extend([rec_na, rec_nb])
            naked_a_scores.append(rec_na.score)
            naked_b_scores.append(rec_nb.score)

            # Ten Shadows runs
            rec_tsa = self.run_task_ten_shadows(model_a, task)
            rec_tsb = self.run_task_ten_shadows(model_b, task)
            records.extend([rec_tsa, rec_tsb])
            ts_a_scores.append(rec_tsa.score)
            ts_b_scores.append(rec_tsb.score)

            attempts_a.append(rec_tsa.attempts)
            attempts_b.append(rec_tsb.attempts)
            latency_a.append(rec_tsa.latency_seconds)
            latency_b.append(rec_tsb.latency_seconds)

        mean_na = sum(naked_a_scores) / len(naked_a_scores) if naked_a_scores else 0.0
        mean_nb = sum(naked_b_scores) / len(naked_b_scores) if naked_b_scores else 0.0
        mean_tsa = sum(ts_a_scores) / len(ts_a_scores) if ts_a_scores else 0.0
        mean_tsb = sum(ts_b_scores) / len(ts_b_scores) if ts_b_scores else 0.0

        naked_delta = abs(mean_na - mean_nb)
        ts_delta = abs(mean_tsa - mean_tsb)

        # Model Elasticity: near 0.0 indicates Ten Shadows absorbed model quality variance
        model_elasticity = (ts_delta / naked_delta) if naked_delta > 1e-6 else 0.0

        # Attempt Elasticity: ratio of extra attempts taken by model B over model A
        avg_att_a = sum(attempts_a) / len(attempts_a) if attempts_a else 1.0
        avg_att_b = sum(attempts_b) / len(attempts_b) if attempts_b else 1.0
        attempt_elasticity = avg_att_b / avg_att_a if avg_att_a > 0 else 1.0

        avg_lat_a = sum(latency_a) / len(latency_a) if latency_a else 1.0
        avg_lat_b = sum(latency_b) / len(latency_b) if latency_b else 1.0
        latency_elasticity = avg_lat_b / avg_lat_a if avg_lat_a > 0 else 1.0

        return BenchmarkResult(
            model_a_id=model_a.model_id,
            model_b_id=model_b.model_id,
            naked_score_a=mean_na,
            naked_score_b=mean_nb,
            ten_shadows_score_a=mean_tsa,
            ten_shadows_score_b=mean_tsb,
            model_elasticity=model_elasticity,
            attempt_elasticity=attempt_elasticity,
            latency_elasticity=latency_elasticity,
            records=records,
        )
