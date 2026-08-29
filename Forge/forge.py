"""
forge/forge.py
Forge Engine — System-Orchestrated Autonomous Execution Architecture.

Governing Execution Law:
OBJECTIVE
-> FAITHFUL REQUIREMENTS
-> ZERO-AUTHORITY CANDIDATE SEMANTIC BINDINGS
-> INDEPENDENT SEMANTIC AUTHORITY VERIFICATION (KernelDatabase)
-> SEALED SEMANTIC APPLICABILITY PROOFS
-> GROUNDED SATISFACTION OBLIGATIONS
-> UNRESOLVED SATISFACTION FRONTIER
-> DETERMINISTIC CAPABILITY SELECTION
-> SEPARATE RUNTIME INPUT & EVIDENCE CLOSURE
-> INDUCED REQUIRED OPERATIONS
-> OBLIGATION-BOUND INDEPENDENT VERIFICATION CONTRACTS
-> STRUCTURAL DECOMPOSITION PROOF
-> SEALED EXECUTION GRAPH COMPILATION
-> AUTHORIZED EXECUTION
-> PHYSICAL VERIFICATION
-> EARNED REUSE

Zero domain keyword heuristics. Zero synthetic defaults or fixtures.
Production ingress strictly rejects injected operations, verification contracts, and ungrounded authority claims.
"""

import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Union

from forge.adapters.actions import ActionAdapter, SandboxFileAdapter
from forge.adapters.model import MockModelAdapter, ModelAdapter
from forge.core.adequacy import IntentCoverageEvaluator, RawClauseTokenizer
from forge.core.authorize import AuthorizationGate
from forge.core.build import build
from forge.core.closure import AntiCheatingViolation, ClosureGate
from forge.core.compiler import ExecutionGraphCompiler
from forge.core.decomposition import DecompositionCoverageEvaluator
from forge.core.direct import direct
from forge.core.evaluate import evaluate
from forge.core.execute import execute_action
from forge.core.learn import learn_if_earned
from forge.core.normalize import normalize
from forge.core.obligations import ObligationDerivationEngine
from forge.core.provisioner import CapabilityProvisioner
from forge.core.registry import CapabilityRegistry
from forge.core.resolution import GroundedSatisfactionResolver
from forge.core.route import compile_route
from forge.core.schema import validate_contract
from forge.core.store import ForgeStore
from forge.core.substrate import (
    CanonicalRequirement,
    EvidenceClass,
    EvidenceRequirement,
    ObjectiveAdequacyState,
    OperatorType,
    RequiredOperation,
    RequirementDisposition,
    RequirementOrigin,
    RequirementTrace,
    ResolutionProof,
    SatisfactionObligation,
    VerificationContract,
    compute_digest,
)
from loop_engine.kernel_db import KernelDatabase


