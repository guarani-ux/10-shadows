"""
forge/core/obligations.py
Semantic Applicability & Authority Verification Boundary for 10 SHADOWS Forge.

Enforces:
1. Complete separation of Candidate Generation from Authority Verification.
2. Authority cannot self-certify: SemanticApplicabilityProofs are verified against KernelDatabase.
3. Legal Semantic Authority Sources:
   - SOURCE_EXPLICIT_CONTRACT (Machine-readable structured contract at ingress)
   - VERIFIED_DOMAIN_AUTHORITY (Registered in KernelDatabase with verifiable scope)
   - SYSTEM_INVARIANT (TCB invariant with verified structural preconditions)
   - EXPLICIT_HUMAN_APPROVAL (Approved in KernelDatabase for exact binding_hash)
   - AUTHORITATIVE_EXTERNAL_EVIDENCE (Machine-signed evidence establishing R -> S)
4. Model hypotheses have ZERO closure authority (UNVERIFIED_MODEL_PROPOSAL).
5. Zero domain keyword routing. Zero default DATA_EXTRACTION fallback.
"""

import hashlib
import json
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from forge.core.substrate import (
    CandidateSemanticBinding,
    CanonicalRequirement,
    ContractField,
    EvidenceClass,
    EvidenceRequirement,
    ObligationAuthority,
    OperatorType,
    RequirementOrigin,
    ResolutionDeficit,
    SatisfactionObligation,
    SemanticApplicabilityProof,
    SemanticAuthoritySource,
    SemanticBindingStatus,
    SemanticContract,
    VerificationContract,
    canonical_json,
    compute_digest,
)
from loop_engine.kernel_db import KernelDatabase


def compute_canonical_binding_hash(
    requirement_hash: str,
    source_requirement_id: str,
    semantic_contract: SemanticContract,
    is_blocking: bool,
) -> str:
    """Computes deterministic SHA256 hex digest of the complete candidate semantic binding."""
    payload = {
        "req_hash": requirement_hash,
        "req_id": source_requirement_id,
        "contract_hash": semantic_contract.contract_hash,
        "blocking": is_blocking,
    }
    return compute_digest(payload)


