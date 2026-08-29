import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field

from loop_engine.artifacts import (
    ArtifactRecord,
    ArtifactRegistry,
    MasterAVScriptArtifact,
    ProductionPlanDAGArtifact,
    StructuredSourceArtifact,
)
from loop_engine.canonical_objective import CanonicalObjective, EvidenceReference, UnknownReference
from loop_engine.context import RunContext
from loop_engine.governor import StepExecutionResult, StepGovernor
from loop_engine.kernel_db import KernelDatabase
from loop_engine.runners.herald_runner import HeraldAVScriptDomainRunner
from loop_engine.runners.scribe_runner import ScribeDomainRunner
from loop_engine.runners.slicer_runner import SlicerDomainRunner


class RoutingDecision(BaseModel):
    """
    Explicit, auditable multi-Shadow routing plan.
    """

    objective: str
    run_id: str
    selected_shadow_ids: List[int] = Field(description="Ordered sequence of Shadow IDs to execute")
    selected_domain_codes: List[str]
    excluded_shadow_ids: List[int]
    exclusion_reasons: Dict[int, str]
    expected_artifacts: List[str]
    verification_gates: List[str]
    escalation_conditions: List[str]


class HumanEscalationRecord(BaseModel):
    """
    Structured record emitted when an ambiguous objective, security hazard,
    strike ceiling breach, or required human gate halts automated execution.
    """

    escalation_id: str
    run_id: str
    parent_run_id: str
    task_id: str
    shadow_id: int
    category: Literal[
        "UNRESOLVED_FACTUAL_CONFLICT",
        "MISSING_EVIDENCE",
        "EXTERNAL_PUBLICATION_APPROVAL",
        "DESTRUCTIVE_FILE_MUTATION",
        "MERGE_CONFLICT",
        "AMBIGUOUS_AUDIENCE_OBJECTIVE",
        "SECURITY_SENSITIVE_ACTION",
        "STRIKE_CEILING_EXCEEDED",
        "HUMAN_APPROVAL_REQUIRED",
    ]
    reason: str
    details: Dict[str, Any] = Field(default_factory=dict)
    remediation_options: List[str] = Field(default_factory=list)
    status: Literal["PENDING", "AWAITING_APPROVAL", "RESOLVED_APPROVED", "RESOLVED_REJECTED", "RESOLVED_OVERRIDDEN"] = (
        "AWAITING_APPROVAL"
    )
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class RouteStep(BaseModel):
    """
    A single typed step within a multi-Shadow RoutePlan.
    """

    step_id: str
    shadow_id: int
    domain_code: str
    runner_name: str
    input_artifact_type: Optional[str] = None
    output_artifact_type: str
    output_schema_version: str = "1.0.0"
    producer_version: str = "1.0.0"
    validator_policy_fingerprint: str = "standard_policy_v1"
    dependencies: List[str] = Field(default_factory=list)
    requires_human_approval: bool = False


class RoutePlan(BaseModel):
    """
    Topologically ordered, deterministic multi-Shadow route plan.
    """

    plan_id: str
    pipeline_type: str
    canonical_objective_hash: str
    selected_shadow_ids: List[int]
    selected_domain_codes: List[str]
    excluded_shadow_ids: List[int]
    exclusion_reasons: Dict[int, str]
    steps: List[RouteStep]
    route_plan_hash: str = ""

    def compute_route_hash(self) -> str:
        """Computes deterministic SHA-256 hash of the complete plan."""
        step_signatures = [
            f"{s.step_id}:{s.shadow_id}:{s.domain_code}:{s.input_artifact_type}:{s.output_artifact_type}"
            for s in self.steps
        ]
        raw_repr = f"{self.pipeline_type}:{self.canonical_objective_hash}:{','.join(step_signatures)}"
        return hashlib.sha256(raw_repr.encode("utf-8")).hexdigest()


class RouteExecutionResult(BaseModel):
    """
    Structured outcome of an end-to-end multi-Shadow route execution.
    """

    status: Literal["SUCCESS", "ESCALATED", "AWAITING_APPROVAL", "RESUMED", "ABORTED"]
    parent_run_id: str
    route_plan_hash: str
    completed_step_ids: List[str] = Field(default_factory=list)
    cached_step_ids: List[str] = Field(default_factory=list)
    current_step_id: Optional[str] = None
    final_artifact_id: Optional[str] = None
    final_artifact_type: Optional[str] = None
    step_results: Dict[str, StepExecutionResult] = Field(default_factory=dict)
    escalation: Optional[HumanEscalationRecord] = None
    last_error: Optional[str] = None