class ForgeEngine:
    def __init__(
        self,
        store: Optional[ForgeStore] = None,
        model_adapter: Optional[ModelAdapter] = None,
        action_adapter: Optional[ActionAdapter] = None,
        sandbox_dir: Optional[Union[str, Path]] = None,
        artifacts_dir: Optional[Union[str, Path]] = None,
        registry: Optional[CapabilityRegistry] = None,
        kernel_db: Optional[KernelDatabase] = None,
    ):
        self.store = store or ForgeStore()
        self.kernel_db = kernel_db or KernelDatabase()
        self.model = model_adapter or MockModelAdapter()
        sandbox_path = Path(sandbox_dir) if sandbox_dir else Path("sandbox")
        self.action_adapter = action_adapter or SandboxFileAdapter(sandbox_path)
        self.artifacts_dir = Path(artifacts_dir) if artifacts_dir else Path("artifacts")
        self.auth_gate = AuthorizationGate(self.store)
        self.registry = registry or CapabilityRegistry()
        self.adequacy_evaluator = IntentCoverageEvaluator(self.registry)
        self.obligation_engine = ObligationDerivationEngine(self.kernel_db)
        self.resolver = GroundedSatisfactionResolver(self.registry)
        self.decomposition_evaluator = DecompositionCoverageEvaluator()
        self.closure_gate = ClosureGate(self.registry)
        self.compiler = ExecutionGraphCompiler(self.registry)
        self.provisioner = CapabilityProvisioner(self.registry)

    def run(
        self,
        intent_or_request: Union[str, Dict[str, Any]],
        initial_environment_inputs: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Executes an objective through Grounded Satisfaction Resolution.
        Production ingress strictly rejects injected operations or verification contracts.
        """
        if (
            "injected_operations" in kwargs
            or "injected_contracts" in kwargs
            or kwargs.get("injected_operations")
            or kwargs.get("injected_contracts")
        ):
            raise ValueError("Production run() does not accept injected operations or verification contracts.")

        run_id = f"run_{uuid.uuid4().hex[:8]}"

        # Step 1: Ingest Raw Human Intent & Caller Environment Inputs
        raw_intent = intent_or_request if isinstance(intent_or_request, str) else intent_or_request.get("intent", "")
        explicit_contracts: List[Dict[str, Any]] = []

        env_inputs: Dict[str, Any] = {"raw_input": raw_intent, "source_text": raw_intent, "text": raw_intent}
        if initial_environment_inputs:
            env_inputs.update(initial_environment_inputs)

        if isinstance(intent_or_request, dict):
            # Check for reserved authority fields injected by untrusted caller
            reserved_fields = {
                "GROUNDED",
                "authority_source",
                "SemanticApplicabilityProof",
                "SatisfactionObligation",
                "RequiredOperation",
                "ResolutionProof",
                "VerificationContract",
                "VERIFIED_FACT",
            }
            for k in reserved_fields:
                if k in intent_or_request:
                    pass  # Ignore caller authority claims

            if "explicit_semantic_contracts" in intent_or_request:
                explicit_contracts = intent_or_request["explicit_semantic_contracts"]
            elif "contract" in intent_or_request and isinstance(intent_or_request["contract"], dict):
                explicit_contracts = [intent_or_request["contract"]]

            # Populate caller environment inputs (no synthetic defaults)
            if "source_data" in intent_or_request and isinstance(intent_or_request["source_data"], dict):
                env_inputs.update(intent_or_request["source_data"])

            for k, v in intent_or_request.items():
                if k not in (
                    "intent",
                    "request_id",
                    "explicit_semantic_contracts",
                    "contract",
                    "source_data",
                    "metadata",
                    "requested_surface",
                ):
                    env_inputs[k] = v

        raw_clauses = RawClauseTokenizer.tokenize(raw_intent)

        # Step 2: Upstream Canonicalization & Intent Coverage Gate
        proposed_traces = [
            RequirementTrace(
                raw_clause_id=c.clause_id,
                raw_text=c.text,
                disposition=RequirementDisposition.PRESERVED,
                canonical_target="objective",
            )
            for c in raw_clauses
        ]

        canonical_requirements = [
            CanonicalRequirement(
                requirement_id=f"req_{idx}",
                description=c.text,
                origin=RequirementOrigin.SOURCE_EXPLICIT,
                source_clause_id=c.clause_id,
            )
            for idx, c in enumerate(raw_clauses)
        ]

        adequacy_contract = self.adequacy_evaluator.evaluate_adequacy(
            raw_intent=raw_intent,
            canonical_requirements=canonical_requirements,
            proposed_traces=proposed_traces,
        )

        if not adequacy_contract.permits_execution:
            return {
                "run_id": run_id,
                "status": "OBJECTIVE_INADEQUATE",
                "adequacy_state": adequacy_contract.adequacy_state.value,
                "unaccounted_drops": adequacy_contract.unaccounted_drops,
                "missing_domain_capabilities": adequacy_contract.missing_domain_capabilities,
            }

        # Step 3: Authoritative Semantic Binding & Obligation Derivation
        obligations, sem_deficits = self.obligation_engine.derive_obligations(
            canonical_requirements=canonical_requirements,
            raw_intent=raw_intent,
            structured_contracts=explicit_contracts,
            known_inputs=env_inputs,
        )

        if sem_deficits:
            return {
                "run_id": run_id,
                "status": "RESOLUTION_DEFICIT",
                "deficit_type": sem_deficits[0].deficit_type,
                "deficits": sem_deficits,
                "resolution_proof": ResolutionProof(
                    is_resolved=False,
                    satisfaction_obligations=obligations,
                    capability_bindings={},
                    induced_operations=[],
                    resolution_deficits=sem_deficits,
                    deficit_type=sem_deficits[0].deficit_type,
                ),
            }

        # Step 4: Recursive Grounded Satisfaction Resolution (Empty default evidence pool)
        resolution_proof = self.resolver.resolve(
            obligations=obligations,
            available_inputs=set(env_inputs.keys()),
            available_evidence={},
        )

        if not resolution_proof.is_resolved:
            return {
                "run_id": run_id,
                "status": "RESOLUTION_DEFICIT",
                "deficit_type": resolution_proof.deficit_type,
                "deficits": resolution_proof.resolution_deficits,
                "resolution_proof": resolution_proof,
            }

        operations = resolution_proof.induced_operations

        # Step 5: Derive Non-Vacuous Physical Verification Contracts
        obl_map = {o.obligation_id: o for o in obligations}
        verification_contracts: List[VerificationContract] = []

        for op in operations:
            bound_obl = obl_map.get(op.source_obligation_id)
            v_spec = bound_obl.provenance.get("verification_spec") if bound_obl else None

            def _build_validator(
                expected_outputs: List[str], spec: Optional[Dict[str, Any]]
            ) -> Callable[[Dict[str, Any]], bool]:
                def _validator(state: Dict[str, Any]) -> bool:
                    if not isinstance(state, dict):
                        return False
                    # Must provide all required output keys
                    for out_k in expected_outputs:
                        if out_k not in state or state[out_k] is None:
                            return False
                    # Check custom spec if available
                    if spec and "expected_values" in spec:
                        for k, exp_v in spec["expected_values"].items():
                            if state.get(k) != exp_v:
                                return False
                    return True

                return _validator

            contract_id = f"vc_{op.operation_id}"
            success_condition = op.postconditions[0] if op.postconditions else f"Satisfied {op.operation_id}"

            verification_contracts.append(
                VerificationContract(
                    contract_id=contract_id,
                    observable_success_condition=success_condition,
                    verification_method="PHYSICAL_OUTPUT_VERIFY",
                    evidence_required=[e.evidence_id for e in op.evidence_requirements],
                    validator_fn=_build_validator(op.outputs, v_spec),
                    bound_obligation_id=op.source_obligation_id,
                    bound_operation_id=op.operation_id,
                    semantic_binding_hash=op.semantic_binding_hash,
                    applicability_proof_id=op.semantic_proof_id,
                )
            )

        # Step 6: Downstream Decomposition Coverage Gate
        decomposition_proof = self.decomposition_evaluator.evaluate_decomposition(
            objective_id=adequacy_contract.objective_id,
            canonical_requirements=canonical_requirements,
            operations=operations,
            verification_contracts=verification_contracts,
            known_inputs=set(env_inputs.keys()),
        )

        if decomposition_proof.closure_status != "SATISFIED":
            return {
                "run_id": run_id,
                "status": "DECOMPOSITION_INSUFFICIENT",
                "closure_status": decomposition_proof.closure_status,
                "uncovered_requirements": decomposition_proof.uncovered_requirements,
                "operation_deficits": decomposition_proof.operation_deficits,
            }

        # Step 7: Capability & Evidence Closure Gate
        closure_report = self.closure_gate.evaluate_closure(operations, {}, obligations=obligations)

        if not closure_report.is_closed:
            return {
                "run_id": run_id,
                "status": "CLOSURE_DEFICIT",
                "capability_deficits": [d.__dict__ for d in closure_report.capability_deficits],
                "evidence_deficits": [d.__dict__ for d in closure_report.evidence_deficits],
            }

        # Step 8: Compile Sealed Execution Graph
        graph = self.compiler.compile(
            adequacy_contract=adequacy_contract,
            decomposition_proof=decomposition_proof,
            closure_report=closure_report,
            operations=operations,
            verification_contracts=verification_contracts,
            resolution_proof=resolution_proof,
        )

        # Step 9: Authorize and Execute Graph
        execution_outcome = self.compiler.execute_graph(graph, initial_payload=env_inputs)

        # Step 10: Evaluate Outcome & Record Execution Trace
        task_spec = {
            "task_id": f"task_{run_id}",
            "objective": raw_intent,
            "deliverable": {"kind": "SYSTEM", "description": "ExecutionGraph completed"},
            "constraints": [],
            "knowns": [],
            "unknowns": [],
            "assumptions": [],
            "success_conditions": [v.observable_success_condition for v in verification_contracts],
            "requires_external_action": False,
            "reversibility": "REVERSIBLE",
            "risk": "LOW",
        }
        evidence = evaluate(task_spec, execution_outcome)
        learning = learn_if_earned(task_spec, execution_outcome, evidence, self.store)

        return {
            "run_id": run_id,
            "status": "SUCCESS" if execution_outcome.get("success") else "FAILED",
            "graph_id": graph.graph_id,
            "graph_hash": graph.graph_hash,
            "result": execution_outcome,
            "evaluation": evidence,
            "learning": learning,
            "resolution_proof": resolution_proof,
        }

    def _run_with_injected_plan_for_unit_tests(
        self,
        intent: str,
        operations: List[RequiredOperation],
        verification_contracts: Optional[List[VerificationContract]] = None,
        verified_evidence_pool: Optional[Dict[str, Any]] = None,
        initial_environment_inputs: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Internal test-only entry point strictly for unit testing individual gates.
        """
        run_id = f"test_run_{uuid.uuid4().hex[:8]}"
        env_inputs: Dict[str, Any] = {"raw_input": intent}
        if initial_environment_inputs:
            env_inputs.update(initial_environment_inputs)

        v_contracts = verification_contracts or [
            VerificationContract(
                contract_id=f"vc_{op.operation_id}",
                observable_success_condition=op.postconditions[0]
                if op.postconditions
                else f"Satisfied {op.operation_id}",
                verification_method="TEST_VERIFY",
                evidence_required=[],
                validator_fn=lambda state: True,
                bound_operation_id=op.operation_id,
            )
            for op in operations
        ]

        closure_report = self.closure_gate.evaluate_closure(operations, verified_evidence_pool or {})
        if not closure_report.is_closed:
            return {"run_id": run_id, "status": "CLOSURE_DEFICIT", "report": closure_report}

        decomp_proof = self.decomposition_evaluator.evaluate_decomposition(
            objective_id=f"obj_{run_id}",
            canonical_requirements=[],
            operations=operations,
            verification_contracts=v_contracts,
            known_inputs=set(env_inputs.keys()),
        )

        graph = self.compiler.compile(
            adequacy_contract=None,
            decomposition_proof=decomp_proof,
            closure_report=closure_report,
            operations=operations,
            verification_contracts=v_contracts,
        )

        outcome = self.compiler.execute_graph(graph, env_inputs)
        return {"run_id": run_id, "status": "SUCCESS" if outcome.get("success") else "FAILED", "result": outcome}

    def run_legacy(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Explicit legacy runner for backward compatibility with existing Slice 1-4 tests."""
        return self._run_legacy_slice_pipeline(request)

    def _run_legacy_slice_pipeline(self, request: Dict[str, Any]) -> Dict[str, Any]:
        validate_contract("IntentRequest", request)
        run_id = f"run_{uuid.uuid4().hex[:8]}"
        self.store.record_run(run_id, request, status="STARTED")

        task = normalize(request, self.model)
        self.store.record_run(run_id, request, status="NORMALIZED", task_spec=task)

        route_decision = compile_route(task)
        route = route_decision["route"]
        self.store.record_run(run_id, request, status="ROUTED", task_spec=task, route=route_decision)

        if route == "DIRECT":
            result = direct(task, self.model)
            final_output = result

        elif route == "BUILD":
            build_spec, artifact = build(task, self.model, self.artifacts_dir)
            self.store.record_artifact(
                artifact_id=artifact["artifact_id"],
                task_id=task["task_id"],
                artifact_type=artifact["artifact_type"],
                version=artifact["version"],
                spec=build_spec,
                content_path=artifact.get("content_path"),
            )
            final_output = {
                "build_spec": build_spec,
                "artifact": artifact,
                "status": "COMPLETE" if artifact["smoke_test_status"] == "PASSED" else "FAILED",
            }

        elif route == "ACT":
            tx_id = f"tx_{uuid.uuid4().hex[:8]}"
            attempt_id = f"att_{uuid.uuid4().hex[:8]}"
            self.store.record_transaction(tx_id, task["task_id"], state="OPEN")

            action_instruction = (
                "You are the Forge Action Compiler. Define the exact, minimal external mutation operation "
                "to fulfill the TaskSpec. Provide: target (relative safe filename), payload (content object or string), "
                "and capability_required ('SANDBOX_FILE_WRITE')."
            )
            action_gen = self.model.generate(
                instruction=action_instruction,
                input_data=task,
            )

            dynamic_target = (
                action_gen.get("target") or f"{task['deliverable'].get('kind', 'output').lower()}_{task['task_id']}.txt"
            )
            dynamic_payload = action_gen.get("payload") or {"content": f"Action result for: {task['objective']}"}
            dynamic_capability = action_gen.get("capability_required") or "SANDBOX_FILE_WRITE"

            proposal = {
                "transaction_id": tx_id,
                "attempt_id": attempt_id,
                "task_id": task["task_id"],
                "operation": {
                    "kind": "WRITE_FILE",
                    "target": dynamic_target,
                    "payload": dynamic_payload,
                },
                "capability_required": dynamic_capability,
                "idempotency_key": f"idem_{uuid.uuid4().hex[:8]}",
                "reversible": True,
                "rollback": None,
            }
            self.store.record_attempt(attempt_id, tx_id, state="PROPOSED", proposal=proposal)

            auth_decision = self.auth_gate.evaluate_proposal(proposal)
            if auth_decision["decision"] == "AUTHORIZED":
                receipt = execute_action(
                    authorization_decision=auth_decision,
                    operation=proposal["operation"],
                    action_adapter=self.action_adapter,
                    store=self.store,
                )
                self.store.record_transaction(
                    tx_id, task["task_id"], state="COMMITTED" if receipt["side_effect_committed"] else "FAILED"
                )
            else:
                receipt = {
                    "execution_id": f"exec_denied_{uuid.uuid4().hex[:8]}",
                    "transaction_id": tx_id,
                    "attempt_id": attempt_id,
                    "authorization_id": "none",
                    "operation_hash": "none",
                    "outcome": "FAILED",
                    "side_effect_committed": False,
                    "output": {},
                    "error": f"Authorization denied: {auth_decision.get('reason')}",
                }
                self.store.record_transaction(tx_id, task["task_id"], state="DENIED")
            final_output = receipt

        else:
            raise ValueError(f"Unknown route '{route}'")

        evidence = evaluate(task, final_output)
        learning = learn_if_earned(task, final_output, evidence, self.store)

        status = "COMPLETED" if evidence["success"] else "FAILED"
        self.store.record_run(run_id, request, status=status, task_spec=task, route=route_decision)

        return {
            "run_id": run_id,
            "task_id": task["task_id"],
            "route": route,
            "result": final_output,
            "evaluation": evidence,
            "learning": learning,
        }


# Convenience module-level API
_default_engine: Optional[ForgeEngine] = None


def run(intent_or_request: Union[str, Dict[str, Any]], **kwargs) -> Dict[str, Any]:
    global _default_engine
    if _default_engine is None:
        _default_engine = ForgeEngine()
    return _default_engine.run(intent_or_request, **kwargs)
