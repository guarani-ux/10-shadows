from typing import Any, Dict
from forge.adapters.model import ModelAdapter
from forge.core.schema import validate_contract


def direct(task_spec: Dict[str, Any], model_adapter: ModelAdapter) -> Dict[str, Any]:
    """
    Executes a DIRECT route task using the model adapter and produces a DirectResult.
    """
    validate_contract("TaskSpec", task_spec)

    prompt = (
        f"Solve the following direct task.\n"
        f"Objective: {task_spec.get('objective')}\n"
        f"Deliverable Kind: {task_spec.get('deliverable', {}).get('kind')}\n"
        f"Constraints: {task_spec.get('constraints')}\n"
        f"Knowns: {task_spec.get('knowns')}\n"
        f"Assumptions: {task_spec.get('assumptions')}\n"
        f"Success Conditions: {task_spec.get('success_conditions')}\n"
    )

    generation = model_adapter.generate(
        instruction=prompt,
        input_data=task_spec
    )

    unresolved = generation.get("unresolved", []) if isinstance(generation, dict) else []
    status = "COMPLETE" if not unresolved else "NEEDS_INPUT"

    direct_result = {
        "task_id": task_spec["task_id"],
        "status": status,
        "result": generation,
        "unresolved": unresolved
    }

    validate_contract("DirectResult", direct_result)
    return direct_result
