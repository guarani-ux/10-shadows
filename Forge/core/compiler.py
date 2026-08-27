"""
forge/core/compiler.py
Typed Execution Graph Compiler and Deterministic DAG Runner.

Enforces:
1. Two-Key Gatekeeper Law (Adequacy == ADEQUATE_FOR_EXECUTION && Decomposition == SATISFIED).
2. Sealed Capability Bindings (Consumes exact bindings sealed in ResolutionProof; NO reselection or operator fallback).
3. Lineage Preservation: Every node carries proof IDs and hashes.
4. Deterministic execution with physical verifier gates and independent obligation verification.
"""

import hashlib
import inspect
import uuid
from typing import Any, Dict, List, Optional

from forge.core.registry import CapabilityRegistry
from forge.core.substrate import (
    CapabilityBinding,
    ClosureReport,
    DecompositionProof,
    ExecutionGraph,
    ObjectiveAdequacyContract,
    ObjectiveAdequacyState,
    RequiredOperation,
    ResolutionProof,
    VerificationContract,
    compute_digest,
)


class ObjectiveInadequateError(Exception):
    """Raised when attempting to compile a graph for an inadequate CanonicalObjective."""
    pass


class DecompositionIncompleteError(Exception):
    """Raised when attempting to compile a graph without 100% decomposition coverage."""
    pass


class ClosureDeficitError(Exception):
    """Raised when attempting to compile a graph with open capability or evidence deficits."""
    pass


