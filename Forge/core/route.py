from typing import Any, Dict
from forge.core.schema import validate_contract


def requires_persistent_capability(task_spec: Dict[str, Any]) -> bool:
    """
    Minimal deterministic check for whether a task requires a persistent reusable capability.
    """
    deliverable = task_spec.get("deliverable", {})
    kind = deliverable.get("kind", "")
    description = deliverable.get("description", "").lower()
    objective = task_spec.get("objective", "").lower()

    if kind in ("SYSTEM", "CODE", "WORKFLOW", "ACTION"):
        return True

    keywords = ["reusable", "processor", "pipeline", "workflow", "persist", "tool", "script"]
    if any(kw in objective or kw in description for kw in keywords):
        return True

    return False


def compile_route(task_spec: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compiles the minimum execution route (DIRECT | BUILD | ACT) for a given TaskSpec.
    """
    validate_contract("TaskSpec", task_spec)

    task_id = task_spec["task_id"]

    if task_spec.get("requires_external_action"):
        route_decision = {
            "task_id": task_id,
            "route": "ACT",
            "reason": "Task requires external or persistent mutation.",
            "minimal_next_step": "Construct ActionProposal and pass to authorization gate.",
            "stop_condition": "Action executed and receipt recorded."
        }
    elif requires_persistent_capability(task_spec):
        route_decision = {
            "task_id": task_id,
            "route": "BUILD",
            "reason": "Task requires a persistent, reusable capability or system artifact.",
            "minimal_next_step": "Synthesize BuildSpec and generate minimal processor.",
            "stop_condition": "Artifact produced and smoke test passed."
        }
    else:
        route_decision = {
            "task_id": task_id,
            "route": "DIRECT",
            "reason": "Requested outcome can be produced immediately without persistent machinery or side effects.",
            "minimal_next_step": "Process task directly through model adapter.",
            "stop_condition": "DirectResult generated."
        }

    validate_contract("RouteDecision", route_decision)
    return route_decision
