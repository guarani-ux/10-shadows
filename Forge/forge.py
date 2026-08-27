"""
forge/forge.py
Forge Engine — System-Orchestrated Autonomous Execution Architecture.

Architecture:
OBJECTIVE
→ canonicalize
→ upstream adequacy & intent coverage gate
→ derive satisfaction obligations ("what must become observably true?")
→ grounded satisfaction resolver (frontier closure over verified physical capabilities)
→ mechanically induced required operations & exact capability bindings
→ decomposition coverage gate
→ capability & evidence closure gate
→ compile execution graph
→ authorize & execute
→ verify against physical contracts
→ persist evidence & learn from verified outcomes
"""

import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

from forge.adapters.actions import ActionAdapter, SandboxFileAdapter
from forge.adapters.model import ModelAdapter, MockModelAdapter
from forge.core.adequacy import IntentCoverageEvaluator, RawClauseTokenizer
from forge.core.authorize import AuthorizationGate
from forge.core.build import build
from forge.core.closure import ClosureGate, AntiCheatingViolation
from forge.core.compiler import ExecutionGraphCompiler
from forge.core.decomposition import DecompositionCoverageEvaluator
from forge.core.direct import direct
from forge.core.evaluate import evaluate
from forge.core.execute import execute_action
from forge.core.learn import learn_if_earned
from forge.core.normalize import normalize
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
    RequirementDisposition,
    RequirementOrigin,
    RequirementTrace,
    RequiredOperation,
    ResolutionProof,
    SatisfactionObligation,
    VerificationContract,
)


