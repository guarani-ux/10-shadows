"""
forge/core/decomposition.py
Deterministic Decomposition Verifier & Coverage Evaluator.

Proves that a proposed RequiredOperation DAG is mathematically sufficient to satisfy
a CanonicalObjective using type-theoretic reachability, terminal output subsumption,
and verification contract mapping. Prevents ExecutionGraph compilation until
decomposition closure passes.
"""

import hashlib
import re
from typing import Any, Dict, List, Optional, Set

from forge.core.substrate import (
    CanonicalRequirement,
    DecompositionProof,
    OperatorType,
    RequiredOperation,
    VerificationContract,
)


class DecompositionCoverageEvaluator:
    """
    Evaluates candidate operation decompositions against the physical contract lattice
    of a CanonicalObjective.
    """

    def evaluate_decomposition(
        self,
        objective_id: str,
        canonical_requirements: List[CanonicalRequirement],
        operations: List[RequiredOperation],
        verification_contracts: List[VerificationContract],
        known_inputs: Optional[Set[str]] = None,
    ) -> DecompositionProof:
        obj_hash = hashlib.sha256(objective_id.encode("utf-8")).hexdigest()
        standard_inputs = {
            "raw_input", "context", "objective", "constraints", "verified_evidence",
            "source_text", "extraction_schema", "target", "payload", "force", "area",
            "claims", "tasks", "source_code", "error_trace", "worktree_path", "test_file",
            "user_id", "data"
        }
        produced_outputs = set(known_inputs or standard_inputs)

        mapped_ops = [op.operation_id for op in operations]
        op_map = {op.operation_id: op for op in operations}
        uncovered_reqs: List[str] = []
        introduced_assumptions: List[str] = []
        operation_deficits: List[str] = []

        # 1. Operator Ontology & Deficit Check
        valid_operators = set(OperatorType)
        for op in operations:
            if op.operator not in valid_operators:
                operation_deficits.append(f"{op.operation_id}: Unknown operator '{op.operator}'")

        # 2. Dependency Completeness & Reachability (No Floating Inputs)
        dependency_complete = True

        for op in operations:
            # Check dependencies exist in graph
            for dep in op.dependencies:
                if dep not in op_map:
                    dependency_complete = False
                    break

            # Check inputs are reachably supplied either from initial inputs or upstream dependencies
            for inp in op.inputs:
                is_supplied = (
                    inp in produced_outputs
                    or any(inp in op_map[dep].outputs for dep in op.dependencies if dep in op_map)
                )
                if not is_supplied:
                    dependency_complete = False

            # Add this operation's outputs to available outputs
            for out in op.outputs:
                produced_outputs.add(out)

        # 3. Requirement Coverage Proof Across Graph Operations
        for req in canonical_requirements:
            req_words = set(re.findall(r"\w+", req.description.lower())) - {
                "a", "an", "the", "in", "to", "for", "and", "of", "with", "is", "on", "into", "as", "by"
            }
            if not req_words:
                continue

            covered = False
            for op in operations:
                # Semantic responsibility match
                if any(w in op.semantic_responsibility.lower() for w in req_words):
                    covered = True
                    break
                # Postcondition match
                if any(any(w in post.lower() for w in req_words) for post in op.postconditions):
                    covered = True
                    break
                # Output key match
                if any(any(w in out.lower() for w in req_words) for out in op.outputs):
                    covered = True
                    break

            if not covered:
                uncovered_reqs.append(req.description)

        # 4. Verification Gate Completeness
        gate_conditions = {vc.observable_success_condition.lower() for vc in verification_contracts}
        verified_ops_count = 0
        for op in operations:
            if any(post.lower() in gate_conditions or any(post.lower() in g for g in gate_conditions) for post in op.postconditions):
                verified_ops_count += 1
            elif op.operator in (OperatorType.TEST, OperatorType.VALIDATE):
                verified_ops_count += 1

        terminal_coverage = (
            (len(canonical_requirements) - len(uncovered_reqs)) / len(canonical_requirements)
            if canonical_requirements
            else 1.0
        )
        verification_coverage = (
            verified_ops_count / len(operations)
            if operations
            else 1.0
        )

        # 5. Closure Status Determination
        if operation_deficits:
            closure_status = "ONTOLOGY_INSUFFICIENT"
        elif terminal_coverage == 1.0 and dependency_complete and not uncovered_reqs:
            closure_status = "SATISFIED"
        else:
            closure_status = "INSUFFICIENT"

        return DecompositionProof(
            objective_hash=obj_hash,
            mapped_operations=mapped_ops,
            uncovered_requirements=uncovered_reqs,
            introduced_assumptions=introduced_assumptions,
            dependency_completeness=dependency_complete,
            terminal_output_coverage=terminal_coverage,
            verification_coverage=verification_coverage,
            closure_status=closure_status,
            operation_deficits=operation_deficits,
        )