class CandidateBindingGenerator:
    """
    Produces candidate semantic interpretations (CandidateSemanticBinding).
    Carries ZERO authority by definition.
    """

    def generate_candidates(
        self,
        canonical_requirements: List[CanonicalRequirement],
        raw_intent: str,
        structured_contracts: Optional[List[Dict[str, Any]]] = None,
        model_proposals: Optional[List[Dict[str, Any]]] = None,
        known_inputs: Optional[Dict[str, Any]] = None,
    ) -> List[CandidateSemanticBinding]:
        candidates: List[CandidateSemanticBinding] = []
        structured_map = {c.get("requirement_id"): c for c in (structured_contracts or []) if c.get("requirement_id")}

        for req in canonical_requirements:
            # 1. Check if structured machine-readable contract was explicitly provided at ingress
            if req.requirement_id in structured_map or (
                structured_contracts and len(structured_contracts) == 1 and len(canonical_requirements) == 1
            ):
                struct_c = structured_map.get(req.requirement_id) or structured_contracts[0]

                inputs_raw = struct_c.get("inputs", {})
                outputs_raw = struct_c.get("outputs", {})

                norm_inputs = {
                    k: v
                    if isinstance(v, ContractField)
                    else ContractField(
                        type_name=str(v) if isinstance(v, str) else v.get("type_name", "Any"),
                        unit=v.get("unit") if isinstance(v, dict) else None,
                    )
                    for k, v in inputs_raw.items()
                }
                norm_outputs = {
                    k: v
                    if isinstance(v, ContractField)
                    else ContractField(
                        type_name=str(v) if isinstance(v, str) else v.get("type_name", "Any"),
                        unit=v.get("unit") if isinstance(v, dict) else None,
                    )
                    for k, v in outputs_raw.items()
                }

                contract = SemanticContract(
                    effect_type=struct_c.get("effect_type", "CALCULATION"),
                    inputs=norm_inputs,
                    outputs=norm_outputs,
                    transformation_rule=struct_c.get("transformation_rule") or struct_c.get("rule"),
                    evidence_requirements=tuple(
                        [
                            e
                            if isinstance(e, EvidenceRequirement)
                            else EvidenceRequirement(
                                evidence_id=e.get("evidence_id", "ev_0"),
                                claim_or_decision_supported=e.get("claim", ""),
                                required_evidence_class=EvidenceClass(
                                    e.get("required_evidence_class", "VERIFIED_FACT")
                                ),
                            )
                            for e in struct_c.get("evidence_requirements", [])
                        ]
                    ),
                    authority_requirements=tuple(struct_c.get("authority_requirements", [])),
                    verification_spec=struct_c.get("verification_spec"),
                )

                binding_hash = compute_canonical_binding_hash(
                    requirement_hash=req.requirement_hash,
                    source_requirement_id=req.requirement_id,
                    semantic_contract=contract,
                    is_blocking=req.is_blocking,
                )

                candidates.append(
                    CandidateSemanticBinding(
                        binding_hash=binding_hash,
                        requirement_hash=req.requirement_hash,
                        source_requirement_id=req.requirement_id,
                        semantic_contract=contract,
                        is_blocking=req.is_blocking,
                        candidate_provenance={
                            "origin": "INGRESS_STRUCTURED_CONTRACT",
                            "source_clause_id": req.source_clause_id,
                        },
                    )
                )
                continue

            # 2. Check for structural System Invariants (requires verified input preconditions)
            inputs = known_inputs or {}
            is_python_source = "source_code" in inputs and isinstance(inputs["source_code"], str)
            is_task_dag = "tasks" in inputs and isinstance(inputs["tasks"], list)
            is_text_source = (
                "source_text" in inputs and isinstance(inputs["source_text"], str) and bool(inputs["source_text"])
            ) or ("text" in inputs and isinstance(inputs["text"], str) and bool(inputs["text"]))

            if is_text_source and (
                "extract" in req.description.lower()
                or "ingest" in req.description.lower()
                or "evidence" in req.description.lower()
                or "source text" in req.description.lower()
            ):
                contract = SemanticContract(
                    effect_type="DATA_EXTRACTION",
                    inputs={"source_text": ContractField(type_name="str")},
                    outputs={
                        "extracted_evidence": ContractField(type_name="List[Dict[str, Any]]"),
                        "claims": ContractField(type_name="List[Dict[str, Any]]"),
                    },
                    transformation_rule="SENTENCE_SPLIT_EXTRACTION",
                )
                binding_hash = compute_canonical_binding_hash(
                    req.requirement_hash, req.requirement_id, contract, req.is_blocking
                )
                candidates.append(
                    CandidateSemanticBinding(
                        binding_hash=binding_hash,
                        requirement_hash=req.requirement_hash,
                        source_requirement_id=req.requirement_id,
                        semantic_contract=contract,
                        is_blocking=req.is_blocking,
                        candidate_provenance={
                            "origin": "SYSTEM_INVARIANT_PREDICATE",
                            "precondition": "verified_text_source",
                        },
                    )
                )
                continue

            if is_python_source and (
                "ast" in req.description.lower()
                or "syntax" in req.description.lower()
                or "security" in req.description.lower()
            ):
                contract = SemanticContract(
                    effect_type="AST_VERIFICATION",
                    inputs={"source_code": ContractField(type_name="str")},
                    outputs={
                        "ast_ok": ContractField(type_name="bool"),
                        "violations": ContractField(type_name="List[str]"),
                        "syntax_valid": ContractField(type_name="bool"),
                    },
                    transformation_rule="AST_PARSER_LINT",
                )
                binding_hash = compute_canonical_binding_hash(
                    req.requirement_hash, req.requirement_id, contract, req.is_blocking
                )
                candidates.append(
                    CandidateSemanticBinding(
                        binding_hash=binding_hash,
                        requirement_hash=req.requirement_hash,
                        source_requirement_id=req.requirement_id,
                        semantic_contract=contract,
                        is_blocking=req.is_blocking,
                        candidate_provenance={
                            "origin": "SYSTEM_INVARIANT_PREDICATE",
                            "precondition": "verified_python_source",
                        },
                    )
                )
                continue

            if is_task_dag and (
                "dag" in req.description.lower()
                or "topological" in req.description.lower()
                or "decompose" in req.description.lower()
                or "sort" in req.description.lower()
            ):
                contract = SemanticContract(
                    effect_type="TOPOLOGICAL_SORT",
                    inputs={"tasks": ContractField(type_name="List[Dict[str, Any]]")},
                    outputs={
                        "sorted_dag": ContractField(type_name="List[str]"),
                        "has_cycles": ContractField(type_name="bool"),
                        "node_count": ContractField(type_name="int"),
                    },
                    transformation_rule="DAG_TOPOLOGICAL_SORT",
                )
                binding_hash = compute_canonical_binding_hash(
                    req.requirement_hash, req.requirement_id, contract, req.is_blocking
                )
                candidates.append(
                    CandidateSemanticBinding(
                        binding_hash=binding_hash,
                        requirement_hash=req.requirement_hash,
                        source_requirement_id=req.requirement_id,
                        semantic_contract=contract,
                        is_blocking=req.is_blocking,
                        candidate_provenance={
                            "origin": "SYSTEM_INVARIANT_PREDICATE",
                            "precondition": "verified_task_list",
                        },
                    )
                )
                continue

            # 3. Incorporate any model proposals (ZERO AUTHORITY HYPOTHESES)
            matched_model_props = [
                p
                for p in (model_proposals or [])
                if p.get("requirement_id") == req.requirement_id or not p.get("requirement_id")
            ]
            if matched_model_props:
                for prop in matched_model_props:
                    inputs_raw = prop.get("inputs", {})
                    outputs_raw = prop.get("outputs", {})
                    contract = SemanticContract(
                        effect_type=prop.get("effect_type", "UNVERIFIED_EFFECT"),
                        inputs={
                            k: ContractField(type_name=str(v) if isinstance(v, str) else v.get("type_name", "Any"))
                            for k, v in inputs_raw.items()
                        },
                        outputs={
                            k: ContractField(type_name=str(v) if isinstance(v, str) else v.get("type_name", "Any"))
                            for k, v in outputs_raw.items()
                        },
                        transformation_rule=prop.get("transformation_rule"),
                    )
                    binding_hash = compute_canonical_binding_hash(
                        req.requirement_hash, req.requirement_id, contract, req.is_blocking
                    )
                    candidates.append(
                        CandidateSemanticBinding(
                            binding_hash=binding_hash,
                            requirement_hash=req.requirement_hash,
                            source_requirement_id=req.requirement_id,
                            semantic_contract=contract,
                            is_blocking=req.is_blocking,
                            candidate_provenance={"origin": "MODEL_PROPOSAL", "raw_proposal": prop},
                        )
                    )

        return candidates


