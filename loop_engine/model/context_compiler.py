"""
loop_engine/model/context_compiler.py
Deterministic Context Compiler for 10 SHADOWS.

Provisions the minimum sufficient cognitive environment for an operation.
Preserves strict authority classes (Authoritative, State, Procedure, Memory, Tools, Uncertainty).
Guarantees deterministic compilation without arbitrary context stuffing or hallucinated authority promotion.
"""

from __future__ import annotations

from enum import Enum
import hashlib
import json
from typing import Any, Dict, List, Optional, Sequence, Union
from pydantic import BaseModel, Field

from loop_engine.canonical_objective import CanonicalObjective
from loop_engine.capability import CapabilityContract
from loop_engine.context import RunContext
from loop_engine.model.boundary import DeficitDeclaration, DeficitType


class ContextClass(str, Enum):
    AUTHORITATIVE = "AUTHORITATIVE"  # Invariants, constraints, verified evidence, governance
    STATE = "STATE"                  # Execution state, attempt, stage, unresolved obligations
    PROCEDURE = "PROCEDURE"          # Applicable skills, externalized engineering methodologies
    MEMORY = "MEMORY"                # Distilled failure signatures, negative constraints, prior capabilities
    TOOLS = "TOOLS"                  # Available action surfaces, schemas, contracts
    UNCERTAINTY = "UNCERTAINTY"      # Missing facts, ungrounded requirements, declared deficits


