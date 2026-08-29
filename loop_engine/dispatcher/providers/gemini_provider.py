"""Gemini worker adapter for the alternate Rust/Python dispatcher path.

A real network response can provide empirical execution evidence. Missing
credentials, invalid bindings, parse failures, or unavailable network paths are
not empirical execution and must not be labelled as such.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from loop_engine.dispatcher.protocol import (
    ProviderUsage,
    WorkerAuthorization,
    WorkerEvidenceModality,
    WorkerExecutionResult,
)
from loop_engine.dispatcher.providers.base import WorkerProviderAdapter


def _run_git(args: List[str], cwd: Path) -> Tuple[int, str, str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        check=False,
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


class GeminiWorkerAdapter(WorkerProviderAdapter):
    """Google Gemini adapter for an explicitly governed dispatcher workspace."""

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

    @property
    def provider_name(self) -> str:
        return "gemini"

    def _failed(
        self,
        auth: WorkerAuthorization,
        started_at: str,
        start_time: float,
        before_sha: str,
        message: str,
        *,
        rejected: bool = False,
    ) -> WorkerExecutionResult:
        duration = max(0.001, time.perf_counter() - start_time)
        return WorkerExecutionResult(
            protocol_version="1.0.0",
            run_id=auth.run_id,
            invocation_id=auth.invocation_id,
            worker_id=auth.worker_id,
            requested_provider="gemini",
            requested_model=auth.requested_model,
            resolved_provider="google",
            resolved_model="UNPROVEN",
            provider_invocation_id=None,
            modality=WorkerEvidenceModality.STRUCTURAL,
            started_at=started_at,
            ended_at=datetime.now(timezone.utc).isoformat(),
            duration_seconds=round(duration, 3),
            exit_status="REJECTED" if rejected else "FAILURE",
            usage=None,
            output_digest=hashlib.sha256(message.encode("utf-8")).hexdigest(),
            workspace_before_sha=before_sha,
            workspace_after_sha=before_sha,
            files_changed=[],
            provider_receipt=None,
            errors=[message],
            completion_status="REJECTED" if rejected else "FAILED",
        )

    def execute(self, auth: WorkerAuthorization, workspace_path: Path) -> WorkerExecutionResult:
        start_time = time.perf_counter()
        started_at = datetime.now(timezone.utc).isoformat()
        workspace = workspace_path.resolve()

        _, before_sha, _ = _run_git(["rev-parse", "HEAD"], cwd=workspace)
        if not before_sha or len(before_sha) != 40:
            before_sha = auth.baseline_sha

        if not auth.verify_token():
            return self._failed(
                auth,
                started_at,
                start_time,
                before_sha,
                "Invocation binding digest is invalid.",
                rejected=True,
            )
        if (
            workspace != Path(auth.governed_workspace_path).resolve()
            or workspace != Path(auth.filesystem_boundary).resolve()
        ):
            return self._failed(
                auth,
                started_at,
                start_time,
                before_sha,
                "Workspace does not match the declared dispatcher boundary.",
                rejected=True,
            )
        if not self._api_key:
            return self._failed(
                auth,
                started_at,
                start_time,
                before_sha,
                "GEMINI_API_KEY is not configured; no provider invocation occurred.",
            )

        workspace_files = []
        for path in workspace.rglob("*.py"):
            if any(part.startswith(".") or part in {"__pycache__", "venv", "target"} for part in path.parts):
                continue
            try:
                workspace_files.append(
                    {
                        "path": str(path.relative_to(workspace)),
                        "content": path.read_text(encoding="utf-8", errors="replace")[:3000],
                    }
                )
            except OSError:
                continue

        prompt_payload = {
            "objective": auth.objective,
            "attempt_number": auth.attempt_number,
            "failure_evidence": auth.failure_evidence,
            "workspace_files": workspace_files[:20],
            "instruction": (
                "Fulfill the objective within the provided workspace. Return JSON with key 'files' "
                "mapping relative file paths to complete file contents."
            ),
        }
        model_name = auth.requested_model or "gemini-3.7-flash"
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self._api_key}"
        )
        request_body = {
            "contents": [{"parts": [{"text": json.dumps(prompt_payload)}]}],
            "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"},
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(request_body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        files_changed: List[str] = []
        errors: List[str] = []
        resolved_model = "UNPROVEN"
        provider_receipt: Optional[Dict[str, object]] = None
        usage_info = None
        provider_invocation_id: Optional[str] = None
        empirical_invocation_observed = False

        try:
            with urllib.request.urlopen(request, timeout=auth.timeout_seconds) as response:
                response_bytes = response.read()
                response_json = json.loads(response_bytes.decode("utf-8"))
                empirical_invocation_observed = True
                resolved_model = response_json.get("modelVersion") or model_name
                response_id = response_json.get("responseId") or hashlib.sha256(response_bytes).hexdigest()[:24]
                provider_invocation_id = str(response_id)

                usage = response_json.get("usageMetadata", {})
                prompt_tokens = usage.get("promptTokenCount")
                candidate_tokens = usage.get("candidatesTokenCount")
                total_tokens = usage.get("totalTokenCount")
                if prompt_tokens is not None or candidate_tokens is not None or total_tokens is not None:
                    usage_info = ProviderUsage(
                        prompt_tokens=prompt_tokens,
                        candidate_tokens=candidate_tokens,
                        total_tokens=total_tokens,
                    )

                candidates = response_json.get("candidates", [])
                if not candidates:
                    errors.append("Gemini returned no candidate payload.")
                else:
                    text_output = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    parsed = json.loads(text_output)
                    files_map = parsed.get("files", {})
                    if not isinstance(files_map, dict):
                        errors.append("Gemini response did not contain a valid files mapping.")
                    else:
                        for rel_path, contents in files_map.items():
                            if not isinstance(rel_path, str) or not isinstance(contents, str):
                                errors.append("Gemini returned a non-string file path or file content.")
                                continue
                            target_file = (workspace / rel_path).resolve()
                            if not _is_within(target_file, workspace) or target_file == workspace:
                                errors.append(f"Rejected path outside workspace: {rel_path}")
                                continue
                            target_file.parent.mkdir(parents=True, exist_ok=True)
                            target_file.write_text(contents, encoding="utf-8")
                            files_changed.append(rel_path)

                provider_receipt = {
                    "response_id": response_id,
                    "provider_name": "google",
                    "model_id": resolved_model,
                    "raw_response_digest": hashlib.sha256(response_bytes).hexdigest(),
                    "tokens_prompt": prompt_tokens,
                    "tokens_completion": candidate_tokens,
                    "tokens_total": total_tokens,
                }

                if files_changed and not errors:
                    _run_git(["add", "-A"], cwd=workspace)
                    code, _, error = _run_git(
                        ["commit", "--no-verify", "-m", f"governed worker attempt {auth.attempt_number}"],
                        cwd=workspace,
                    )
                    if code != 0:
                        errors.append(f"Git commit failed: {error}")
        except Exception as exc:
            errors.append(f"Gemini API execution failure: {type(exc).__name__}: {exc}")

        _, after_sha, _ = _run_git(["rev-parse", "HEAD"], cwd=workspace)
        if not after_sha or len(after_sha) != 40:
            after_sha = before_sha

        duration = max(0.001, time.perf_counter() - start_time)
        success = empirical_invocation_observed and bool(files_changed) and not errors
        digest = hashlib.sha256(f"{before_sha}:{after_sha}:{files_changed}".encode("utf-8")).hexdigest()
        return WorkerExecutionResult(
            protocol_version="1.0.0",
            run_id=auth.run_id,
            invocation_id=auth.invocation_id,
            worker_id=auth.worker_id,
            requested_provider="gemini",
            requested_model=auth.requested_model,
            resolved_provider="google",
            resolved_model=resolved_model,
            provider_invocation_id=provider_invocation_id,
            modality=(
                WorkerEvidenceModality.EMPIRICAL if empirical_invocation_observed else WorkerEvidenceModality.STRUCTURAL
            ),
            started_at=started_at,
            ended_at=datetime.now(timezone.utc).isoformat(),
            duration_seconds=round(duration, 3),
            exit_status="SUCCESS" if success else "FAILURE",
            usage=usage_info,
            output_digest=digest,
            workspace_before_sha=before_sha,
            workspace_after_sha=after_sha,
            files_changed=files_changed,
            provider_receipt=provider_receipt,
            errors=errors,
            completion_status="COMPLETED" if success else "FAILED",
        )
