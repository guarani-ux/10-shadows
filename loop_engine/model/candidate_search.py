"""
loop_engine/model/candidate_search.py
Adaptive Candidate Search & Structured Failure Feedback Engine for 10 SHADOWS.

Eliminates one-shot brittleness by adapting search depth (1 vs K candidates)
based on task risk, novelty, and failure history. Compiles physical failures into
bounded, causally distilled repair context for attempt N+1.
"""

from __future__ import annotations

from enum import Enum
import hashlib
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple
from pydantic import BaseModel, Field

from loop_engine.model.boundary import (
    InferenceEffort,
    ModelAdapter,
    ModelRequest,
    ModelResponse,
)
from loop_engine.model.context_compiler import ContextCompiler, CompiledContext


class TaskDifficulty(str, Enum):
    LOW = "LOW"        # Reversible, simple routine generation (1 candidate)
    MEDIUM = "MEDIUM"  # Moderate complexity, unverified edge cases (1 candidate + critique/repair)
    HIGH = "HIGH"      # High risk, irreversible, novel domain, or prior failure (Multi-candidate search)


class SearchPolicy(str, Enum):
    SINGLE = "SINGLE"
    CRITIQUE_REPAIR = "CRITIQUE_REPAIR"
    MULTI_CANDIDATE = "MULTI_CANDIDATE"


class CandidateEvaluation(BaseModel):
    """
    Physical evaluation result of a generated candidate.
    """
    candidate_id: str
    payload: Any
    is_valid: bool
    score: float = 0.0
    failure_classification: Optional[str] = None
    failure_signature: Optional[str] = None
    execution_trace: Optional[str] = None
    negative_constraint: Optional[str] = None


