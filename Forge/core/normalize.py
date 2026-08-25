import uuid
from typing import Any, Dict
from forge.adapters.model import ModelAdapter
from forge.core.schema import validate_contract


def normalize(intent_request: Dict[str, Any], model_adapter: ModelAdapter) -> Dict[str, Any]:
    """
    Normalizes an IntentRequest into a structured TaskSpec.
    Ensures that real objectives and constraints survive, unknowns are not invented,
    and output strictly validates against TaskSpec schema.
    """
    validate_contract("IntentRequest", intent_request)

    prompt = (
        "You are the Forge Task Normalizer. Convert the given raw intent and context into a precise TaskSpec. "
        "Extract: objective, deliverable (kind and description), constraints, knowns, unknowns, assumptions, "
        "success_conditions, requires_external_action (bool), reversibility ('REVERSIBLE'|'PARTIALLY_REVERSIBLE'|'IRREVERSIBLE'), "
        "and risk ('LOW'|'MEDIUM'|'HIGH'). "
        "Do not invent facts. Keep simple tasks simple."
    )

    extracted = model_adapter.generate(
        instruction=prompt,
        input_data=intent_request
    )

    task_id = f"task_{uuid.uuid4().hex[:8]}"

    # Enforce safe defaults and merge
    task_spec = {
        "task_id": task_id,
        "objective": extracted.get("objective") or intent_request.get("intent"),
        "deliverable": extracted.get("deliverable") or {
            "kind": intent_request.get("requested_surface") if intent_request.get("requested_surface") != "AUTO" else "ANSWER",
            "description": f"Outcome for {intent_request.get('intent')}"
        },
        "constraints": extracted.get("constraints", intent_request.get("constraints", [])),
        "knowns": extracted.get("knowns", []),
        "unknowns": extracted.get("unknowns", []),
        "assumptions": extracted.get("assumptions", []),
        "success_conditions": extracted.get("success_conditions", [f"Fulfill {intent_request.get('intent')}"]),
        "requires_external_action": bool(extracted.get("requires_external_action", False)),
        "reversibility": extracted.get("reversibility", "REVERSIBLE"),
        "risk": extracted.get("risk", "LOW")
    }

    validate_contract("TaskSpec", task_spec)
    return task_spec
