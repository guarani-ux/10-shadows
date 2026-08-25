"""Model adapter interface for candidate extraction and synthesis."""

import abc
from typing import List, Dict, Any


class BaseModelAdapter(abc.ABC):
    """Abstract base adapter for probabilistic language models."""

    @abc.abstractmethod
    def extract_claims(self, text: str, source_id: str, topic_id: str) -> List[Dict[str, Any]]:
        """Extract candidate claims matching CandidateClaimSpec JSON schema."""
        pass


class MockModelAdapter(BaseModelAdapter):
    """Deterministic model adapter for unit testing and red-team validation."""

    def __init__(self, fixed_claims: List[Dict[str, Any]]):
        self.fixed_claims = fixed_claims

    def extract_claims(self, text: str, source_id: str, topic_id: str) -> List[Dict[str, Any]]:
        return list(self.fixed_claims)