class CompiledContext(BaseModel):
    """
    Structured, authority-preserved cognitive context emitted by ContextCompiler.
    """
    context_digest: str
    authoritative: Dict[str, Any] = Field(default_factory=dict)
    state: Dict[str, Any] = Field(default_factory=dict)
    procedure: Dict[str, Any] = Field(default_factory=dict)
    memory: Dict[str, Any] = Field(default_factory=dict)
    tools: Dict[str, Any] = Field(default_factory=dict)
    uncertainty: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serializes compiled context grouped by explicit authority classes."""
        return {
            "AUTHORITATIVE": self.authoritative,
            "STATE": self.state,
            "PROCEDURE": self.procedure,
            "MEMORY": self.memory,
            "TOOLS": self.tools,
            "UNCERTAINTY": self.uncertainty,
        }

    def compute_digest(self) -> str:
        """Computes deterministic cryptographic hash of the compiled context."""
        canonical_json = json.dumps(self.to_dict(), sort_keys=True, default=str)
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


class ContextCompiler:
    """
    Deterministic context compilation engine.
    Assembles minimal sufficient context without leaking unverified model outputs into fact.
    """
    def __init__(
        self,
        governance_rules: Optional[Dict[str, Any]] = None,
        procedures_registry: Optional[Dict[str, Any]] = None,
    ):
        self.governance_rules = governance_rules or {}
        self.procedures_registry = procedures_registry or {}

    def compile(
        self,
        objective: Union[str, CanonicalObjective, Dict[str, Any]],
        run_context: Optional[RunContext] = None,
        constraints: Optional[Sequence[str]] = None,
        verified_evidence: Optional[Sequence[Dict[str, Any]]] = None,
        applicable_procedure: Optional[str] = None,
        failure_history: Optional[Sequence[Dict[str, Any]]] = None,
        available_tools: Optional[Sequence[Union[str, CapabilityContract]]] = None,
        declared_deficits: Optional[Sequence[DeficitDeclaration]] = None,
        unresolved_unknowns: Optional[Sequence[str]] = None,
        domain_knowledge: Optional[Dict[str, Any]] = None,
    ) -> CompiledContext:
        """
        Compiles distinct information sources into their respective authority classes.
        """
        # 1. Authoritative Class (Invariants, grounded constraints, verified evidence)
        authoritative: Dict[str, Any] = {}
        if isinstance(objective, CanonicalObjective):
            authoritative["objective_id"] = objective.objective_id
            authoritative["description"] = objective.description
            authoritative["desired_outcome"] = objective.desired_outcome
            authoritative["forbidden_actions"] = list(objective.forbidden_actions)
            authoritative["verified_evidence"] = [e.model_dump() if hasattr(e, "model_dump") else e for e in objective.verified_evidence]
        elif isinstance(objective, dict):
            authoritative["objective"] = objective.get("objective") or objective.get("intent", "")
            authoritative["constraints"] = list(objective.get("constraints", []))
            authoritative["success_conditions"] = list(objective.get("success_conditions", []))
            if "verified_evidence" in objective:
                authoritative["verified_evidence"] = objective["verified_evidence"]
        else:
            authoritative["objective"] = str(objective)
            authoritative["constraints"] = list(constraints or [])

        if constraints and "constraints" not in authoritative:
            authoritative["constraints"] = list(constraints)
        if verified_evidence:
            authoritative["verified_evidence"] = list(verified_evidence)
        if self.governance_rules:
            authoritative["governance_rules"] = self.governance_rules
        if domain_knowledge:
            authoritative["knowledge"] = domain_knowledge


        # 2. State Class (Execution status, run_id, attempt number, strike number)
        state: Dict[str, Any] = {}
        if run_context:
            state["run_id"] = run_context.run_id
            state["task_id"] = run_context.task_id
            state["attempt_number"] = run_context.attempt_number
            state["strike_number"] = run_context.strike_number
            state["stage"] = run_context.stage
            state["source_commit"] = run_context.source_commit
        else:
            state["attempt_number"] = 1
            state["stage"] = "INITIALIZED"

        # 3. Procedure Class (Externalized engineering methodologies)
        procedure: Dict[str, Any] = {}
        if applicable_procedure:
            if applicable_procedure in self.procedures_registry:
                procedure["name"] = applicable_procedure
                procedure["methodology"] = self.procedures_registry[applicable_procedure]
            else:
                procedure["name"] = applicable_procedure
                procedure["methodology"] = f"Execute standard procedure for {applicable_procedure}"

        # 4. Memory Class (Distilled failure signatures, negative constraints, prior capabilities)
        memory: Dict[str, Any] = {}
        if failure_history:
            # Distill failure history without dumping raw verbose logs
            distilled_failures = []
            negative_constraints = set()
            for entry in failure_history:
                sig = entry.get("failure_signature") or entry.get("signature") or "UNKNOWN_SIG"
                cls = entry.get("classification") or entry.get("failure_classification") or "UNSPECIFIED"
                distilled_failures.append({
                    "signature": sig,
                    "classification": str(cls),
                    "root_cause": entry.get("root_cause", "Unspecified error trace"),
                })
                # Add negative constraint if available
                if "negative_constraint" in entry:
                    negative_constraints.add(entry["negative_constraint"])
                elif "failed_pattern" in entry:
                    negative_constraints.add(f"DO NOT REPEAT: {entry['failed_pattern']}")

            memory["failure_feedback"] = distilled_failures
            if negative_constraints:
                memory["negative_constraints"] = list(negative_constraints)

        # 5. Tools & Capabilities Class
        tools: Dict[str, Any] = {}
        if available_tools:
            tool_list = []
            for t in available_tools:
                if isinstance(t, CapabilityContract):
                    tool_list.append({
                        "capability_id": t.capability_id,
                        "domain": t.domain,
                        "supported_objective_types": list(t.supported_objective_types),
                    })
                else:
                    tool_list.append({"capability_id": str(t)})
            tools["available_capabilities"] = tool_list

        # 6. Uncertainty Class (Explicit deficits, unknown facts)
        uncertainty: Dict[str, Any] = {}
        if declared_deficits:
            uncertainty["declared_deficits"] = [
                d.model_dump() if hasattr(d, "model_dump") else d for d in declared_deficits
            ]

        if unresolved_unknowns:
            uncertainty["unresolved_unknowns"] = list(unresolved_unknowns)

        compiled = CompiledContext(
            context_digest="",
            authoritative=authoritative,
            state=state,
            procedure=procedure,
            memory=memory,
            tools=tools,
            uncertainty=uncertainty,
        )
        compiled.context_digest = compiled.compute_digest()
        return compiled