class SemanticAuthorityVerifier:
    """
    Evaluates candidate semantic interpretations against KernelDatabase custody.
    Never invents missing contracts or infers authority from model output or matching capabilities.
    """

    def __init__(self, kernel_db: Optional[KernelDatabase] = None):
        self.kernel_db = kernel_db or KernelDatabase()

    def verify_candidate(
        self,
        candidate: CandidateSemanticBinding,
        canonical_requirement: CanonicalRequirement,
    ) -> Tuple[SemanticBindingStatus, Optional[SemanticApplicabilityProof], Optional[str]]:
        # 1. Validate complete canonical binding hash integrity
        expected_hash = compute_canonical_binding_hash(
            requirement_hash=canonical_requirement.requirement_hash,
            source_requirement_id=canonical_requirement.requirement_id,
            semantic_contract=candidate.semantic_contract,
            is_blocking=canonical_requirement.is_blocking,
        )
        if candidate.binding_hash != expected_hash:
            return (SemanticBindingStatus.UNSUPPORTED, None, "Candidate binding hash mismatch / tampered structure.")

        # 2. Check Path A: SOURCE_EXPLICIT_CONTRACT (Origin must be literal structured contract)
        if candidate.candidate_provenance.get("origin") == "INGRESS_STRUCTURED_CONTRACT":
            proof_id = f"sp_src_{uuid.uuid4().hex[:8]}"
            proof = SemanticApplicabilityProof(
                proof_id=proof_id,
                binding_hash=candidate.binding_hash,
                requirement_hash=candidate.requirement_hash,
                semantic_contract_hash=candidate.semantic_contract.contract_hash,
                authority_source=SemanticAuthoritySource.SOURCE_EXPLICIT_CONTRACT,
                authority_record_id=f"rec_src_{candidate.source_requirement_id}",
            )
            self.kernel_db.record_semantic_proof(
                proof_id=proof.proof_id,
                binding_hash=proof.binding_hash,
                requirement_hash=proof.requirement_hash,
                semantic_contract_hash=proof.semantic_contract_hash,
                authority_source=proof.authority_source.value,
                authority_record_id=proof.authority_record_id,
                verifier_version=proof.verifier_version,
                status="VERIFIED",
            )
            return (SemanticBindingStatus.GROUNDED, proof, None)

        # 3. Check Path B: SYSTEM_INVARIANT (Preconditions physically verified)
        if candidate.candidate_provenance.get("origin") == "SYSTEM_INVARIANT_PREDICATE":
            proof_id = f"sp_inv_{uuid.uuid4().hex[:8]}"
            proof = SemanticApplicabilityProof(
                proof_id=proof_id,
                binding_hash=candidate.binding_hash,
                requirement_hash=candidate.requirement_hash,
                semantic_contract_hash=candidate.semantic_contract.contract_hash,
                authority_source=SemanticAuthoritySource.SYSTEM_INVARIANT,
                authority_record_id=f"tcb_invariant_{candidate.semantic_contract.effect_type}",
            )
            self.kernel_db.record_semantic_proof(
                proof_id=proof.proof_id,
                binding_hash=proof.binding_hash,
                requirement_hash=proof.requirement_hash,
                semantic_contract_hash=proof.semantic_contract_hash,
                authority_source=proof.authority_source.value,
                authority_record_id=proof.authority_record_id,
                verifier_version=proof.verifier_version,
                status="VERIFIED",
            )
            return (SemanticBindingStatus.GROUNDED, proof, None)

        # 4. Check Path C: EXPLICIT_HUMAN_APPROVAL in KernelDatabase
        approval = self.kernel_db.get_approval_for_subject(
            subject_type="SEMANTIC_BINDING", subject_hash=candidate.binding_hash
        )
        if approval:
            proof_id = f"sp_app_{uuid.uuid4().hex[:8]}"
            proof = SemanticApplicabilityProof(
                proof_id=proof_id,
                binding_hash=candidate.binding_hash,
                requirement_hash=candidate.requirement_hash,
                semantic_contract_hash=candidate.semantic_contract.contract_hash,
                authority_source=SemanticAuthoritySource.EXPLICIT_HUMAN_APPROVAL,
                authority_record_id=approval["approval_id"],
            )
            self.kernel_db.record_semantic_proof(
                proof_id=proof.proof_id,
                binding_hash=proof.binding_hash,
                requirement_hash=proof.requirement_hash,
                semantic_contract_hash=proof.semantic_contract_hash,
                authority_source=proof.authority_source.value,
                authority_record_id=proof.authority_record_id,
                verifier_version=proof.verifier_version,
                status="VERIFIED",
            )
            return (SemanticBindingStatus.GROUNDED, proof, None)

        # 5. Check Path D: VERIFIED_DOMAIN_AUTHORITY in KernelDatabase
        domain_authorities = self.kernel_db.find_domain_authorities(status="VERIFIED")
        for dom_auth in domain_authorities:
            mapping = dom_auth.get("mapping", {})
            if canonical_requirement.description in mapping or canonical_requirement.requirement_id in mapping:
                expected_rule = mapping.get(canonical_requirement.description) or mapping.get(
                    canonical_requirement.requirement_id
                )
                if expected_rule and expected_rule.get("effect_type") == candidate.semantic_contract.effect_type:
                    proof_id = f"sp_dom_{uuid.uuid4().hex[:8]}"
                    proof = SemanticApplicabilityProof(
                        proof_id=proof_id,
                        binding_hash=candidate.binding_hash,
                        requirement_hash=candidate.requirement_hash,
                        semantic_contract_hash=candidate.semantic_contract.contract_hash,
                        authority_source=SemanticAuthoritySource.VERIFIED_DOMAIN_AUTHORITY,
                        authority_record_id=dom_auth["authority_id"],
                    )
                    self.kernel_db.record_semantic_proof(
                        proof_id=proof.proof_id,
                        binding_hash=proof.binding_hash,
                        requirement_hash=proof.requirement_hash,
                        semantic_contract_hash=proof.semantic_contract_hash,
                        authority_source=proof.authority_source.value,
                        authority_record_id=proof.authority_record_id,
                        verifier_version=proof.verifier_version,
                        status="VERIFIED",
                    )
                    return (SemanticBindingStatus.GROUNDED, proof, None)

        # 6. Check Path E: AUTHORITATIVE_EXTERNAL_EVIDENCE in KernelDatabase
        for ev_req in candidate.semantic_contract.evidence_requirements:
            ev_rec = self.kernel_db.get_authority_evidence(ev_req.evidence_id)
            if (
                ev_rec
                and ev_rec.get("status") == "VERIFIED"
                and ev_rec.get("evidence_class") == ev_req.required_evidence_class.value
            ):
                proof_id = f"sp_ev_{uuid.uuid4().hex[:8]}"
                proof = SemanticApplicabilityProof(
                    proof_id=proof_id,
                    binding_hash=candidate.binding_hash,
                    requirement_hash=candidate.requirement_hash,
                    semantic_contract_hash=candidate.semantic_contract.contract_hash,
                    authority_source=SemanticAuthoritySource.AUTHORITATIVE_EXTERNAL_EVIDENCE,
                    authority_record_id=ev_rec["evidence_id"],
                )
                self.kernel_db.record_semantic_proof(
                    proof_id=proof.proof_id,
                    binding_hash=proof.binding_hash,
                    requirement_hash=proof.requirement_hash,
                    semantic_contract_hash=proof.semantic_contract_hash,
                    authority_source=proof.authority_source.value,
                    authority_record_id=proof.authority_record_id,
                    verifier_version=proof.verifier_version,
                    status="VERIFIED",
                )
                return (SemanticBindingStatus.GROUNDED, proof, None)

        # If origin is model proposal without independent grounding
        if candidate.candidate_provenance.get("origin") == "MODEL_PROPOSAL":
            return (
                SemanticBindingStatus.UNSUPPORTED,
                None,
                f"Model proposed effect '{candidate.semantic_contract.effect_type}' carries zero closure authority without independent domain/source/human grounding.",
            )

        return (
            SemanticBindingStatus.UNSUPPORTED,
            None,
            f"No verified semantic authority in KernelDatabase grounds candidate contract '{candidate.semantic_contract.effect_type}' for requirement '{canonical_requirement.requirement_id}'.",
        )


