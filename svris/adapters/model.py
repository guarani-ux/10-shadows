"""
svris/adapters/model.py
SVRIS Model Adapter Bridge.
Inherits from canonical loop_engine.model.boundary.ModelAdapter
while maintaining 100% backward-compatible extract_claims(...) API.
"""

from typing import Any, Dict, List

from loop_engine.model.boundary import (
    ModelAdapter as CanonicalModelAdapter,
)
from loop_engine.model.boundary import (
    ModelRequest,
    ModelResponse,
)


class BaseModelAdapter(CanonicalModelAdapter):
    """
    SVRIS BaseModelAdapter base class, bridging to canonical ModelAdapter.
    """

    @property
    def model_id(self) -> str:
        return "svris-model-base"

    @property
    def provider_name(self) -> str:
        return "svris"

    def execute(self, request: ModelRequest) -> ModelResponse:
        text = request.compiled_context.get("AUTHORITATIVE", {}).get("text", request.objective)
        source_id = request.metadata.get("source_id", "src_default")
        topic_id = request.metadata.get("topic_id", "top_default")
        claims = self.extract_claims(text, source_id, topic_id)
        return ModelResponse(
            task_id=request.task_id,
            candidate_payload=claims,
            model_identifier=self.model_id,
            provider=self.provider_name,
        )

    def extract_claims(self, text: str, source_id: str, topic_id: str) -> List[Dict[str, Any]]:
        """Extract candidate claims matching CandidateClaimSpec JSON schema."""
        raise NotImplementedError("Subclasses must implement extract_claims or execute.")


class MockModelAdapter(BaseModelAdapter):
    """Deterministic model adapter for unit testing and red-team validation."""

    def __init__(self, fixed_claims: List[Dict[str, Any]]):
        self.fixed_claims = fixed_claims

    @property
    def model_id(self) -> str:
        return "svris-mock"

    def extract_claims(self, text: str, source_id: str, topic_id: str) -> List[Dict[str, Any]]:
        return list(self.fixed_claims)
