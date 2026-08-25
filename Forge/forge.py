import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Union
from forge.adapters.actions import ActionAdapter, SandboxFileAdapter
from forge.adapters.model import ModelAdapter, MockModelAdapter
from forge.core.authorize import AuthorizationGate
from forge.core.build import build
from forge.core.direct import direct
from forge.core.evaluate import evaluate
from forge.core.execute import execute_action
from forge.core.learn import learn_if_earned
from forge.core.normalize import normalize
from forge.core.route import compile_route
from forge.core.schema import validate_contract
from forge.core.store import ForgeStore


class ForgeEngine:
    def __init__(
        self,
        store: Optional[ForgeStore] = None,
        model_adapter: Optional[ModelAdapter] = None,
        action_adapter: Optional[ActionAdapter] = None,
        sandbox_dir: Optional[Union[str, Path]] = None,
        artifacts_dir: Optional[Union[str, Path]] = None
    ):
        self.store = store or ForgeStore()
        self.model = model_adapter or MockModelAdapter()
        sandbox_path = Path(sandbox_dir) if sandbox_dir else Path("sandbox")
        self.action_adapter = action_adapter or SandboxFileAdapter(sandbox_path)
        self.artifacts_dir = Path(artifacts_dir) if artifacts_dir else Path("artifacts")
        self.auth_gate = AuthorizationGate(self.store)

    def run(self, intent_or_request: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Main entrypoint: converts raw human intent into the smallest useful result,
        reusable capability, or authorized action.
        """
        # Step 1: Ingest and wrap raw string into IntentRequest if needed
        if isinstance(intent_or_request, str):
            request = {
                "request_id": f"req_{uuid.uuid4().hex[:8]}",
                "intent": intent_or_request,
                "context": [],
                "constraints": [],
                "requested_surface": "AUTO"
            }
        else:
            request = intent_or_request

        validate_contract("IntentRequest", request)
        run_id = f"run_{uuid.uuid4().hex[:8]}"
        self.store.record_run(run_id, request, status="STARTED")

        # Step 2: Understand & Normalize (Slice 1)
        task = normalize(request, self.model)
        self.store.record_run(run_id, request, status="NORMALIZED", task_spec=task)

        # Step 3: Compile Minimal Route
        route_decision = compile_route(task)
        route = route_decision["route"]
        self.store.record_run(run_id, request, status="ROUTED", task_spec=task, route=route_decision)

        # Step 4: Execute Selected Minimal Route
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
                content_path=artifact.get("content_path")
            )
            final_output = {
                "build_spec": build_spec,
                "artifact": artifact,
                "status": "COMPLETE" if artifact["smoke_test_status"] == "PASSED" else "FAILED"
            }

        elif route == "ACT":
            # Dynamic Action Proposal formulation from TaskSpec
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
                input_data=task
            )

            # Fallback sane defaults derived dynamically from task if model returns basic dictionary
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
                    "payload": dynamic_payload
                },
                "capability_required": dynamic_capability,
                "idempotency_key": f"idem_{uuid.uuid4().hex[:8]}",
                "reversible": True,
                "rollback": None
            }
            self.store.record_attempt(attempt_id, tx_id, state="PROPOSED", proposal=proposal)

            # Authorization Gate (Slice 3)
            auth_decision = self.auth_gate.evaluate_proposal(proposal)
            if auth_decision["decision"] == "AUTHORIZED":
                receipt = execute_action(
                    authorization_decision=auth_decision,
                    operation=proposal["operation"],
                    action_adapter=self.action_adapter,
                    store=self.store
                )
                self.store.record_transaction(tx_id, task["task_id"], state="COMMITTED" if receipt["side_effect_committed"] else "FAILED")
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
                    "error": f"Authorization denied: {auth_decision.get('reason')}"
                }
                self.store.record_transaction(tx_id, task["task_id"], state="DENIED")
            final_output = receipt

        else:
            raise ValueError(f"Unknown route '{route}'")

        # Step 5: Reality Evaluation (Slice 4)
        evidence = evaluate(task, final_output)

        # Step 6: Earned Learning Loop
        learning = learn_if_earned(task, final_output, evidence, self.store)

        status = "COMPLETED" if evidence["success"] else "FAILED"
        self.store.record_run(run_id, request, status=status, task_spec=task, route=route_decision)

        return {
            "run_id": run_id,
            "task_id": task["task_id"],
            "route": route,
            "result": final_output,
            "evaluation": evidence,
            "learning": learning
        }


# Convenience module-level API
_default_engine: Optional[ForgeEngine] = None


def run(intent_or_request: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
    global _default_engine
    if _default_engine is None:
        _default_engine = ForgeEngine()
    return _default_engine.run(intent_or_request)