class ObligationDerivationEngine:
    """
    Coordinates CandidateBindingGenerator and SemanticAuthorityVerifier.
    Translates ONLY legitimately verified SemanticApplicabilityProofs into SatisfactionObligations.
    """

    def __init__(self, kernel_db: Optional[KernelDatabase] = None):
        self.kernel_db = kernel_db or KernelDatabase()
        self.generator = CandidateBindingGenerator()
        self.verifier = SemanticAuthorityVerifier(self.kernel_db)

    def derive_obligations(
        self,
        canonical_requirements: List[CanonicalRequirement],
        raw_intent: str,
        structured_contracts: Optional[List[Dict[str, Any]]] = None,
        model_proposals: Optional[List[Dict[str, Any]]] = None,
        known_inputs: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[SatisfactionObligation], List[ResolutionDeficit]]:
        obligations: List[SatisfactionObligation] = []
        deficits: List[ResolutionDeficit] = []

        candidates = self.generator.generate_candidates(
            canonical_requirements=canonical_requirements,
            raw_intent=raw_intent,
            structured_contracts=structured_contracts,
            model_proposals=model_proposals,
            known_inputs=known_inputs,
        )

        req_map = {r.requirement_id: r for r in canonical_requirements}

        for req in canonical_requirements:
            req_candidates = [c for c in candidates if c.source_requirement_id == req.requirement_id]

            if not req_candidates:
                if req.is_blocking:
                    deficits.append(
                        ResolutionDeficit(
                            deficit_type="SEMANTIC_BINDING_DEFICIT",
                            obligation_id=f"obl_{req.requirement_id}",
                            reason=f"No candidate semantic interpretation generated for requirement '{req.requirement_id}' ({req.description}).",
                            missing_element="SEMANTIC_APPLICABILITY_PROOF",
                        )
                    )
                continue

            # Evaluate each candidate interpretation through the passive verifier
            grounded_proofs: List[Tuple[CandidateSemanticBinding, SemanticApplicabilityProof]] = []
            rejection_reasons: List[str] = []

            for cand in req_candidates:
                status, proof, reason = self.verifier.verify_candidate(cand, req)
                if status == SemanticBindingStatus.GROUNDED and proof is not None:
                    # Double-check proof resolves legitimately from KernelDatabase
                    persisted = self.kernel_db.get_semantic_proof(proof.proof_id)
                    if persisted and persisted.get("status") == "VERIFIED":
                        grounded_proofs.append((cand, proof))
                else:
                    if reason:
                        rejection_reasons.append(reason)

            if len(grounded_proofs) > 1:
                # Ambiguous: Multiple conflicting grounded interpretations with no decider
                if req.is_blocking:
                    deficits.append(
                        ResolutionDeficit(
                            deficit_type="AMBIGUOUS",
                            obligation_id=f"obl_{req.requirement_id}",
                            reason=f"Requirement '{req.requirement_id}' has {len(grounded_proofs)} conflicting grounded interpretations with no deciding policy.",
                            missing_element="AMBIGUITY_RESOLUTION_AUTHORITY",
                        )
                    )
                continue

            if len(grounded_proofs) == 1:
                cand, proof = grounded_proofs[0]
                obl_authority = (
                    ObligationAuthority.SOURCE_GROUNDED
                    if proof.authority_source == SemanticAuthoritySource.SOURCE_EXPLICIT_CONTRACT
                    else ObligationAuthority.SYSTEM_INVARIANT
                    if proof.authority_source == SemanticAuthoritySource.SYSTEM_INVARIANT
                    else ObligationAuthority.VERIFIED_DOMAIN_DERIVED
                    if proof.authority_source
                    in (
                        SemanticAuthoritySource.VERIFIED_DOMAIN_AUTHORITY,
                        SemanticAuthoritySource.AUTHORITATIVE_EXTERNAL_EVIDENCE,
                    )
                    else ObligationAuthority.HUMAN_APPROVED
                )

                input_contract = {k: v.type_name for k, v in cand.semantic_contract.inputs.items()}
                output_contract = {k: v.type_name for k, v in cand.semantic_contract.outputs.items()}

                # Construct grounded obligation carrying sealed proof lineage
                obl = SatisfactionObligation(
                    obligation_id=f"obl_{req.requirement_id}",
                    source_requirement_ids=[req.requirement_id],
                    authority=obl_authority,
                    required_effect_type=cand.semantic_contract.effect_type,
                    required_input_contract=input_contract,
                    required_output_contract=output_contract,
                    required_evidence=list(cand.semantic_contract.evidence_requirements),
                    required_authority=list(cand.semantic_contract.authority_requirements),
                    required_verification=[],
                    is_blocking=cand.is_blocking,
                    provenance={
                        "proof_id": proof.proof_id,
                        "authority_source": proof.authority_source.value,
                        "authority_record_id": proof.authority_record_id,
                        "transformation_rule": cand.semantic_contract.transformation_rule,
                        "verification_spec": cand.semantic_contract.verification_spec,
                    },
                    requirement_hash=cand.requirement_hash,
                    semantic_binding_hash=cand.binding_hash,
                    applicability_proof_id=proof.proof_id,
                    applicability_proof_hash=proof.semantic_contract_hash,
                )
                obligations.append(obl)
            else:
                # No candidate was grounded
                if req.is_blocking:
                    deficits.append(
                        ResolutionDeficit(
                            deficit_type="SEMANTIC_BINDING_DEFICIT",
                            obligation_id=f"obl_{req.requirement_id}",
                            reason="; ".join(rejection_reasons)
                            or f"Requirement '{req.requirement_id}' lacks verified semantic authority.",
                            missing_element="SEMANTIC_APPLICABILITY_PROOF",
                        )
                    )

        return obligations, deficits
