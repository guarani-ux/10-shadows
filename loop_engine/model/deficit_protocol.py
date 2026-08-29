"""
loop_engine/model/deficit_protocol.py
First-Class Deficit Protocol & Resolution Loop for 10 SHADOWS.

Enables models and verifiers to declare missing capabilities, knowledge, or evidence
rather than bluffing or hallucinating. Closes the deficit loop through deterministic
system-side provisioning and context recompilation without consuming strike budgets.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from pydantic import BaseModel, Field

from loop_engine.model.boundary import (
    DeficitDeclaration,
    DeficitType,
    ModelAdapter,
    ModelRequest,
    ModelResponse,
)
from loop_engine.model.context_compiler import CompiledContext, ContextCompiler


class DeficitProvisionResult(BaseModel):
    """
    Result of attempting to provision a declared deficit.
    """

    deficit: DeficitDeclaration
    is_resolved: bool
    provisioned_data: Optional[Dict[str, Any]] = None
    message: str = ""


class DeficitResolver(abc.ABC):
    """
    Abstract interface for provisioning declared deficits.
    """

    @abc.abstractmethod
    def can_resolve(self, deficit: DeficitDeclaration) -> bool:
        """Returns True if this resolver can satisfy the declared deficit."""
        pass

    @abc.abstractmethod
    def resolve(self, deficit: DeficitDeclaration) -> DeficitProvisionResult:
        """Provisions the requested knowledge, evidence, or capability."""
        pass


class InProcessDeficitResolver(DeficitResolver):
    """
    Configurable in-process resolver for knowledge, evidence, tools, and domain rules.
    """

    def __init__(
        self,
        knowledge_base: Optional[Dict[str, Any]] = None,
        tool_registry: Optional[Dict[str, Any]] = None,
        evidence_store: Optional[Dict[str, Any]] = None,
    ):
        self.knowledge_base = knowledge_base or {}
        self.tool_registry = tool_registry or {}
        self.evidence_store = evidence_store or {}

    def can_resolve(self, deficit: DeficitDeclaration) -> bool:
        if deficit.deficit_type == DeficitType.MISSING_KNOWLEDGE:
            key = deficit.required_provision or deficit.target_subject
            return bool(key and key in self.knowledge_base)
        elif deficit.deficit_type == DeficitType.MISSING_CAPABILITY:
            key = deficit.required_provision or deficit.target_subject
            return bool(key and key in self.tool_registry)
        elif deficit.deficit_type == DeficitType.MISSING_EVIDENCE:
            key = deficit.required_provision or deficit.target_subject
            return bool(key and key in self.evidence_store)
        return False

    def resolve(self, deficit: DeficitDeclaration) -> DeficitProvisionResult:
        key = deficit.required_provision or deficit.target_subject or ""
        if deficit.deficit_type == DeficitType.MISSING_KNOWLEDGE:
            data = self.knowledge_base.get(key)
            if data:
                return DeficitProvisionResult(
                    deficit=deficit,
                    is_resolved=True,
                    provisioned_data={"domain_knowledge": {key: data}},
                    message=f"Provisioned domain knowledge for '{key}'.",
                )
        elif deficit.deficit_type == DeficitType.MISSING_CAPABILITY:
            tool = self.tool_registry.get(key)
            if tool:
                return DeficitProvisionResult(
                    deficit=deficit,
                    is_resolved=True,
                    provisioned_data={"available_tools": [tool]},
                    message=f"Provisioned capability '{key}'.",
                )
        elif deficit.deficit_type == DeficitType.MISSING_EVIDENCE:
            ev = self.evidence_store.get(key)
            if ev:
                return DeficitProvisionResult(
                    deficit=deficit,
                    is_resolved=True,
                    provisioned_data={"verified_evidence": [ev]},
                    message=f"Provisioned verified evidence for '{key}'.",
                )

        return DeficitProvisionResult(
            deficit=deficit,
            is_resolved=False,
            message=f"Unable to provision deficit of type {deficit.deficit_type.value}.",
        )


class DeficitResolutionLoop:
    """
    Coordinates model candidate execution with automatic deficit detection,
    system-side provisioning, context recompilation, and retry.
    """

    def __init__(
        self,
        context_compiler: ContextCompiler,
        resolver: DeficitResolver,
        max_deficit_cycles: int = 3,
    ):
        self.context_compiler = context_compiler
        self.resolver = resolver
        self.max_deficit_cycles = max_deficit_cycles

    def run_with_deficit_resolution(
        self,
        adapter: ModelAdapter,
        base_request: ModelRequest,
        objective: Any,
        initial_context_kwargs: Optional[Dict[str, Any]] = None,
    ) -> Tuple[ModelResponse, int, List[DeficitProvisionResult]]:
        """
        Executes generation against the model. If deficits are declared,
        attempts resolution, recompiles context, and retries.
        Returns: (final_response, resolution_cycles, provision_history).
        """
        context_kwargs = dict(initial_context_kwargs or {})
        history: List[DeficitProvisionResult] = []
        cycles = 0

        # Initial compile
        compiled = self.context_compiler.compile(objective=objective, **context_kwargs)
        current_request = base_request.model_copy(deep=True)
        current_request.compiled_context = compiled.to_dict()

        while cycles < self.max_deficit_cycles:
            response = adapter.execute(current_request)
            if not response.declared_deficits:
                # No deficits declared; return response directly
                return response, cycles, history

            # Deficit detected! Attempt system-side provisioning
            resolved_any = False
            unresolved_deficits = []

            for deficit in response.declared_deficits:
                if self.resolver.can_resolve(deficit):
                    prov = self.resolver.resolve(deficit)
                    history.append(prov)
                    if prov.is_resolved and prov.provisioned_data:
                        resolved_any = True
                        # Merge provisioned data into context kwargs
                        if "domain_knowledge" in prov.provisioned_data:
                            existing_k = context_kwargs.get("domain_knowledge") or {}
                            existing_k.update(prov.provisioned_data["domain_knowledge"])
                            context_kwargs["domain_knowledge"] = existing_k
                        if "available_tools" in prov.provisioned_data:
                            existing_t = list(context_kwargs.get("available_tools") or [])
                            existing_t.extend(prov.provisioned_data["available_tools"])
                            context_kwargs["available_tools"] = existing_t
                        if "verified_evidence" in prov.provisioned_data:
                            existing_e = list(context_kwargs.get("verified_evidence") or [])
                            existing_e.extend(prov.provisioned_data["verified_evidence"])
                            context_kwargs["verified_evidence"] = existing_e
                else:
                    unresolved_deficits.append(deficit)

            if not resolved_any:
                # Cannot resolve remaining deficits; return response with unresolved deficits
                return response, cycles, history

            # Recompile context with provisioned information
            cycles += 1
            context_kwargs["declared_deficits"] = unresolved_deficits
            compiled = self.context_compiler.compile(objective=objective, **context_kwargs)
            current_request.compiled_context = compiled.to_dict()
            current_request.unresolved_deficits = unresolved_deficits

        # Return last response after max cycles
        response = adapter.execute(current_request)
        return response, cycles, history
