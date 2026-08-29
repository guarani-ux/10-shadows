"""
loop_engine/constitution/sufficiency.py
Law 6 Objective Sufficiency Engine with Live JTMS Invalidation Integration.

Enforces:
- Law 6 Objective Sufficiency is mathematically derived from authoritative evidence.
- Direct query of live JTMS / RelationalGraphStore: Retracted or falsified evidence nodes
  immediately invalidate claim qualification and reopen dependent requirements.
- 0-requirement and dropped-requirement exploits fail closed.
- Disjunctive bypasses cannot skip unresolved mandatory blocking requirements.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from typing import Any, Dict, List, Optional, Set, Tuple

from forge.core.substrate import CanonicalRequirement, compute_digest
from loop_engine.constitution.evidence import (
    ApplicabilityDimension,
    EpistemicClaim,
    EpistemicDimension,
    QualifiedEvidence,
    RelationalEvidenceEvaluator,
)
from loop_engine.constitution.lifecycle import (
    SemanticQualificationStatus,
    VersionedObjectiveSpecification,
)
from loop_engine.relational.graph_db import RelationalGraphStore
from loop_engine.relational.schema import EpistemicStatus


class CompositionRule(str, Enum):
    MANDATORY_CONJUNCTION = "MANDATORY_CONJUNCTION"  # All mandatory requirements must be satisfied (AND)
    AUTHORITATIVE_ALTERNATIVES = "AUTHORITATIVE_ALTERNATIVES"  # Explicit disjunction permitted by objective semantics (OR)
    CONDITIONAL = "CONDITIONAL"  # Requires prerequisite satisfaction before branch is active
    OPTIONAL_PREFERENCE = "OPTIONAL_PREFERENCE"  # Best-effort preference; does not block completion


@dataclass
class ObjectiveSufficiencyProof:
    """
    Cryptographic proof of Law 6 Objective Sufficiency.
    """
    objective_id: str
    objective_version: int
    is_satisfied: bool
    satisfied_requirement_ids: List[str]
    unresolved_mandatory_ids: List[str]
    falsified_mandatory_ids: List[str]
    composition_rule: CompositionRule
    proof_digest: str
    evaluated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class Law6SufficiencyEngine:
    """
    Evaluates whether an objective is legitimately accomplished under Law 6.
    Integrates directly with live JTMS relational store for real-time invalidation.
    """

    @staticmethod
    def evaluate_specification(
        spec: VersionedObjectiveSpecification,
        claims: Dict[str, EpistemicClaim],
        evidence_by_claim: Dict[str, List[QualifiedEvidence]],
        active_candidate_sha: Optional[str] = None,
        active_environment_fingerprint: Optional[str] = None,
        composition_rule: CompositionRule = CompositionRule.MANDATORY_CONJUNCTION,
        alternative_ids: Optional[List[str]] = None,
        jtms_store: Optional[RelationalGraphStore] = None,
    ) -> ObjectiveSufficiencyProof:
        """
        Evaluates the objective specification against qualified epistemic claims,
        evidence, and live JTMS dependency state.
        """
        satisfied_ids: List[str] = []
        unresolved_mandatory: List[str] = []
        falsified_mandatory: List[str] = []

        # 1. Check specification qualification status
        if spec.qualification_status != SemanticQualificationStatus.QUALIFIED:
            unresolved_mandatory.append(f"UNQUALIFIED_SPECIFICATION_{spec.qualification_status.value}")
            return Law6SufficiencyEngine._build_proof(
                spec, False, [], unresolved_mandatory, [], composition_rule
            )

        # 2. Prevent 0-requirement false-success exploit on non-trivial objectives
        if not spec.requirements:
            if len(spec.canonical_intent.strip()) > 0:
                unresolved_mandatory.append("INSUFFICIENT_REQUIREMENTS_EMPTY_SET")
                return Law6SufficiencyEngine._build_proof(
                    spec, False, [], unresolved_mandatory, [], composition_rule
                )

        # 3. Evaluate each canonical requirement
        for req in spec.requirements:
            claim = claims.get(req.requirement_id)
            if not claim:
                if req.is_blocking:
                    unresolved_mandatory.append(req.requirement_id)
                continue

            # JTMS Live Invalidation Check
            if jtms_store:
                node = jtms_store.get_node(req.requirement_id)
                if node and node.epistemic_status in (EpistemicStatus.INVALIDATED, EpistemicStatus.CONTESTED, EpistemicStatus.PROPOSED):
                    if req.is_blocking:
                        unresolved_mandatory.append(req.requirement_id)
                    continue

            ev_list = evidence_by_claim.get(claim.claim_id, [])

            # Filter evidence against live JTMS store
            if jtms_store:
                filtered_ev: List[QualifiedEvidence] = []
                for ev in ev_list:
                    ev_node = jtms_store.get_node(ev.evidence_id)
                    if ev_node and ev_node.epistemic_status in (EpistemicStatus.INVALIDATED, EpistemicStatus.CONTESTED, EpistemicStatus.PROPOSED):
                        continue
                    filtered_ev.append(ev)
                ev_list = filtered_ev

            ep_status, app_status, _note = RelationalEvidenceEvaluator.evaluate_claim(
                claim=claim,
                evidence_list=ev_list,
                active_candidate_sha=active_candidate_sha,
                active_environment_fingerprint=active_environment_fingerprint,
            )

            if ep_status == EpistemicDimension.SUPPORTED and app_status == ApplicabilityDimension.APPLICABLE:
                satisfied_ids.append(req.requirement_id)
            elif ep_status in (EpistemicDimension.CONTRADICTED, EpistemicDimension.UNSUPPORTED):
                if req.is_blocking:
                    if ep_status == EpistemicDimension.CONTRADICTED:
                        falsified_mandatory.append(req.requirement_id)
                    else:
                        unresolved_mandatory.append(req.requirement_id)
            else:
                if req.is_blocking:
                    unresolved_mandatory.append(req.requirement_id)

        # 4. Evaluate composition rule
        if falsified_mandatory:
            is_satisfied = False
        else:
            if composition_rule == CompositionRule.MANDATORY_CONJUNCTION:
                is_satisfied = len(unresolved_mandatory) == 0 and len(satisfied_ids) > 0
            elif composition_rule == CompositionRule.AUTHORITATIVE_ALTERNATIVES:
                target_alt_ids = set(alternative_ids or [])
                has_alternative_satisfied = bool(set(satisfied_ids).intersection(target_alt_ids))
                other_unresolved = [uid for uid in unresolved_mandatory if uid not in target_alt_ids]
                is_satisfied = has_alternative_satisfied and len(other_unresolved) == 0
            else:
                is_satisfied = len(unresolved_mandatory) == 0 and len(satisfied_ids) > 0

        return Law6SufficiencyEngine._build_proof(
            spec, is_satisfied, satisfied_ids, unresolved_mandatory, falsified_mandatory, composition_rule
        )

    @staticmethod
    def _build_proof(
        spec: VersionedObjectiveSpecification,
        is_satisfied: bool,
        satisfied_ids: List[str],
        unresolved: List[str],
        falsified: List[str],
        composition: CompositionRule,
    ) -> ObjectiveSufficiencyProof:
        digest = compute_digest({
            "spec_hash": spec.specification_hash,
            "satisfied": sorted(satisfied_ids),
            "unresolved": sorted(unresolved),
            "falsified": sorted(falsified),
            "composition": composition.value,
            "is_satisfied": is_satisfied,
        })
        return ObjectiveSufficiencyProof(
            objective_id=spec.objective_id,
            objective_version=spec.version,
            is_satisfied=is_satisfied,
            satisfied_requirement_ids=sorted(satisfied_ids),
            unresolved_mandatory_ids=sorted(unresolved),
            falsified_mandatory_ids=sorted(falsified),
            composition_rule=composition,
            proof_digest=digest,
        )