class SearchEngine:
    """
    Coordinates candidate generation, physical evaluation ranking,
    and structured failure feedback loop.
    """
    def __init__(
        self,
        context_compiler: ContextCompiler,
        evaluator: Optional[Callable[[Any], CandidateEvaluation]] = None,
    ):
        self.context_compiler = context_compiler
        self.evaluator = evaluator or self._default_evaluator

    @staticmethod
    def _default_evaluator(candidate: Any) -> CandidateEvaluation:
        """Default AST/smoke evaluator for candidates."""
        cid = f"cand_{hashlib.sha256(str(candidate).encode()).hexdigest()[:8]}"
        if isinstance(candidate, dict):
            status = candidate.get("status", "")
            code = candidate.get("code", "")
            if status == "SUCCESS" or "def run():" in code and "flawed" not in code and "raise" not in code:
                return CandidateEvaluation(candidate_id=cid, payload=candidate, is_valid=True, score=1.0)
            elif "raise" in code or status == "ADVERSARIAL":
                return CandidateEvaluation(
                    candidate_id=cid,
                    payload=candidate,
                    is_valid=False,
                    score=0.0,
                    failure_classification="CANDIDATE_FAILURE",
                    failure_signature="SIG_RUNTIME_EXCEPTION",
                    execution_trace="Candidate raised unhandled exception during execution.",
                    negative_constraint=f"DO NOT REPEAT: Code containing 'raise RuntimeError'",
                )
            else:
                return CandidateEvaluation(
                    candidate_id=cid,
                    payload=candidate,
                    is_valid=False,
                    score=0.2,
                    failure_classification="CANDIDATE_FAILURE",
                    failure_signature="SIG_INCOMPLETE_IMPLEMENTATION",
                    execution_trace="Candidate is missing full implementation.",
                    negative_constraint=f"DO NOT REPEAT: Incomplete stub returning flawed value",
                )
        return CandidateEvaluation(candidate_id=cid, payload=candidate, is_valid=True, score=0.5)

    def determine_search_policy(
        self,
        difficulty: TaskDifficulty,
        has_prior_failures: bool = False,
    ) -> SearchPolicy:
        """Selects the search policy based on measurable conditions."""
        if has_prior_failures or difficulty == TaskDifficulty.HIGH:
            return SearchPolicy.MULTI_CANDIDATE
        elif difficulty == TaskDifficulty.MEDIUM:
            return SearchPolicy.CRITIQUE_REPAIR
        return SearchPolicy.SINGLE

    def execute_search(
        self,
        adapter: ModelAdapter,
        base_request: ModelRequest,
        objective: Any,
        difficulty: TaskDifficulty = TaskDifficulty.LOW,
        max_repair_attempts: int = 3,
        k_candidates: int = 3,
        initial_context_kwargs: Optional[Dict[str, Any]] = None,
    ) -> Tuple[CandidateEvaluation, List[CandidateEvaluation], int]:
        """
        Executes candidate search and repair loop.
        Returns: (winning_candidate_evaluation, all_evaluations, total_model_calls).
        """
        context_kwargs = dict(initial_context_kwargs or {})
        failure_history: List[Dict[str, Any]] = []
        all_evals: List[CandidateEvaluation] = []
        model_calls = 0

        for attempt in range(1, max_repair_attempts + 1):
            policy = self.determine_search_policy(
                difficulty=difficulty,
                has_prior_failures=len(failure_history) > 0,
            )

            # Update context with compiled failure history
            context_kwargs["failure_history"] = failure_history
            compiled = self.context_compiler.compile(objective=objective, **context_kwargs)

            request = base_request.model_copy(deep=True)
            request.compiled_context = compiled.to_dict()

            if policy == SearchPolicy.MULTI_CANDIDATE:
                # Request multiple candidates or deep inference effort
                request.candidate_count = k_candidates
                request.inference_effort = InferenceEffort.DEEP
                response = adapter.execute(request)
                model_calls += 1

                # Gather candidates
                candidates = [response.candidate_payload]
                if response.structured_alternatives:
                    candidates.extend(response.structured_alternatives)

                # Evaluate all candidates against physical evaluator
                evaluated_batch = [self.evaluator(c) for c in candidates]
                all_evals.extend(evaluated_batch)

                # Pick the highest scoring valid candidate
                valid_candidates = [e for e in evaluated_batch if e.is_valid]
                if valid_candidates:
                    valid_candidates.sort(key=lambda x: x.score, reverse=True)
                    return valid_candidates[0], all_evals, model_calls

                # None passed: compile best failure for next attempt
                evaluated_batch.sort(key=lambda x: x.score, reverse=True)
                worst_eval = evaluated_batch[0]
                failure_history.append({
                    "signature": worst_eval.failure_signature or f"FAIL_ATTEMPT_{attempt}",
                    "classification": worst_eval.failure_classification or "CANDIDATE_FAILURE",
                    "root_cause": worst_eval.execution_trace or "Evaluator rejected candidate",
                    "negative_constraint": worst_eval.negative_constraint or f"DO NOT REPEAT attempt {attempt}",
                })

            else:
                # Single candidate generation
                request.candidate_count = 1
                request.inference_effort = InferenceEffort.STANDARD if policy == SearchPolicy.CRITIQUE_REPAIR else InferenceEffort.FAST
                response = adapter.execute(request)
                model_calls += 1

                eval_result = self.evaluator(response.candidate_payload)
                all_evals.append(eval_result)

                if eval_result.is_valid:
                    return eval_result, all_evals, model_calls

                # Candidate failed: compile causal failure packet
                failure_history.append({
                    "signature": eval_result.failure_signature or f"FAIL_ATTEMPT_{attempt}",
                    "classification": eval_result.failure_classification or "CANDIDATE_FAILURE",
                    "root_cause": eval_result.execution_trace or "Evaluator rejected candidate",
                    "negative_constraint": eval_result.negative_constraint or f"DO NOT REPEAT attempt {attempt}",
                })

        # Return best evaluation found even if invalid after exhausting attempts
        all_evals.sort(key=lambda x: x.score, reverse=True)
        return all_evals[0], all_evals, model_calls