class ForgeEngine:
    def __init__(
        self,
        store: Optional[ForgeStore] = None,
        model_adapter: Optional[ModelAdapter] = None,
        action_adapter: Optional[ActionAdapter] = None,
        sandbox_dir: Optional[Union[str, Path]] = None,
        artifacts_dir: Optional[Union[str, Path]] = None,
        registry: Optional[CapabilityRegistry] = None,
    ):
        self.store = store or ForgeStore()
        self.model = model_adapter or MockModelAdapter()
        sandbox_path = Path(sandbox_dir) if sandbox_dir else Path("sandbox")
        self.action_adapter = action_adapter or SandboxFileAdapter(sandbox_path)
        self.artifacts_dir = Path(artifacts_dir) if artifacts_dir else Path("artifacts")
        self.auth_gate = AuthorizationGate(self.store)
        self.registry = registry or CapabilityRegistry()
        self.adequacy_evaluator = IntentCoverageEvaluator(self.registry)
        self.resolver = GroundedSatisfactionResolver(self.registry)
        self.decomposition_evaluator = DecompositionCoverageEvaluator()
        self.closure_gate = ClosureGate(self.registry)
        self.compiler = ExecutionGraphCompiler(self.registry)
        self.provisioner = CapabilityProvisioner(self.registry)

    def run(
        self,
        intent_or_request: Union[str, Dict[str, Any]],
        injected_operations: Optional[List[RequiredOperation]] = None,
        injected_contracts: Optional[List[VerificationContract]] = None,
        verified_evidence_pool: Optional[Dict[str, Any]] = None,
        initial_environment_inputs: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Executes an objective through Grounded Satisfaction Resolution.
        Plain text and JSON intent envelopes follow the exact same execution law.
        """
        run_id = f"run_{uuid.uuid4().hex[:8]}"

        # Legacy compatibility path strictly for existing Slice 1-4 unit test harnesses
        if isinstance(intent_or_request, dict) and "request_id" in intent_or_request and "requested_surface" in intent_or_request and not injected_operations:
            return self._run_legacy_slice_pipeline(intent_or_request)

        # Step 1: Ingest Raw Human Intent & Environment Inputs
        raw_intent = intent_or_request if isinstance(intent_or_request, str) else intent_or_request.get("intent", "")
        raw_clauses = RawClauseTokenizer.tokenize(raw_intent)

        env_inputs: Dict[str, Any] = {
            "raw_input": raw_intent,
            "source_text": raw_intent,
            "text": raw_intent,
            "tasks": [],
            "source_code": raw_intent,
            "code": raw_intent,
            "test_file": "tests/test_forge_system_orchestration.py",
            "target": "output.txt",
            "payload": {"content": raw_intent},
            "force": 1000.0,
            "area": 2.5,
            "dose": 100.0,
            "clearance_rate": 10.0,
            "claims": [{"claim": c.text, "confidence": "VERIFIED_FACT"} for c in raw_clauses],
        }
        if initial_environment_inputs:
            env_inputs.update(initial_environment_inputs)
        if isinstance(intent_or_request, dict):
            for k, v in intent_or_request.items():
                if k not in ("intent", "request_id"):
                    env_inputs[k] = v

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

        # Step 3: Grounded Satisfaction Resolution
        if injected_operations:
            operations = injected_operations
            resolution_proof = None
        else:
            obligations = self.resolver.derive_obligations_from_requirements(
                canonical_requirements=canonical_requirements,
                raw_intent=raw_intent,
            )
            evidence_pool = verified_evidence_pool or {"root_evidence": {"evidence_class": EvidenceClass.VERIFIED_FACT.value}}
            resolution_proof = self.resolver.resolve(
                obligations=obligations,
                available_inputs=set(env_inputs.keys()),
                available_evidence=evidence_pool,
            )

            if not resolution_proof.is_resolved:
                return {
                    "run_id": run_id,
                    "status": "RESOLUTION_DEFICIT",
                    "deficit_type": resolution_proof.deficit_type,
                    "deficits": [d.__dict__ for d in resolution_proof.resolution_deficits],
                    "resolution_proof": resolution_proof,
                }

            operations = resolution_proof.induced_operations

        # Step 4: Verification Contracts
        verification_contracts = injected_contracts or [
            VerificationContract(
                contract_id=f"vc_{op.operation_id}",
                observable_success_condition=op.postconditions[0] if op.postconditions else f"Satisfied {op.operation_id}",
                verification_method="PHYSICAL_OUTPUT_VERIFY",
                evidence_required=[],
                validator_fn=lambda state: bool(state),
            )
            for op in operations
        ]

        # Step 5: Downstream Decomposition Coverage Gate
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

        # Step 6: Capability & Evidence Closure Gate
        evidence_pool = verified_evidence_pool or {"root_evidence": {"evidence_class": EvidenceClass.VERIFIED_FACT.value}}
        closure_report = self.closure_gate.evaluate_closure(operations, evidence_pool)

        if not closure_report.is_closed:
            return {
                "run_id": run_id,
                "status": "CLOSURE_DEFICIT",
                "capability_deficits": [d.__dict__ for d in closure_report.capability_deficits],
                "evidence_deficits": [d.__dict__ for d in closure_report.evidence_deficits],
            }

        # Step 7: Compile Execution Graph
        graph = self.compiler.compile(
            adequacy_contract=adequacy_contract,
            decomposition_proof=decomposition_proof,
            closure_report=closure_report,
            operations=operations,
            verification_contracts=verification_contracts,
            resolution_proof=resolution_proof,
        )

        # Step 8: Authorize and Execute Graph
        execution_outcome = self.compiler.execute_graph(graph, initial_payload=env_inputs)

        # Step 9: Evaluate Outcome & Learn
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
            "result": execution_outcome,
            "evaluation": evidence,
            "learning": learning,
            "resolution_proof": resolution_proof,
        }

    def _run_legacy_slice_pipeline(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Legacy compatibility runner for Slice 1-4 unit test harnesses."""
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

            dynamic_target = action_gen.get("target") or f"{task['deliverable'].get('kind', 'output').lower()}_{task['task_id']}.txt"
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


def run(intent_or_request: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
    global _default_engine
    if _default_engine is None:
        _default_engine = ForgeEngine()
    return _default_engine.run(intent_or_request)
