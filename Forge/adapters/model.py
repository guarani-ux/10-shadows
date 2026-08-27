import abc
from typing import Any, Callable, Dict, Optional


class ModelAdapter(abc.ABC):
    @abc.abstractmethod
    def generate(
        self,
        *,
        instruction: str,
        input_data: Dict[str, Any],
        output_schema: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Executes a generation pass with an LLM backend or test harness.
        """
        pass


class MockModelAdapter(ModelAdapter):
    """
    Deterministic ModelAdapter for offline execution, unit tests, and CI/CD validation.
    """
    def __init__(self, default_handler: Optional[Callable[[str, Dict[str, Any]], Dict[str, Any]]] = None):
        self.default_handler = default_handler
        self.preset_responses: Dict[str, Dict[str, Any]] = {}
        self.call_history: list[Dict[str, Any]] = []

    def register_response(self, instruction_key: str, response: Dict[str, Any]) -> None:
        self.preset_responses[instruction_key] = response

    def generate(
        self,
        *,
        instruction: str,
        input_data: Dict[str, Any],
        output_schema: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        self.call_history.append({
            "instruction": instruction,
            "input_data": input_data,
            "output_schema": output_schema
        })

        # Check explicit registered response
        for key, resp in self.preset_responses.items():
            if key.lower() in instruction.lower():
                return resp

        # Custom handler fallback
        if self.default_handler:
            return self.default_handler(instruction, input_data)

        # Built-in deterministic defaults for standard prompts
        if "normalize" in instruction.lower():
            intent = input_data.get("intent", "")
            return {
                "objective": intent,
                "deliverable": {
                    "kind": input_data.get("requested_surface", "ANSWER") if input_data.get("requested_surface") != "AUTO" else "ANSWER",
                    "description": f"Output for: {intent}"
                },
                "constraints": input_data.get("constraints", []),
                "knowns": [f"Known: {c.get('label')}" for c in input_data.get("context", [])],
                "unknowns": [],
                "assumptions": [],
                "success_conditions": [f"Satisfies {intent}"],
                "requires_external_action": False,
                "reversibility": "REVERSIBLE",
                "risk": "LOW"
            }

        if "direct" in instruction.lower():
            objective = input_data.get("objective", "")
            return {
                "summary": f"Direct result for '{objective}'",
                "content": f"Successfully processed direct task '{objective}'."
            }

        return {"status": "ok", "message": "Default mock response"}