class BoundedShadowRouter:
    """
    Shadow Routing & Capability Orchestrator.

    Inspects canonical objectives, determines required Shadow domains,
    orders them by dependency DAG, and executes verified multi-Shadow pipelines.
    """

    CAPABILITY_MAP = {
        "media_deconstruction": (4, "media"),
        "av_script_generation": (3, "herald"),
        "adversarial_audit": (5, "inquisitor"),
        "relational_memory": (6, "scribe"),
        "dag_decomposition": (7, "slicer"),
        "worktree_isolation": (8, "warden"),
        "self_healing_repair": (9, "alchemist"),
        "state_projection": (10, "gamemaster"),
    }

    @classmethod
    def route_objective(cls, objective: Dict[str, Any]) -> RoutingDecision:
        """Legacy helper for backward compatibility."""
        obj_type = objective.get("type", "unknown")
        task_id = objective.get("task_id", "task_routed")
        run_id = f"route_{task_id}"

        selected_ids: List[int] = []
        selected_codes: List[str] = []
        expected_artifacts: List[str] = []
        verification_gates: List[str] = []
        escalation_conditions: List[str] = [
            "Missing verified evidence in CanonicalMediaBrief",
            "Merge conflict in Warden worktree",
            "Strike ceiling exceeded (3 strikes)",
        ]

        if obj_type == "av_production":
            selected_ids = [6, 3, 7, 8, 10]
            selected_codes = ["scribe", "herald", "slicer", "warden", "gamemaster"]
            expected_artifacts = ["canonical_brief.json", "master_av_script.md", "task_dag.json", "wal_receipt.json"]
            verification_gates = ["AntiAILinguisticGuard", "CinematographyValidator", "DeterministicScriptValidator"]
        elif obj_type == "self_healing":
            selected_ids = [9, 8, 2, 10]
            selected_codes = ["alchemist", "warden", "svris", "gamemaster"]
            expected_artifacts = ["crash_diagnostic.json", "surgical_patch.json", "wal_receipt.json"]
            verification_gates = ["ASTSyntaxGate", "IsolatedPytestGate"]
        else:
            selected_ids = [3, 8, 10]
            selected_codes = ["herald", "warden", "gamemaster"]
            expected_artifacts = ["av_script.json", "wal_receipt.json"]
            verification_gates = ["DeterministicScriptValidator"]

        all_shadow_ids = set(range(1, 11))
        excluded_ids = sorted(list(all_shadow_ids - set(selected_ids)))
        exclusion_reasons = {
            s_id: f"Shadow {s_id} not required for objective type '{obj_type}'." for s_id in excluded_ids
        }

        return RoutingDecision(
            objective=str(objective.get("description", obj_type)),
            run_id=run_id,
            selected_shadow_ids=selected_ids,
            selected_domain_codes=selected_codes,
            excluded_shadow_ids=excluded_ids,
            exclusion_reasons=exclusion_reasons,
            expected_artifacts=expected_artifacts,
            verification_gates=verification_gates,
            escalation_conditions=escalation_conditions,
        )

    @classmethod
    def plan_route(
        cls,
        canonical_objective: CanonicalObjective,
        requested_pipeline_type: str = "media_production",
    ) -> RoutePlan:
        """
        Synthesizes a minimal, topologically sorted multi-Shadow RoutePlan.
        """
        obj_hash = canonical_objective.compute_objective_hash()
        plan_id = f"plan_{canonical_objective.objective_id}"

        if requested_pipeline_type == "media_production":
            # Flow: Scribe (6) -> Herald (3) -> Slicer (7)
            steps = [
                RouteStep(
                    step_id="step_1_scribe",
                    shadow_id=6,
                    domain_code="scribe",
                    runner_name="TheScribeDomainRunner",
                    input_artifact_type=None,
                    output_artifact_type="StructuredSourceArtifact",
                    dependencies=[],
                ),
                RouteStep(
                    step_id="step_2_herald",
                    shadow_id=3,
                    domain_code="herald",
                    runner_name="TheHeraldAVScriptDomainRunner",
                    input_artifact_type="StructuredSourceArtifact",
                    output_artifact_type="MasterAVScriptArtifact",
                    dependencies=["step_1_scribe"],
                ),
                RouteStep(
                    step_id="step_3_slicer",
                    shadow_id=7,
                    domain_code="slicer",
                    runner_name="TheSlicerDomainRunner",
                    input_artifact_type="MasterAVScriptArtifact",
                    output_artifact_type="ProductionPlanDAGArtifact",
                    dependencies=["step_2_herald"],
                ),
            ]
            selected_shadow_ids = [6, 3, 7]
            selected_domain_codes = ["scribe", "herald", "slicer"]
        else:
            steps = [
                RouteStep(
                    step_id="step_1_single",
                    shadow_id=3,
                    domain_code="herald",
                    runner_name="TheHeraldAVScriptDomainRunner",
                    input_artifact_type=None,
                    output_artifact_type="MasterAVScriptArtifact",
                    dependencies=[],
                )
            ]
            selected_shadow_ids = [3]
            selected_domain_codes = ["herald"]

        all_shadow_ids = set(range(1, 11))
        excluded_ids = sorted(list(all_shadow_ids - set(selected_shadow_ids)))
        exclusion_reasons = {
            s_id: f"Shadow {s_id} not required for pipeline '{requested_pipeline_type}'." for s_id in excluded_ids
        }

        plan = RoutePlan(
            plan_id=plan_id,
            pipeline_type=requested_pipeline_type,
            canonical_objective_hash=obj_hash,
            selected_shadow_ids=selected_shadow_ids,
            selected_domain_codes=selected_domain_codes,
            excluded_shadow_ids=excluded_ids,
            exclusion_reasons=exclusion_reasons,
            steps=steps,
        )
        plan.route_plan_hash = plan.compute_route_hash()
        return plan

    @classmethod
    def execute_route(
        cls,
        plan: RoutePlan,
        canonical_objective: CanonicalObjective,
        parent_context: RunContext,
        artifact_registry: ArtifactRegistry,
        kernel_db: KernelDatabase,
        step_governor: Optional[StepGovernor] = None,
        resume: bool = False,
        runner_instances: Optional[Dict[str, Any]] = None,
        forced_step_failure: Optional[Dict[str, int]] = None,
        forced_step_failure_msg: Optional[str] = None,
    ) -> RouteExecutionResult:
        """
        Executes a multi-Shadow RoutePlan with verification-bound resume and human pause/resume state machine.
        """
        governor = step_governor or StepGovernor(kernel_db=kernel_db)
        forced_failures = forced_step_failure or {}

        # Default runner instances if not provided
        runners = runner_instances or {
            "scribe": ScribeDomainRunner(),
            "herald": HeraldAVScriptDomainRunner(),
            "slicer": SlicerDomainRunner(),
        }

        completed_steps: List[str] = []
        cached_steps: List[str] = []
        step_results: Dict[str, StepExecutionResult] = {}
        current_input: Any = canonical_objective
        current_artifact_id: Optional[str] = None
        current_artifact_hash: str = "0" * 64
        final_artifact_type: Optional[str] = None

        # Parent run state initialization
        kernel_db.record_run_state(
            run_id=parent_context.run_id,
            task_id=parent_context.task_id,
            shadow_id=parent_context.shadow_id,
            domain_code=parent_context.domain_code,
            source_commit=parent_context.source_commit,
            objective_hash=canonical_objective.compute_objective_hash(),
            canonical_input_hash=parent_context.canonical_input_hash,
            status="RUNNING",
            authority_level=parent_context.authority_level,
            status_history=parent_context.status_history,
            current_attempt=1,
            current_strike=0,
        )

        for step in plan.steps:
            # 1. Verification-Bound Resume Check
            if resume:
                cached_rec = artifact_registry.find_verified_artifact(
                    parent_run_id=parent_context.run_id,
                    route_plan_hash=plan.route_plan_hash,
                    step_id=step.step_id,
                    source_artifact_hash=current_artifact_hash,
                    source_commit=parent_context.source_commit,
                    producer_version=step.producer_version,
                    validator_policy_fingerprint=step.validator_policy_fingerprint,
                    output_schema_version=step.output_schema_version,
                )

                if cached_rec:
                    cached_steps.append(step.step_id)
                    completed_steps.append(step.step_id)
                    current_artifact_id = cached_rec.artifact_id
                    current_artifact_hash = cached_rec.content_sha256
                    final_artifact_type = cached_rec.artifact_type
                    # Load payload for forward pass
                    payload = artifact_registry.load_artifact_content(cached_rec)
                    if step.output_artifact_type == "StructuredSourceArtifact":
                        current_input = StructuredSourceArtifact.model_validate(payload)
                    elif step.output_artifact_type == "MasterAVScriptArtifact":
                        current_input = MasterAVScriptArtifact.model_validate(payload)
                    elif step.output_artifact_type == "ProductionPlanDAGArtifact":
                        current_input = ProductionPlanDAGArtifact.model_validate(payload)
                    continue

            # 2. Check for required human approval gate
            if step.requires_human_approval:
                escalation_id = f"esc_approval_{step.step_id}_{int(datetime.now(timezone.utc).timestamp())}"
                escalation_record = HumanEscalationRecord(
                    escalation_id=escalation_id,
                    run_id=f"child_{step.shadow_id}_{parent_context.run_id}_{step.step_id}",
                    parent_run_id=parent_context.run_id,
                    task_id=parent_context.task_id,
                    shadow_id=step.shadow_id,
                    category="HUMAN_APPROVAL_REQUIRED",
                    reason=f"Step '{step.step_id}' requires explicit operator review before proceeding.",
                    details={"step_id": step.step_id, "route_plan_hash": plan.route_plan_hash},
                    remediation_options=["APPROVE_AND_PROCEED", "ABORT_PIPELINE"],
                )
                kernel_db.record_escalation(
                    escalation_id=escalation_id,
                    run_id=escalation_record.run_id,
                    parent_run_id=parent_context.run_id,
                    task_id=parent_context.task_id,
                    shadow_id=step.shadow_id,
                    category=escalation_record.category,
                    reason=escalation_record.reason,
                    details=escalation_record.details,
                    remediation_options=escalation_record.remediation_options,
                )
                parent_context.transition_status("AWAITING_APPROVAL")
                kernel_db.record_run_state(
                    run_id=parent_context.run_id,
                    task_id=parent_context.task_id,
                    shadow_id=parent_context.shadow_id,
                    domain_code=parent_context.domain_code,
                    source_commit=parent_context.source_commit,
                    objective_hash=canonical_objective.compute_objective_hash(),
                    canonical_input_hash=parent_context.canonical_input_hash,
                    status="AWAITING_APPROVAL",
                    authority_level=parent_context.authority_level,
                    status_history=parent_context.status_history,
                )
                return RouteExecutionResult(
                    status="AWAITING_APPROVAL",
                    parent_run_id=parent_context.run_id,
                    route_plan_hash=plan.route_plan_hash,
                    completed_step_ids=completed_steps,
                    cached_step_ids=cached_steps,
                    current_step_id=step.step_id,
                    final_artifact_id=current_artifact_id,
                    final_artifact_type=final_artifact_type,
                    step_results=step_results,
                    escalation=escalation_record,
                )

            # 3. Execute step under StepGovernor
            runner = runners.get(step.domain_code)
            if not runner:
                raise ValueError(f"No runner registered for domain '{step.domain_code}'")

            forced_fail_attempt = forced_failures.get(step.step_id)

            step_res = governor.run_step(
                loop=runner,
                raw_input=current_input,
                parent_context=parent_context,
                step_id=step.step_id,
                forced_failure_attempt=forced_fail_attempt,
                forced_failure_msg=forced_step_failure_msg,
            )

            step_results[step.step_id] = step_res

            # 4. Handle Step Outcome
            if step_res.status == "SUCCESS":
                completed_steps.append(step.step_id)

                # Reconstruct and register verified artifact
                artifact_obj: Any = None
                if step.output_artifact_type == "StructuredSourceArtifact":
                    if isinstance(current_input, CanonicalObjective):
                        artifact_obj = StructuredSourceArtifact(
                            source_project_id=current_input.objective_id,
                            canonical_goal=current_input.desired_outcome,
                            target_audience=current_input.target_audience,
                            core_message=current_input.core_message,
                            intended_audience_action=current_input.intended_audience_action,
                            narrative_arc_type=current_input.narrative_arc_type,
                            verified_facts=current_input.verified_evidence,
                            explicit_unknowns=current_input.explicit_unknowns,
                            provenance={"source_commit": parent_context.source_commit},
                        )
                elif step.output_artifact_type == "MasterAVScriptArtifact":
                    # Load from runner staging or destination
                    dest_md = step_res.receipt.get("destination_markdown", "") if step_res.receipt else ""
                    dest_json = step_res.receipt.get("destination_json", "") if step_res.receipt else ""
                    from pathlib import Path

                    p_json = Path(dest_json)
                    p_md = Path(dest_md)
                    if p_json.exists() and p_md.exists():
                        bp_data = json.loads(p_json.read_text(encoding="utf-8"))
                        md_data = p_md.read_text(encoding="utf-8")
                        from loop_engine.herald.schema import MasterAVScriptBlueprint

                        bp = MasterAVScriptBlueprint.model_validate(bp_data)
                        evidence_refs = [
                            EvidenceReference(
                                evidence_id=e.evidence_id,
                                source_description=e.source_description,
                                confidence="VERIFIED_FACT",
                            )
                            for e in bp.verified_evidence
                        ]
                        unknown_refs = [
                            UnknownReference(
                                unknown_id=u.unknown_id,
                                description=u.description,
                                classification=u.classification
                                if u.classification
                                in (
                                    "CREATIVE_PROPOSAL",
                                    "ASSUMPTION_REQUIRING_APPROVAL",
                                    "UNRESOLVED_FACTUAL_CONFLICT",
                                    "UNRESOLVED_UNKNOWN",
                                )
                                else "ASSUMPTION_REQUIRING_APPROVAL",
                                mitigation_or_approval_decision=u.mitigation_or_approval_decision
                                or "Standard coverage",
                            )
                            for u in bp.explicit_unknowns
                        ]
                        artifact_obj = MasterAVScriptArtifact(
                            script_id=bp.script_id,
                            source_artifact_id=current_artifact_id or "root_source",
                            source_artifact_hash=current_artifact_hash,
                            strategic_intent=bp.strategic_intent,
                            technical_scope=bp.technical_scope,
                            verified_facts=evidence_refs,
                            explicit_unknowns=unknown_refs,
                            av_table=bp.av_table,
                            modular_cutdowns=bp.technical_scope.modular_cutdowns,
                            rendered_markdown=md_data,
                            provenance={"source_commit": parent_context.source_commit},
                        )
                elif step.output_artifact_type == "ProductionPlanDAGArtifact":
                    dest_file = step_res.receipt.get("destination", "") if step_res.receipt else ""
                    from pathlib import Path

                    p = Path(dest_file)
                    if p.exists():
                        raw_data = json.loads(p.read_text(encoding="utf-8"))
                        if "artifact" in raw_data:
                            artifact_obj = ProductionPlanDAGArtifact.model_validate(raw_data["artifact"])

                if artifact_obj:
                    # Stage and promote artifact in registry
                    art_rec = artifact_registry.stage_artifact(
                        artifact_obj=artifact_obj,
                        run_id=step_res.run_id,
                        parent_run_id=parent_context.run_id,
                        producing_shadow_id=step.shadow_id,
                        domain_code=step.domain_code,
                        step_id=step.step_id,
                        route_plan_hash=plan.route_plan_hash,
                        source_artifact_hash=current_artifact_hash,
                        source_commit=parent_context.source_commit,
                        producer_version=step.producer_version,
                        validator_policy_fingerprint=step.validator_policy_fingerprint,
                    )
                    artifact_registry.transition_state(
                        artifact_id=art_rec.artifact_id,
                        to_state="VERIFIED",
                        reason="STEP_VERIFICATION_PASSED",
                        actor_domain=step.domain_code,
                    )
                    artifact_registry.transition_state(
                        artifact_id=art_rec.artifact_id,
                        to_state="PROMOTED",
                        reason="PROMOTED_TO_PRODUCTION",
                        actor_domain=step.domain_code,
                    )
                    current_artifact_id = art_rec.artifact_id
                    current_artifact_hash = art_rec.content_sha256
                    current_input = artifact_obj
                    final_artifact_type = step.output_artifact_type

            else:
                # Step Failed / Aborted -> Trigger Human Escalation
                escalation_id = f"esc_{step.step_id}_{int(datetime.now(timezone.utc).timestamp())}"
                escalation_record = HumanEscalationRecord(
                    escalation_id=escalation_id,
                    run_id=step_res.run_id,
                    parent_run_id=parent_context.run_id,
                    task_id=parent_context.task_id,
                    shadow_id=step.shadow_id,
                    category="STRIKE_CEILING_EXCEEDED",
                    reason=step_res.last_error
                    or f"Step '{step.step_id}' aborted after 3 failed verification attempts.",
                    details={
                        "step_id": step.step_id,
                        "strikes_exhausted": step_res.strikes_used,
                        "negative_constraints_ledger": step_res.negative_constraints_ledger,
                    },
                    remediation_options=[
                        "REVISE_CANONICAL_OBJECTIVE",
                        "MANUAL_OVERRIDE_AND_RESUME",
                        "ABORT_PIPELINE",
                    ],
                )

                kernel_db.record_escalation(
                    escalation_id=escalation_id,
                    run_id=step_res.run_id,
                    parent_run_id=parent_context.run_id,
                    task_id=parent_context.task_id,
                    shadow_id=step.shadow_id,
                    category=escalation_record.category,
                    reason=escalation_record.reason,
                    details=escalation_record.details,
                    remediation_options=escalation_record.remediation_options,
                )

                parent_context.transition_status("ESCALATED")
                parent_context.transition_status("AWAITING_APPROVAL")

                kernel_db.record_run_state(
                    run_id=parent_context.run_id,
                    task_id=parent_context.task_id,
                    shadow_id=parent_context.shadow_id,
                    domain_code=parent_context.domain_code,
                    source_commit=parent_context.source_commit,
                    objective_hash=canonical_objective.compute_objective_hash(),
                    canonical_input_hash=parent_context.canonical_input_hash,
                    status="AWAITING_APPROVAL",
                    authority_level=parent_context.authority_level,
                    status_history=parent_context.status_history,
                )

                return RouteExecutionResult(
                    status="ESCALATED",
                    parent_run_id=parent_context.run_id,
                    route_plan_hash=plan.route_plan_hash,
                    completed_step_ids=completed_steps,
                    cached_step_ids=cached_steps,
                    current_step_id=step.step_id,
                    final_artifact_id=current_artifact_id,
                    final_artifact_type=final_artifact_type,
                    step_results=step_results,
                    escalation=escalation_record,
                    last_error=step_res.last_error,
                )

        # All steps completed successfully
        parent_context.transition_status("COMPLETED")
        kernel_db.record_run_state(
            run_id=parent_context.run_id,
            task_id=parent_context.task_id,
            shadow_id=parent_context.shadow_id,
            domain_code=parent_context.domain_code,
            source_commit=parent_context.source_commit,
            objective_hash=canonical_objective.compute_objective_hash(),
            canonical_input_hash=parent_context.canonical_input_hash,
            status="COMPLETED",
            authority_level=parent_context.authority_level,
            status_history=parent_context.status_history,
            ended_at=datetime.now(timezone.utc).isoformat(),
        )

        return RouteExecutionResult(
            status="SUCCESS",
            parent_run_id=parent_context.run_id,
            route_plan_hash=plan.route_plan_hash,
            completed_step_ids=completed_steps,
            cached_step_ids=cached_steps,
            final_artifact_id=current_artifact_id,
            final_artifact_type=final_artifact_type,
            step_results=step_results,
        )

    @classmethod
    def resolve_escalation(
        cls,
        escalation_id: str,
        decision: Literal["APPROVED", "REJECTED", "OVERRIDDEN"],
        human_authority: str,
        operator_notes: str,
        parent_run_id: str,
        resulting_plan_hash: str,
        resumed_step_id: str,
        kernel_db: KernelDatabase,
    ) -> Dict[str, Any]:
        """
        Records human decision and transitions escalation to resolved state in SQLite.
        """
        approval_id = f"appr_{escalation_id}_{int(datetime.now(timezone.utc).timestamp())}"
        decision_payload = {
            "decision": decision,
            "operator_notes": operator_notes,
            "resolved_at": datetime.now(timezone.utc).isoformat(),
        }

        kernel_db.record_approval(
            approval_id=approval_id,
            escalation_id=escalation_id,
            parent_run_id=parent_run_id,
            human_authority=human_authority,
            decision=decision,
            decision_payload=decision_payload,
            resulting_plan_hash=resulting_plan_hash,
            resumed_step_id=resumed_step_id,
        )

        return {
            "status": f"RESOLVED_{decision}",
            "approval_id": approval_id,
            "escalation_id": escalation_id,
            "decision": decision,
            "resumed_step_id": resumed_step_id,
        }
