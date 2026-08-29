"""
loop_engine/providers
Strict Worker and Provider Adapters for 10 SHADOWS.
"""

from loop_engine.providers.antigravity_provider import AntigravityBuilderProvider
from loop_engine.providers.base import BaseWorkerProvider, WorkerExecutionResult
from loop_engine.providers.deterministic_provider import DeterministicBuilderProvider
from loop_engine.providers.gemini_provider import GeminiBuilderProvider

__all__ = [
    "BaseWorkerProvider",
    "WorkerExecutionResult",
    "DeterministicBuilderProvider",
    "GeminiBuilderProvider",
    "AntigravityBuilderProvider",
]
