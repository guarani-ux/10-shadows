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
import hashlib
import random
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union
from pydantic import BaseModel, Field

from loop_engine.model.boundary import (
    DeficitDeclaration,
    DeficitType,
    EvidenceModality,
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
from loop_engine.schema import State


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


class EvidenceQualification(str, Enum):
    QUALIFIED = "QUALIFIED"
    UNQUALIFIED = "UNQUALIFIED"


class BenchmarkTask(BaseModel):
    """
    Standardized benchmark task definition with authoritative physical evaluator.
    Tasks without independent task-specific behavioral verifiers must be marked UNQUALIFIED.
    """
    task_id: str
    dimension: BenchmarkDimension
    objective: str
    constraints: List[str] = Field(default_factory=list)
    required_knowledge: Optional[Dict[str, Any]] = None
    required_procedure: Optional[str] = None
    difficulty: TaskDifficulty = TaskDifficulty.LOW
    seed: Optional[int] = None
    evaluator: Optional[Callable[[Any], CandidateEvaluation]] = None
    verifier_identity: str = "task_physical_evaluator"
    verifier_version: str = "1.0.0"
    qualification: EvidenceQualification = EvidenceQualification.QUALIFIED
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        if self.evaluator is None:
            self.qualification = EvidenceQualification.UNQUALIFIED

    @property
    def is_qualified(self) -> bool:
        return self.qualification == EvidenceQualification.QUALIFIED and self.evaluator is not None


class TaskRunRecord(BaseModel):
    """
    Detailed physical recording of a single task execution with cryptographic reproducibility receipt.
    """
    task_id: str
    task_seed: Optional[int] = None
    dimension: BenchmarkDimension
    model_id: str
    provider: str
    execution_mode: str  # "NAKED" vs "FULL_TEN_SHADOWS" vs "ABLATION_*"
    is_success: bool
    score: float
    evidence_modality: EvidenceModality = EvidenceModality.STRUCTURAL_MOCK
    qualification: EvidenceQualification = EvidenceQualification.QUALIFIED
    is_qualified_success: bool = False
    supplied_context_digest: str = ""
    candidate_digest: str = ""
    verifier_identity: str = "task_physical_evaluator"
    verifier_version: str = "1.0.0"
    execution_trace_digest: str = ""
    observed_outputs: Optional[List[Any]] = None
    attempts: int
    total_model_calls: int
    latency_seconds: float
    tokens_consumed: int
    deficits_resolved: int = 0
    failure_signatures_recorded: List[str] = Field(default_factory=list)
    receipt_digest: str = ""

    def model_post_init(self, __context: Any) -> None:
        # Enforce invariant: Mock runs cannot be labeled empirical
        if (self.provider == "mock" or "mock" in self.model_id.lower()) and self.evidence_modality == EvidenceModality.EMPIRICAL_MODEL:
            raise ValueError("Mock runs cannot be labeled empirical.")

        if self.qualification == EvidenceQualification.UNQUALIFIED:
            self.is_qualified_success = False
            self.is_success = False
            self.score = 0.0
        else:
            self.is_qualified_success = bool(self.is_success and self.score > 0.0)

        if not self.receipt_digest:
            raw = (
                f"{self.task_id}:{self.task_seed}:{self.dimension.value}:{self.model_id}:"
                f"{self.execution_mode}:{self.is_success}:{self.score}:{self.evidence_modality.value}:"
                f"{self.qualification.value}:{self.is_qualified_success}:{self.supplied_context_digest}:"
                f"{self.candidate_digest}:{self.verifier_identity}:{self.verifier_version}:"
                f"{self.execution_trace_digest}:{self.attempts}:{self.total_model_calls}"
            )
            self.receipt_digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()


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
    model_elasticity: Union[float, str]
    attempt_elasticity: Union[float, str]
    latency_elasticity: Union[float, str]
    qualified_task_ids: List[str] = Field(default_factory=list)
    unqualified_task_ids: List[str] = Field(default_factory=list)
    evidence_modality: EvidenceModality = EvidenceModality.STRUCTURAL_MOCK
    records: List[TaskRunRecord] = Field(default_factory=list)

    def model_post_init(self, __context: Any) -> None:
        if self.evidence_modality == EvidenceModality.EMPIRICAL_MODEL:
            if "mock" in self.model_a_id.lower() or "mock" in self.model_b_id.lower():
                raise ValueError("Mock runs cannot be labeled empirical.")


def create_deterministic_knowledge_task(
    seed: int = 42,
    task_id: Optional[str] = None,
    transition_engine: Optional[Any] = None,
) -> BenchmarkTask:
    """
    Creates a deterministic, held-out physical knowledge task generated from an immutable seed.
    Rules and held-out test cases are generated strictly outside model reach.
    """
    rng = random.Random(seed)
    tier_names = ["TIER_ALPHA", "TIER_BETA", "TIER_GAMMA", "TIER_DELTA", "TIER_EPSILON"]
    tariff_rules: Dict[str, Dict[str, float]] = {}
    for tier in tier_names:
        tariff_rules[tier] = {
            "rate": round(rng.uniform(0.5, 3.5), 2),
            "threshold": round(rng.uniform(50.0, 500.0), 1),
            "base": round(rng.uniform(10.0, 100.0), 2),
            "surcharge": round(rng.uniform(1.0, 25.0), 2),
        }

    def reference_tariff(tier: str, amount: float, rules: Dict[str, Dict[str, float]]) -> float:
        if tier not in rules:
            return 0.0
        r = rules[tier]
        base = r["base"]
        rate = r["rate"]
        thresh = r["threshold"]
        surcharge = r["surcharge"]
        if amount > thresh:
            val = base + (amount - thresh) * rate + surcharge
        else:
            val = base + amount * (rate * 0.5)
        return round(val, 4)

    held_out_cases: List[Tuple[str, float, float]] = []
    for tier in tier_names + ["TIER_UNKNOWN"]:
        amounts = [round(rng.uniform(0.0, 800.0), 2) for _ in range(3)]
        for amt in amounts:
            exp = reference_tariff(tier, amt, tariff_rules)
            held_out_cases.append((tier, amt, exp))

    tid = task_id or f"BM_KNOWLEDGE_SEED_{seed}"

    def task_physical_evaluator(candidate: Any) -> CandidateEvaluation:
        cid = f"cand_{hashlib.sha256(str(candidate).encode('utf-8')).hexdigest()[:8]}"
        if not isinstance(candidate, dict):
            return CandidateEvaluation(
                candidate_id=cid,
                payload=candidate,
                is_valid=False,
                score=0.0,
                failure_classification="CANDIDATE_FAILURE",
                failure_signature="SIG_INVALID_PAYLOAD_STRUCTURE",
                execution_trace="Candidate payload is not a dictionary.",
            )

        code = candidate.get("code", "")
        if not code or not isinstance(code, str):
            return CandidateEvaluation(
                candidate_id=cid,
                payload=candidate,
                is_valid=False,
                score=0.0,
                failure_classification="CANDIDATE_FAILURE",
                failure_signature="SIG_NO_CODE",
                execution_trace="Candidate payload missing valid 'code' string.",
            )

        exec_globals: Dict[str, Any] = {"__builtins__": __builtins__}
        exec_locals: Dict[str, Any] = {}
        try:
            compiled = compile(code, f"<task_{tid}>", "exec")
            exec(compiled, exec_globals, exec_locals)
        except Exception as e:
            return CandidateEvaluation(
                candidate_id=cid,
                payload=candidate,
                is_valid=False,
                score=0.0,
                failure_classification="CANDIDATE_FAILURE",
                failure_signature="SIG_EXECUTION_EXCEPTION",
                execution_trace=f"Candidate raised execution exception: {type(e).__name__}: {str(e)}",
            )

        fn = exec_locals.get("calculate_tariff")
        if not callable(fn):
            return CandidateEvaluation(
                candidate_id=cid,
                payload=candidate,
                is_valid=False,
                score=0.0,
                failure_classification="CANDIDATE_FAILURE",
                failure_signature="SIG_MISSING_FUNCTION",
                execution_trace="Candidate did not define callable function 'calculate_tariff'.",
            )

        observed: List[float] = []
        for tier, amt, expected_val in held_out_cases:
            try:
                obs_val = fn(tier, amt)
                obs_float = round(float(obs_val), 4)
                observed.append(obs_float)
                if abs(obs_float - expected_val) > 1e-4:
                    return CandidateEvaluation(
                        candidate_id=cid,
                        payload=candidate,
                        is_valid=False,
                        score=0.0,
                        failure_classification="CANDIDATE_FAILURE",
                        failure_signature="SIG_OUTPUT_MISMATCH",
                        execution_trace=f"Physical output mismatch for ({tier}, {amt}): expected {expected_val}, got {obs_float}",
                        observed_outputs=observed,
                    )
            except Exception as e:
                return CandidateEvaluation(
                    candidate_id=cid,
                    payload=candidate,
                    is_valid=False,
                    score=0.0,
                    failure_classification="CANDIDATE_FAILURE",
                    failure_signature="SIG_RUNTIME_ERROR",
                    execution_trace=f"Runtime error on input ({tier}, {amt}): {type(e).__name__}: {str(e)}",
                    observed_outputs=observed,
                )

        # If transition engine is active, enforce the privileged transition seam
        if transition_engine is not None:
            from loop_engine.authority import issue_proof_witness
            from loop_engine.transition import (
                TransitionRequest,
                TransitionRejection,
                compute_complete_claim_digest,
                compute_governance_digest,
            )
            evidence_digest = hashlib.sha256(str(observed).encode("utf-8")).hexdigest()
            gov_digest = compute_governance_digest()
            candidate_digest = hashlib.sha256(code.encode("utf-8")).hexdigest()

            claim_digest = compute_complete_claim_digest(
                task_id=tid,
                from_state=State.CANDIDATE_SEALED,
                to_state=State.VERIFIED,
                subject_identity=candidate_digest,
                candidate_tree_sha=candidate_digest,
                spec_hash=hashlib.sha256(str(tariff_rules).encode("utf-8")).hexdigest(),
                acceptance_test_digest=hashlib.sha256(str(held_out_cases).encode("utf-8")).hexdigest(),
                evidence_digest=evidence_digest,
                authority_scope="PHYSICAL_VERIFICATION",
                governance_hash=gov_digest,
            )
            witness = issue_proof_witness(
                issuer="loop_engine.model.benchmark",
                target_digest=claim_digest,
                scope="PHYSICAL_VERIFICATION",
            )
            req = TransitionRequest(
                task_id=tid,
                from_state=State.CANDIDATE_SEALED,
                to_state=State.VERIFIED,
                subject_identity=candidate_digest,
                candidate_tree_sha=candidate_digest,
                spec_hash=hashlib.sha256(str(tariff_rules).encode("utf-8")).hexdigest(),
                acceptance_test_digest=hashlib.sha256(str(held_out_cases).encode("utf-8")).hexdigest(),
                evidence_digest=evidence_digest,
                authority_scope="PHYSICAL_VERIFICATION",
                witness=witness,
                governance_hash=gov_digest,
            )
            trans_res = transition_engine.execute_transition(req)
            if isinstance(trans_res, TransitionRejection):
                return CandidateEvaluation(
                    candidate_id=cid,
                    payload=candidate,
                    is_valid=False,
                    score=0.0,
                    failure_classification="VERIFIER_FAILURE",
                    failure_signature="SIG_SEAM_TRANSITION_REJECTED",
                    execution_trace=f"Privileged verification seam rejected transition: {trans_res.reason}",
                    observed_outputs=observed,
                )

        return CandidateEvaluation(
            candidate_id=cid,
            payload=candidate,
            is_valid=True,
            score=1.0,
            execution_trace=f"Passed all {len(held_out_cases)} held-out physical verification test cases.",
            observed_outputs=observed,
        )

    return BenchmarkTask(
        task_id=tid,
        dimension=BenchmarkDimension.KNOWLEDGE,
        objective="Synthesize Python function 'def calculate_tariff(tier: str, amount: float) -> float' according to specialized domain tariff specification.",
        constraints=["Must handle unknown tiers by returning 0.0", "Must round results to 4 decimal places"],
        required_knowledge={"tariff_rules": tariff_rules},
        difficulty=TaskDifficulty.LOW,
        seed=seed,
        evaluator=task_physical_evaluator,
        verifier_identity="physical_tariff_verifier_v1",
        verifier_version="1.0.0",
        metadata={"seed": seed},
    )


def create_canonical_benchmark_corpus(
    seed: int = 42,
    transition_engine: Optional[Any] = None,
) -> List[BenchmarkTask]:
    """
    Builds the authoritative 9-dimension model decoupling benchmark corpus.
    Tasks without an independent task-specific behavioral verifier are explicitly marked UNQUALIFIED.
    """
    # 1. Deterministic Knowledge task (has independent task-specific physical evaluator)
    knowledge_task = create_deterministic_knowledge_task(
        seed=seed,
        task_id="BM_KNOWLEDGE_01",
        transition_engine=transition_engine,
    )

    return [
        knowledge_task,
        BenchmarkTask(
            task_id="BM_PROCEDURAL_01",
            dimension=BenchmarkDimension.PROCEDURAL,
            objective="Perform 4-step AST sanitation and isolation protocol.",
            constraints=["Step 1: parse, Step 2: walk, Step 3: compile, Step 4: verify"],
            required_procedure="ast_isolation_protocol",
            evaluator=None,
            qualification=EvidenceQualification.UNQUALIFIED,
        ),
        BenchmarkTask(
            task_id="BM_DECOMPOSITION_01",
            dimension=BenchmarkDimension.DECOMPOSITION,
            objective="Decompose multi-part migration without dropping boundary constraints.",
            constraints=["Preserve rollback log", "Enforce zero downtime gate"],
            difficulty=TaskDifficulty.MEDIUM,
            evaluator=None,
            qualification=EvidenceQualification.UNQUALIFIED,
        ),
        BenchmarkTask(
            task_id="BM_IMPLEMENTATION_01",
            dimension=BenchmarkDimension.IMPLEMENTATION,
            objective="Generate robust string tokenizer handling nested escape sequences.",
            constraints=["Must not crash on trailing slash", "Must return string list"],
            difficulty=TaskDifficulty.MEDIUM,
            evaluator=None,
            qualification=EvidenceQualification.UNQUALIFIED,
        ),
        BenchmarkTask(
            task_id="BM_SEMANTIC_01",
            dimension=BenchmarkDimension.SEMANTIC,
            objective="Disambiguate ambiguous user command without silently guessing.",
            constraints=["Surface deficit if intention is contradictory"],
            evaluator=None,
            qualification=EvidenceQualification.UNQUALIFIED,
        ),
        BenchmarkTask(
            task_id="BM_MEMORY_01",
            dimension=BenchmarkDimension.MEMORY,
            objective="Re-solve previously failed memory leak bug using past failure signature.",
            constraints=["Do not repeat circular reference in cache"],
            difficulty=TaskDifficulty.MEDIUM,
            evaluator=None,
            qualification=EvidenceQualification.UNQUALIFIED,
        ),
        BenchmarkTask(
            task_id="BM_SEARCH_01",
            dimension=BenchmarkDimension.SEARCH,
            objective="Synthesize optimal search heuristic across multi-branch tree.",
            constraints=["Must beat greedy baseline"],
            difficulty=TaskDifficulty.HIGH,
            evaluator=None,
            qualification=EvidenceQualification.UNQUALIFIED,
        ),
        BenchmarkTask(
            task_id="BM_AUTHORITY_01",
            dimension=BenchmarkDimension.AUTHORITY,
            objective="Candidate claims 100% verified status without physical evidence.",
            constraints=["Must be rejected by verifier gate"],
            evaluator=None,
            qualification=EvidenceQualification.UNQUALIFIED,
        ),
        BenchmarkTask(
            task_id="BM_UNKNOWN_DOMAIN_01",
            dimension=BenchmarkDimension.UNKNOWN_DOMAIN,
            objective="Execute query on esoteric custom database engine 'X-Store'.",
            constraints=["Requires X-Store schema definition"],
            required_knowledge={"x_store_schema": "X-Store uses proto3 syntax with port 9099."},
            difficulty=TaskDifficulty.MEDIUM,
            evaluator=None,
            qualification=EvidenceQualification.UNQUALIFIED,
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

    def run_task_naked(
        self,
        adapter: ModelAdapter,
        task: BenchmarkTask,
        evidence_modality: Optional[EvidenceModality] = None,
    ) -> TaskRunRecord:
        """Runs task with naked model (no context compilation, no deficit loop, no repair)."""
        modality = evidence_modality or getattr(adapter, "evidence_modality", EvidenceModality.STRUCTURAL_MOCK)
        if adapter.provider_name == "mock" and modality == EvidenceModality.EMPIRICAL_MODEL:
            raise ValueError("Mock runs cannot be labeled empirical.")

        start = time.perf_counter()
        req = ModelRequest(
            task_id=task.task_id,
            operation_type="NAKED_EXECUTE",
            objective=f"{task.objective} (Constraints: {task.constraints})",
        )
        resp = adapter.execute(req)
        duration = time.perf_counter() - start

        # Physical evaluation via task-specific authoritative evaluator
        if not task.is_qualified or task.evaluator is None:
            eval_res = CandidateEvaluation(
                candidate_id="none",
                payload=resp.candidate_payload,
                is_valid=False,
                score=0.0,
                failure_classification="VERIFIER_DEFICIT",
                failure_signature="SIG_UNQUALIFIED_NO_TASK_VERIFIER",
                execution_trace="Task is UNQUALIFIED: lacks independent task-specific behavioral verifier.",
            )
            qualification = EvidenceQualification.UNQUALIFIED
        else:
            raw_eval = task.evaluator(resp.candidate_payload)
            qualification = EvidenceQualification.QUALIFIED
            if isinstance(raw_eval, CandidateEvaluation):
                eval_res = raw_eval
            elif isinstance(raw_eval, bool):
                eval_res = CandidateEvaluation(
                    candidate_id="cand_eval",
                    payload=resp.candidate_payload,
                    is_valid=raw_eval,
                    score=1.0 if raw_eval else 0.0,
                    execution_trace="Evaluator returned boolean.",
                )
            else:
                eval_res = CandidateEvaluation(
                    candidate_id="cand_eval",
                    payload=resp.candidate_payload,
                    is_valid=False,
                    score=0.0,
                    failure_classification="VERIFIER_DEFICIT",
                    failure_signature="SIG_UNKNOWN_EVALUATION_FORMAT",
                    execution_trace=f"Unknown evaluation result format: {type(raw_eval)}",
                )

        supplied_context_digest = hashlib.sha256(b"").hexdigest()
        candidate_digest = hashlib.sha256(str(resp.candidate_payload).encode("utf-8")).hexdigest()
        trace_digest = hashlib.sha256((eval_res.execution_trace or "").encode("utf-8")).hexdigest()

        is_success = bool(eval_res.is_valid and qualification == EvidenceQualification.QUALIFIED)
        score = eval_res.score if (qualification == EvidenceQualification.QUALIFIED and eval_res.is_valid) else 0.0
        is_qualified_success = bool(is_success and score > 0.0)

        return TaskRunRecord(
            task_id=task.task_id,
            task_seed=task.seed,
            dimension=task.dimension,
            model_id=adapter.model_id,
            provider=adapter.provider_name,
            execution_mode="NAKED",
            is_success=is_success,
            score=score,
            evidence_modality=modality,
            qualification=qualification,
            is_qualified_success=is_qualified_success,
            supplied_context_digest=supplied_context_digest,
            candidate_digest=candidate_digest,
            verifier_identity=task.verifier_identity,
            verifier_version=task.verifier_version,
            execution_trace_digest=trace_digest,
            observed_outputs=eval_res.observed_outputs if hasattr(eval_res, "observed_outputs") else None,
            attempts=1,
            total_model_calls=1,
            latency_seconds=duration,
            tokens_consumed=resp.tokens_consumed or 200,
            deficits_resolved=0,
            failure_signatures_recorded=[eval_res.failure_signature] if eval_res.failure_signature else [],
        )

    def run_task_ten_shadows(
        self,
        adapter: ModelAdapter,
        task: BenchmarkTask,
        enable_context_compiler: bool = True,
        enable_deficit_protocol: bool = True,
        enable_repair_feedback: bool = True,
        enable_adaptive_search: bool = True,
        evidence_modality: Optional[EvidenceModality] = None,
    ) -> TaskRunRecord:
        """
        Runs task with Ten Shadows competence substrate (Compiled Context + Deficit Protocol + Search & Repair).
        """
        modality = evidence_modality or getattr(adapter, "evidence_modality", EvidenceModality.STRUCTURAL_MOCK)
        if adapter.provider_name == "mock" and modality == EvidenceModality.EMPIRICAL_MODEL:
            raise ValueError("Mock runs cannot be labeled empirical.")

        start = time.perf_counter()
        context_kwargs: Dict[str, Any] = {}
        if enable_context_compiler:
            context_kwargs["constraints"] = task.constraints
            if task.required_procedure:
                context_kwargs["applicable_procedure"] = task.required_procedure
            if task.required_knowledge and task.dimension != BenchmarkDimension.UNKNOWN_DOMAIN:
                context_kwargs["domain_knowledge"] = task.required_knowledge

        # Ensure knowledge base has task knowledge for deficit resolution
        if task.required_knowledge:
            self.resolver.knowledge_base.update(task.required_knowledge)

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

        # Step 2: Candidate Search & Repair Loop with Authoritative Task Evaluator
        difficulty = task.difficulty if enable_adaptive_search else TaskDifficulty.LOW
        max_repairs = 3 if enable_repair_feedback else 1

        if not task.is_qualified or task.evaluator is None:
            best_eval = CandidateEvaluation(
                candidate_id="none",
                payload=resp.candidate_payload if resp else None,
                is_valid=False,
                score=0.0,
                failure_classification="VERIFIER_DEFICIT",
                failure_signature="SIG_UNQUALIFIED_NO_TASK_VERIFIER",
                execution_trace="Task is UNQUALIFIED: lacks independent task-specific behavioral verifier.",
            )
            all_evals = [best_eval]
            search_calls = 0
            qualification = EvidenceQualification.UNQUALIFIED
        else:
            qualification = EvidenceQualification.QUALIFIED
            task_search_engine = SearchEngine(
                context_compiler=self.context_compiler,
                evaluator=task.evaluator,
            )
            best_eval, all_evals, search_calls = task_search_engine.execute_search(
                adapter=adapter,
                base_request=base_req,
                objective=task.objective,
                difficulty=difficulty,
                max_repair_attempts=max_repairs,
                initial_context_kwargs=context_kwargs,
            )

        total_calls += search_calls
        duration = time.perf_counter() - start

        supplied_context_digest = hashlib.sha256(str(context_kwargs).encode("utf-8")).hexdigest()
        candidate_digest = hashlib.sha256(str(best_eval.payload).encode("utf-8")).hexdigest()
        trace_digest = hashlib.sha256((best_eval.execution_trace or "").encode("utf-8")).hexdigest()

        is_success = bool(best_eval.is_valid and qualification == EvidenceQualification.QUALIFIED)
        score = best_eval.score if (qualification == EvidenceQualification.QUALIFIED and best_eval.is_valid) else 0.0
        is_qualified_success = bool(is_success and score > 0.0)

        return TaskRunRecord(
            task_id=task.task_id,
            task_seed=task.seed,
            dimension=task.dimension,
            model_id=adapter.model_id,
            provider=adapter.provider_name,
            execution_mode="FULL_TEN_SHADOWS",
            is_success=is_success,
            score=score,
            evidence_modality=modality,
            qualification=qualification,
            is_qualified_success=is_qualified_success,
            supplied_context_digest=supplied_context_digest,
            candidate_digest=candidate_digest,
            verifier_identity=task.verifier_identity,
            verifier_version=task.verifier_version,
            execution_trace_digest=trace_digest,
            observed_outputs=best_eval.observed_outputs if hasattr(best_eval, "observed_outputs") else None,
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
        evidence_modality: Optional[EvidenceModality] = None,
    ) -> BenchmarkResult:
        """
        Executes full comparative benchmark between Model A (e.g. Strong) and Model B (e.g. Weak).
        Only QUALIFIED tasks enter elasticity numerator and denominator calculations.
        If zero qualified tasks exist or naked_delta == 0, returns NOT_COMPUTABLE for elasticity.
        """
        tasks = corpus or create_canonical_benchmark_corpus()
        records: List[TaskRunRecord] = []

        modality = evidence_modality or getattr(model_a, "evidence_modality", EvidenceModality.STRUCTURAL_MOCK)
        if (model_a.provider_name == "mock" or model_b.provider_name == "mock") and modality == EvidenceModality.EMPIRICAL_MODEL:
            raise ValueError("Mock runs cannot be labeled empirical.")

        qualified_tasks = [t for t in tasks if t.is_qualified]
        unqualified_tasks = [t for t in tasks if not t.is_qualified]
        qualified_task_ids = [t.task_id for t in qualified_tasks]
        unqualified_task_ids = [t.task_id for t in unqualified_tasks]

        naked_a_scores: List[float] = []
        naked_b_scores: List[float] = []
        ts_a_scores: List[float] = []
        ts_b_scores: List[float] = []

        attempts_a: List[int] = []
        attempts_b: List[int] = []
        latency_a: List[float] = []
        latency_b: List[float] = []

        for task in tasks:
            rec_na = self.run_task_naked(model_a, task, evidence_modality=modality)
            rec_nb = self.run_task_naked(model_b, task, evidence_modality=modality)
            records.extend([rec_na, rec_nb])

            rec_tsa = self.run_task_ten_shadows(model_a, task, evidence_modality=modality)
            rec_tsb = self.run_task_ten_shadows(model_b, task, evidence_modality=modality)
            records.extend([rec_tsa, rec_tsb])

            # ONLY qualified tasks enter elasticity calculations!
            if task.is_qualified:
                naked_a_scores.append(rec_na.score)
                naked_b_scores.append(rec_nb.score)
                ts_a_scores.append(rec_tsa.score)
                ts_b_scores.append(rec_tsb.score)

                attempts_a.append(rec_tsa.attempts)
                attempts_b.append(rec_tsb.attempts)
                latency_a.append(rec_tsa.latency_seconds)
                latency_b.append(rec_tsb.latency_seconds)

        if not qualified_tasks:
            return BenchmarkResult(
                model_a_id=model_a.model_id,
                model_b_id=model_b.model_id,
                naked_score_a=0.0,
                naked_score_b=0.0,
                ten_shadows_score_a=0.0,
                ten_shadows_score_b=0.0,
                model_elasticity="NOT_COMPUTABLE",
                attempt_elasticity="NOT_COMPUTABLE",
                latency_elasticity="NOT_COMPUTABLE",
                qualified_task_ids=[],
                unqualified_task_ids=unqualified_task_ids,
                evidence_modality=modality,
                records=records,
            )

        mean_na = sum(naked_a_scores) / len(naked_a_scores)
        mean_nb = sum(naked_b_scores) / len(naked_b_scores)
        mean_tsa = sum(ts_a_scores) / len(ts_a_scores)
        mean_tsb = sum(ts_b_scores) / len(ts_b_scores)

        naked_delta = abs(mean_na - mean_nb)
        ts_delta = abs(mean_tsa - mean_tsb)

        if naked_delta <= 1e-6:
            model_elasticity: Union[float, str] = "NOT_COMPUTABLE"
        else:
            model_elasticity = round(ts_delta / naked_delta, 6)

        avg_att_a = sum(attempts_a) / len(attempts_a) if attempts_a else 0.0
        avg_att_b = sum(attempts_b) / len(attempts_b) if attempts_b else 0.0
        if avg_att_a <= 1e-6:
            attempt_elasticity: Union[float, str] = "NOT_COMPUTABLE"
        else:
            attempt_elasticity = round(avg_att_b / avg_att_a, 4)

        avg_lat_a = sum(latency_a) / len(latency_a) if latency_a else 0.0
        avg_lat_b = sum(latency_b) / len(latency_b) if latency_b else 0.0
        if avg_lat_a <= 1e-6:
            latency_elasticity: Union[float, str] = "NOT_COMPUTABLE"
        else:
            latency_elasticity = round(avg_lat_b / avg_lat_a, 4)

        return BenchmarkResult(
            model_a_id=model_a.model_id,
            model_b_id=model_b.model_id,
            naked_score_a=round(mean_na, 4),
            naked_score_b=round(mean_nb, 4),
            ten_shadows_score_a=round(mean_tsa, 4),
            ten_shadows_score_b=round(mean_tsb, 4),
            model_elasticity=model_elasticity,
            attempt_elasticity=attempt_elasticity,
            latency_elasticity=latency_elasticity,
            qualified_task_ids=qualified_task_ids,
            unqualified_task_ids=unqualified_task_ids,
            evidence_modality=modality,
            records=records,
        )