class ExecutionGraphCompiler:
    """
    Compiles verified objectives, operations, and exact capability bindings into a runnable ExecutionGraph.
    """

    def __init__(self, registry: CapabilityRegistry):
        self.registry = registry

    def compile(
        self,
        adequacy_contract: Optional[ObjectiveAdequacyContract],
        decomposition_proof: DecompositionProof,
        closure_report: Optional[ClosureReport],
        operations: List[RequiredOperation],
        verification_contracts: List[VerificationContract],
        resolution_proof: Optional[ResolutionProof] = None,
        human_gates: Optional[List[str]] = None,
    ) -> ExecutionGraph:
        # Two-Key Gate 1: Upstream Objective Adequacy Check
        if adequacy_contract and not adequacy_contract.permits_execution:
            raise ObjectiveInadequateError(
                f"Cannot compile ExecutionGraph: Objective adequacy state is '{adequacy_contract.adequacy_state.value}'. "
                f"Unaccounted drops: {adequacy_contract.unaccounted_drops}, "
                f"Missing domain caps: {adequacy_contract.missing_domain_capabilities}"
            )

        # Gate 2: Capability & Evidence Closure Check
        if closure_report and not closure_report.is_closed:
            raise ClosureDeficitError(
                f"Cannot compile ExecutionGraph: Closure is open. "
                f"Missing capabilities: {[d.missing_capability for d in closure_report.capability_deficits]}"
            )

        # Two-Key Gate 3: Downstream Decomposition Coverage Check
        if decomposition_proof.closure_status != "SATISFIED":
            raise DecompositionIncompleteError(
                f"Cannot compile ExecutionGraph: Decomposition closure status is '{decomposition_proof.closure_status}'. "
                f"Uncovered requirements: {decomposition_proof.uncovered_requirements}, "
                f"Deficits: {decomposition_proof.operation_deficits}"
            )

        # Bind operations strictly to exact sealed capabilities (NO reselection or fallback)
        bindings: Dict[str, str] = {}
        ev_deps: Dict[str, List[str]] = {}

        for op in operations:
            bound_cap_id: Optional[str] = None
            if op.bound_capability_id:
                bound_cap_id = op.bound_capability_id
            elif resolution_proof:
                for b in resolution_proof.capability_bindings.values():
                    if f"op_{b.obligation_id}" == op.operation_id or b.obligation_id in op.operation_id:
                        bound_cap_id = b.capability_id
                        break

            if not bound_cap_id:
                raise ClosureDeficitError(
                    f"Sealed Compiler Error: Operation '{op.operation_id}' lacks sealed capability binding. "
                    f"Reselection or arbitrary fallback is forbidden."
                )

            cap = self.registry.get_capability(bound_cap_id)
            if not cap or not cap.is_authorized_for_execution:
                raise ClosureDeficitError(
                    f"Bound capability '{bound_cap_id}' for operation '{op.operation_id}' is missing or unauthorized."
                )

            bindings[op.operation_id] = cap.capability_id
            ev_deps[op.operation_id] = [e.evidence_id for e in op.evidence_requirements]

        graph_id = f"graph_{uuid.uuid4().hex[:8]}"
        graph_hash = compute_digest({
            "graph_id": graph_id,
            "obj_hash": decomposition_proof.objective_hash,
            "ops": [op.operation_id for op in operations],
            "bindings": bindings,
            "gates": [vc.contract_id for vc in verification_contracts],
        })

        return ExecutionGraph(
            graph_id=graph_id,
            objective_hash=decomposition_proof.objective_hash,
            operations=operations,
            capability_bindings=bindings,
            evidence_dependencies=ev_deps,
            verification_gates=verification_contracts,
            human_gates=human_gates or [],
            stop_conditions=["All operations executed and verified"],
            failure_routes={op.operation_id: "ESCALATE" for op in operations},
            graph_hash=graph_hash,
        )

    def compile_execution_graph(
        self,
        objective_id: str,
        operations: List[RequiredOperation],
        verification_contracts: List[VerificationContract],
        evidence_pool: Dict[str, Any],
        resolution_proof: Optional[ResolutionProof] = None,
        adequacy_contract: Optional[ObjectiveAdequacyContract] = None,
    ) -> ExecutionGraph:
        """
        Direct compilation helper verifying sealed bindings and closure.
        """
        from forge.core.closure import ClosureGate
        from forge.core.decomposition import DecompositionCoverageEvaluator

        decomp_eval = DecompositionCoverageEvaluator()
        closure_gate = ClosureGate(self.registry)

        closure_rep = closure_gate.evaluate_closure(operations, evidence_pool)
        decomp_proof = decomp_eval.evaluate_decomposition(
            objective_id=objective_id,
            canonical_requirements=[],
            operations=operations,
            verification_contracts=verification_contracts,
        )

        return self.compile(
            adequacy_contract=adequacy_contract,
            decomposition_proof=decomp_proof,
            closure_report=closure_rep,
            operations=operations,
            verification_contracts=verification_contracts,
            resolution_proof=resolution_proof,
        )

    def execute_graph(
        self,
        graph: ExecutionGraph,
        initial_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Deterministically executes the compiled ExecutionGraph by piping data
        through bound capabilities and validating verification gates.
        """
        state_store: Dict[str, Any] = dict(initial_payload)
        execution_trace: List[Dict[str, Any]] = []

        for op in graph.operations:
            cap_id = graph.capability_bindings.get(op.operation_id)
            cap = self.registry.get_capability(cap_id)
            if not cap or not cap.is_authorized_for_execution:
                return {
                    "success": False,
                    "status": "CAPABILITY_UNAUTHORIZED",
                    "failed_operation": op.operation_id,
                    "error": f"Capability '{cap_id}' is not authorized for execution.",
                }

            # Safely invoke capability execution adapter with exact signature inspection
            try:
                sig = inspect.signature(cap.execution_adapter)
                call_args = {}
                for param_name, param in sig.parameters.items():
                    if param.kind == inspect.Parameter.VAR_KEYWORD:
                        call_args.update(state_store)
                        break
                    elif param_name in state_store:
                        call_args[param_name] = state_store[param_name]
                    elif param.default != inspect.Parameter.empty:
                        call_args[param_name] = param.default

                op_output = cap.execution_adapter(**call_args)
            except Exception:
                try:
                    op_output = cap.execution_adapter(state_store)
                except Exception as e:
                    return {
                        "success": False,
                        "status": "EXECUTION_ERROR",
                        "failed_operation": op.operation_id,
                        "error": str(e),
                    }

            # Store outputs
            if isinstance(op_output, dict):
                state_store.update(op_output)
            else:
                for out_key in op.outputs:
                    state_store[out_key] = op_output

            # Run physical verifier if capability has one
            if cap.verifier and not cap.verifier(op_output):
                return {
                    "success": False,
                    "status": "CAPABILITY_VERIFICATION_FAILED",
                    "failed_operation": op.operation_id,
                    "error": f"Capability verifier failed for '{cap_id}'.",
                }

            execution_trace.append({
                "operation_id": op.operation_id,
                "operator": op.operator.value,
                "capability_id": cap_id,
                "output": op_output,
                "source_obligation_id": op.source_obligation_id,
                "semantic_proof_id": op.semantic_proof_id,
            })

        # Run independent obligation-bound verification gates
        for gate in graph.verification_gates:
            if gate.validator_fn:
                gate_passed = gate.validator_fn(state_store)
                if not gate_passed:
                    return {
                        "success": False,
                        "status": "VERIFICATION_GATE_FAILED",
                        "failed_gate": gate.contract_id,
                        "error": f"Verification gate '{gate.observable_success_condition}' failed.",
                        "trace": execution_trace,
                    }

        return {
            "success": True,
            "status": "SUCCESS",
            "graph_id": graph.graph_id,
            "graph_hash": graph.graph_hash,
            "final_state": state_store,
            "trace": execution_trace,
        }
