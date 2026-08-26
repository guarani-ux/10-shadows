from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field
from loop_engine.context import RunContext


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
    or unresolvable merge/fact conflict halts automated execution.
    """
    escalation_id: str
    run_id: str
    task_id: str
    shadow_id: int
    reason: str
    category: Literal[
        "UNRESOLVED_FACTUAL_CONFLICT",
        "MISSING_EVIDENCE",
        "EXTERNAL_PUBLICATION_APPROVAL",
        "DESTRUCTIVE_FILE_MUTATION",
        "MERGE_CONFLICT",
        "AMBIGUOUS_AUDIENCE_OBJECTIVE",
        "SECURITY_SENSITIVE_ACTION",
    ]
    details: Dict[str, Any] = Field(default_factory=dict)
    remediation_options: List[str] = Field(default_factory=list)


class BoundedShadowRouter:
    """
    Shadow Routing & Capability Orchestrator.
    
    Inspects canonical objectives, determines required Shadow domains,
    orders them by dependency DAG, and creates an auditable execution route.
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
        """
        Determines the minimal, necessary subset of Shadows to fulfill the objective.
        """
        obj_type = objective.get("type", "unknown")
        task_id = objective.get("task_id", "task_routed")
        run_id = f"route_{task_id}"

        selected_ids: List[int] = []
        selected_codes: List[str] = []
        excluded_ids: List[int] = []
        exclusion_reasons: Dict[int, str] = {}
        expected_artifacts: List[str] = []
        verification_gates: List[str] = []
        escalation_conditions: List[str] = [
            "Missing verified evidence in CanonicalMediaBrief",
            "Merge conflict in Warden worktree",
            "Strike ceiling exceeded (3 strikes)",
        ]

        if obj_type == "av_production":
            # Flow: Scout/Scribe -> Herald -> Slicer -> Warden -> Game Master
            selected_ids = [6, 3, 7, 8, 10]
            selected_codes = ["scribe", "herald", "slicer", "warden", "gamemaster"]
            expected_artifacts = ["canonical_brief.json", "master_av_script.md", "task_dag.json", "wal_receipt.json"]
            verification_gates = ["AntiAILinguisticGuard", "CinematographyValidator", "DeterministicScriptValidator"]
        elif obj_type == "self_healing":
            # Flow: Alchemist -> Warden -> svris -> Game Master
            selected_ids = [9, 8, 2, 10]
            selected_codes = ["alchemist", "warden", "svris", "gamemaster"]
            expected_artifacts = ["crash_diagnostic.json", "surgical_patch.json", "wal_receipt.json"]
            verification_gates = ["ASTSyntaxGate", "IsolatedPytestGate"]
        else:
            # Default single Shadow execution
            selected_ids = [3, 8, 10]
            selected_codes = ["herald", "warden", "gamemaster"]
            expected_artifacts = ["av_script.json", "wal_receipt.json"]
            verification_gates = ["DeterministicScriptValidator"]

        all_shadow_ids = set(range(1, 11))
        excluded_ids = sorted(list(all_shadow_ids - set(selected_ids)))
        for s_id in excluded_ids:
            exclusion_reasons[s_id] = f"Shadow {s_id} not required for objective type '{obj_type}'."

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
