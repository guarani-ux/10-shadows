"""
forge/core/adequacy.py
Upstream Intent Coverage & Objective Adequacy Evaluator.

Prevents distorted, incomplete, or ungrounded CanonicalObjectives from producing
incorrect execution graphs. Establishes machine-verifiable requirement traceability
from raw human input into CanonicalObjective without delegating judgment to an LLM.
"""

import hashlib
import re
from typing import Any, Dict, List, Optional

from forge.core.substrate import (
    CanonicalRequirement,
    ObjectiveAdequacyContract,
    ObjectiveAdequacyState,
    RawClause,
    RequirementDisposition,
    RequirementOrigin,
    RequirementTrace,
)


class RawClauseTokenizer:
    """
    Deterministic lexical and syntactic clause partitioner for raw human intent.
    Identifies atomic requirements, constraints, deliverable requests, and prohibitions.
    """

    MODAL_PATTERNS = [
        r"(?:must not|cannot|never|do not|prohibit)\s+[^.,;\n]+",
        r"(?:must|shall|should|require|need to|ensure)\s+[^.,;\n]+",
        r"(?:only|strictly)\s+[^.,;\n]+",
    ]

    @classmethod
    def tokenize(cls, raw_intent: str) -> List[RawClause]:
        clauses: List[RawClause] = []
        cleaned = raw_intent.strip()
        if not cleaned:
            return clauses

        # 1. Split on structural line breaks / bullets
        lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
        for line_idx, line in enumerate(lines):
            # Split sentence boundaries and compound action conjunctions
            sentences = [
                s.strip()
                for s in re.split(
                    r"[.;]+|\s+and\s+(?=(?:validate|decompose|extract|calculate|write|detect|commit|check|verify|run))",
                    line,
                    flags=re.IGNORECASE
                )
                if s.strip()
            ]
            for s_idx, s in enumerate(sentences):
                # Detect constraints / deliverables
                s_lower = s.lower()
                is_constraint = any(k in s_lower for k in ["must", "cannot", "never", "only", "strictly", "no ", "without", "budget", "timeout"])
                is_deliverable = any(k in s_lower for k in ["create", "build", "generate", "return", "output", "calculate", "deliverable", "script", "file", "csv", "json"])

                clause_id = f"c_{line_idx}_{s_idx}_{hashlib.sha256(s.encode('utf-8')).hexdigest()[:6]}"
                clauses.append(RawClause(
                    clause_id=clause_id,
                    text=s,
                    is_constraint=is_constraint,
                    is_deliverable=is_deliverable,
                ))

        return clauses


class IntentCoverageEvaluator:
    """
    Evaluates whether a proposed CanonicalObjective faithfully, completely, and
    non-hallucinatively captures the raw human intent.
    """

    def __init__(self, capability_registry: Optional[Any] = None):
        self.capability_registry = capability_registry

    def evaluate_adequacy(
        self,
        raw_intent: str,
        canonical_requirements: List[CanonicalRequirement],
        proposed_traces: List[RequirementTrace],
        explicit_unknowns: Optional[List[Dict[str, Any]]] = None,
    ) -> ObjectiveAdequacyContract:
        raw_clauses = RawClauseTokenizer.tokenize(raw_intent)
        explicit_unknowns = explicit_unknowns or []

        trace_map = {t.raw_clause_id: t for t in proposed_traces}
        unaccounted_drops: List[str] = []
        unauthorized_assumptions: List[str] = []
        missing_domain_capabilities: List[str] = []

        # Invariant 1: Bijective Raw Clause Coverage (Zero Silent Drops)
        for clause in raw_clauses:
            trace = trace_map.get(clause.clause_id)
            if not trace or not trace.disposition:
                # Missing disposition on raw clause
                unaccounted_drops.append(clause.text)

        # Invariant 2: Semantic Addition Control (No Authoritative Hallucinations)
        for req in canonical_requirements:
            if req.origin == RequirementOrigin.ASSUMED:
                # Check if covered by explicit human gate in unknowns
                has_human_gate = any(
                    u.get("requires_human_gate", False) and req.description in u.get("description", "")
                    for u in explicit_unknowns
                )
                if not has_human_gate:
                    unauthorized_assumptions.append(req.description)

            elif req.origin == RequirementOrigin.DOMAIN_DERIVED:
                # Check if Forge possesses verified capability for domain requirement
                domain_cap = req.required_domain_capability
                if domain_cap:
                    has_cap = False
                    if self.capability_registry:
                        cap = self.capability_registry.get_capability(domain_cap)
                        if cap and cap.is_authorized_for_execution:
                            has_cap = True
                    if not has_cap:
                        missing_domain_capabilities.append(f"{req.description} (Requires: {domain_cap})")

        # Invariant 3: Material Ambiguity Preservation
        has_ungated_ambiguity = False
        for trace in proposed_traces:
            if trace.disposition == RequirementDisposition.AMBIGUOUS:
                # Ambiguity must be registered in explicit_unknowns with requires_human_gate=True
                covered = any(
                    u.get("requires_human_gate", False) and trace.raw_text in u.get("description", "")
                    for u in explicit_unknowns
                )
                if not covered:
                    has_ungated_ambiguity = True

        # State Determination
        if unaccounted_drops:
            state = ObjectiveAdequacyState.SOURCE_UNCOVERED
        elif missing_domain_capabilities:
            state = ObjectiveAdequacyState.DOMAIN_REQUIREMENTS_UNVERIFIED
        elif unauthorized_assumptions or has_ungated_ambiguity:
            state = ObjectiveAdequacyState.SOURCE_AMBIGUOUS
        else:
            state = ObjectiveAdequacyState.ADEQUATE_FOR_EXECUTION

        return ObjectiveAdequacyContract(
            objective_id=f"obj_{hashlib.sha256(raw_intent.encode('utf-8')).hexdigest()[:8]}",
            adequacy_state=state,
            raw_clauses=raw_clauses,
            traces=proposed_traces,
            unaccounted_drops=unaccounted_drops,
            unauthorized_assumptions=unauthorized_assumptions,
            missing_domain_capabilities=missing_domain_capabilities,
            details={
                "raw_clause_count": len(raw_clauses),
                "mapped_clause_count": len(proposed_traces) - len(unaccounted_drops),
                "canonical_requirement_count": len(canonical_requirements),
            },
        )
