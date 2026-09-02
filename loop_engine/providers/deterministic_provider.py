"""Deterministic local builder for a small explicit objective family.

This worker writes candidate implementation artifacts only. It deliberately does
not write its own verification tests: canonical verification evidence is owned by
Ten Shadows, not by the builder being evaluated.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from loop_engine.dispatcher.protocol import WorkerAuthorization
from loop_engine.execution_authority import EvidenceModality, WorkerRole
from loop_engine.providers.base import BaseWorkerProvider, WorkerExecutionResult, workspace_matches_authorization


class DeterministicBuilderProvider(BaseWorkerProvider):
    """Write concrete candidates only for the explicitly implemented objective patterns."""

    def execute(
        self,
        authorization: WorkerAuthorization,
        objective: str,
        workspace_path: Path,
        available_capabilities: List[Dict[str, Any]],
        attempt_number: int = 1,
    ) -> WorkerExecutionResult:
        start_time = time.time()
        start_iso = datetime.now(timezone.utc).isoformat()

        if not authorization.verify_token():
            return self._rejected(
                authorization,
                start_time,
                start_iso,
                "Authorization token verification failed.",
                "AUTHORIZATION_TOKEN_INVALID",
            )

        if not workspace_matches_authorization(authorization, workspace_path):
            return self._rejected(
                authorization,
                start_time,
                start_iso,
                "Requested workspace does not match the cryptographically authorized filesystem boundary.",
                "WORKSPACE_BOUNDARY_MISMATCH",
            )

        workspace = Path(workspace_path).resolve()
        workspace.mkdir(parents=True, exist_ok=True)

        obj_lower = objective.lower()
        candidate_caps: List[Dict[str, Any]] = []

        if "celsius" in obj_lower and "fahrenheit" in obj_lower and "convert" in obj_lower and "100" not in obj_lower:
            code_content = (
                '"""Temperature conversion capability."""\n\n'
                "def celsius_to_fahrenheit(celsius: float) -> float:\n"
                '    """Convert Celsius temperature to Fahrenheit."""\n'
                "    return (celsius * 9.0 / 5.0) + 32.0\n\n"
                "def fahrenheit_to_celsius(fahrenheit: float) -> float:\n"
                '    """Convert Fahrenheit temperature to Celsius."""\n'
                "    return (fahrenheit - 32.0) * 5.0 / 9.0\n"
            )
            (workspace / "temperature.py").write_text(code_content, encoding="utf-8")
            output_msg = "Synthesized temperature conversion candidate."
            candidate_caps.append(
                {
                    "capability_id": "cap_temperature_conversion_v1",
                    "name": "Temperature Conversion",
                    "declared_purpose": "Convert temperatures between Celsius and Fahrenheit",
                    "artifact_paths": ["temperature.py"],
                    "dependencies": [],
                    "applicability_constraints": ["temperature", "celsius", "fahrenheit"],
                }
            )
        elif "100" in obj_lower and "fahrenheit" in obj_lower and ("convert" in obj_lower or "using" in obj_lower):
            if not (workspace / "temperature.py").is_file():
                return self._failure(
                    authorization,
                    start_time,
                    start_iso,
                    "CAPABILITY_DEFICIT: the reusable temperature capability was not materialized into the workspace.",
                    "CAPABILITY_DEFICIT",
                )
            eval_content = (
                "from temperature import celsius_to_fahrenheit\n\n"
                "def calculate_target():\n"
                "    return celsius_to_fahrenheit(100.0)\n\n"
                'if __name__ == "__main__":\n'
                "    print(f'100 C in Fahrenheit = {calculate_target()}')\n"
            )
            (workspace / "eval_temperature.py").write_text(eval_content, encoding="utf-8")
            output_msg = "Created a candidate that reuses the materialized temperature capability."
        elif "hydraulic" in obj_lower or "transient" in obj_lower or "pump" in obj_lower or "valve" in obj_lower:
            hydraulic_code = (
                '"""Hydraulic transient analysis fixture."""\n\n'
                "import math\n\n"
                "def compute_joukowsky_surge(rho: float, a: float, v0: float) -> float:\n"
                "    return rho * a * v0\n\n"
                "def compute_wave_speed(K: float, rho: float, D: float, E: float, e: float, c1: float = 0.91) -> float:\n"
                "    denom = 1.0 + c1 * ((K * D) / (E * e))\n"
                "    return math.sqrt((K / rho) / denom)\n"
            )
            (workspace / "hydraulic_transient.py").write_text(hydraulic_code, encoding="utf-8")
            output_msg = "Synthesized hydraulic transient candidate."
            candidate_caps.append(
                {
                    "capability_id": "cap_hydraulic_transient_v1",
                    "name": "Hydraulic Transient Analysis",
                    "declared_purpose": "Calculate wave speeds and Joukowsky pressure surges",
                    "artifact_paths": ["hydraulic_transient.py"],
                    "dependencies": [],
                    "applicability_constraints": ["hydraulic", "water hammer", "surge", "transient", "pump trip"],
                }
            )
        else:
            return self._failure(
                authorization,
                start_time,
                start_iso,
                f"CAPABILITY_DEFICIT: deterministic provider has no implemented objective handler for '{objective}'",
                "CAPABILITY_DEFICIT",
            )

        return WorkerExecutionResult(
            worker_id=authorization.worker_id,
            provider="deterministic",
            model="deterministic-v1",
            role=WorkerRole.BUILDER,
            modality=EvidenceModality.DETERMINISTIC_TEST,
            started_at=start_iso,
            ended_at=datetime.now(timezone.utc).isoformat(),
            duration_seconds=round(time.time() - start_time, 3),
            exit_status="SUCCESS",
            output_payload=output_msg,
            candidate_capabilities=candidate_caps,
        )

    @staticmethod
    def _failure(
        authorization: WorkerAuthorization,
        start_time: float,
        start_iso: str,
        message: str,
        error_code: str,
    ) -> WorkerExecutionResult:
        return WorkerExecutionResult(
            worker_id=authorization.worker_id,
            provider="deterministic",
            model="deterministic-v1",
            role=WorkerRole.BUILDER,
            modality=EvidenceModality.DETERMINISTIC_TEST,
            started_at=start_iso,
            ended_at=datetime.now(timezone.utc).isoformat(),
            duration_seconds=round(time.time() - start_time, 3),
            exit_status="FAILURE",
            output_payload=message,
            error_message=error_code,
        )

    @staticmethod
    def _rejected(
        authorization: WorkerAuthorization,
        start_time: float,
        start_iso: str,
        message: str,
        error_code: str,
    ) -> WorkerExecutionResult:
        return WorkerExecutionResult(
            worker_id=authorization.worker_id,
            provider="deterministic",
            model="deterministic-v1",
            role=WorkerRole.BUILDER,
            modality=EvidenceModality.STRUCTURAL,
            started_at=start_iso,
            ended_at=datetime.now(timezone.utc).isoformat(),
            duration_seconds=time.time() - start_time,
            exit_status="REJECTED",
            output_payload=message,
            error_message=error_code,
        )
