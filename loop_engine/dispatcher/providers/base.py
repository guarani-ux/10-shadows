"""
base.py — Abstract Base Class for Dispatcher Provider Adapters.
"""

from __future__ import annotations

import abc
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loop_engine.dispatcher.protocol import (
    WorkerAuthorization,
    WorkerExecutionResult,
)


class WorkerProviderAdapter(abc.ABC):
    """
    Abstract adapter for a specific worker/model backend (Gemini, Claude, Deterministic, etc.).
    Operates strictly within the governed workspace declared in the authorization.
    """

    @property
    @abc.abstractmethod
    def provider_name(self) -> str:
        pass

    @abc.abstractmethod
    def execute(
        self,
        auth: WorkerAuthorization,
        workspace_path: Path,
    ) -> WorkerExecutionResult:
        """
        Executes worker logic strictly inside workspace_path according to auth.
        Must NOT escape the declared workspace path.
        """
        pass
