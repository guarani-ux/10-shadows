"""
gemini_provider.py — Gemini 3.7 Flash Worker Adapter for 10 SHADOWS Dispatcher.
Executes autonomous code generation against Google Gemini API strictly within the GovernedWorkspace.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loop_engine.dispatcher.protocol import (
    WorkerAuthorization,
    WorkerExecutionResult,
    WorkerEvidenceModality,
    ProviderUsage,
)
from loop_engine.dispatcher.providers.base import WorkerProviderAdapter


def _run_git(args: List[str], cwd: Path) -> Tuple[int, str, str]:
    proc = subprocess.run(
        ["git"] + args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


class GeminiWorkerAdapter(WorkerProviderAdapter):
    """
    Empirical AI Worker Adapter for Google Gemini.
    """

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

    @property
    def provider_name(self) -> str:
        return "gemini"

    def execute(
        self,
        auth: WorkerAuthorization,
        workspace_path: Path,
    ) -> WorkerExecutionResult:
        start_time = time.perf_counter()
        started_at = datetime.now(timezone.utc).isoformat()

        # Capture workspace before SHA
        _, before_sha, _ = _run_git(["rev-parse", "HEAD"], cwd=workspace_path)
        if not before_sha or len(before_sha) != 40:
            before_sha = auth.baseline_sha

        # 1. Credential Check — Fail Closed
        if not self._api_key:
            duration = max(0.001, time.perf_counter() - start_time)
            ended_at = datetime.now(timezone.utc).isoformat()
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
                modality=WorkerEvidenceModality.EMPIRICAL,
                started_at=started_at,
                ended_at=ended_at,
                duration_seconds=round(duration, 3),
                exit_status="FAILURE",
                usage=None,
                output_digest=hashlib.sha256(b"missing_credentials").hexdigest(),
                workspace_before_sha=before_sha,
                workspace_after_sha=before_sha,
                files_changed=[],
                provider_receipt=None,
                errors=["GEMINI_API_KEY not configured in environment."],
                completion_status="FAILED_UNAUTHORIZED",
            )

        # 2. Gather Context from Workspace
        workspace_files = []
        for p in workspace_path.rglob("*.py"):
            if not any(part.startswith(".") or part in ("__pycache__", "venv", "target") for part in p.parts):
                rel = p.relative_to(workspace_path)
                try:
                    workspace_files.append({"path": str(rel), "content": p.read_text(encoding="utf-8", errors="replace")[:3000]})
                except Exception:
                    pass

        prompt_payload = {
            "objective": auth.objective,
            "attempt_number": auth.attempt_number,
            "failure_evidence": auth.failure_evidence,
            "workspace_files": workspace_files[:20],
            "instruction": (
                "You are an expert software engineer operating inside an isolated git workspace. "
                "Fulfill the objective completely. Return a JSON object with key 'files' mapping relative "
                "file paths to their complete updated or new Python code contents: {'files': {'path/to/file.py': 'code...'}}"
            ),
        }

        model_name = auth.requested_model or "gemini-3.7-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self._api_key}"
        
        req_body = {
            "contents": [{"parts": [{"text": json.dumps(prompt_payload)}]}],
            "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"},
        }

        data_bytes = json.dumps(req_body).encode("utf-8")
        http_req = urllib.request.Request(
            url,
            data=data_bytes,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        files_changed = []
        errors = []
        resolved_model = "UNPROVEN"
        provider_receipt = None
        usage_info = None
        req_id = f"req_gemini_{auth.invocation_id}"

        try:
            with urllib.request.urlopen(http_req, timeout=auth.timeout_seconds) as resp:
                resp_bytes = resp.read()
                resp_json = json.loads(resp_bytes.decode("utf-8"))
                
                # Check for explicit resolved model in response metadata
                if "modelVersion" in resp_json:
                    resolved_model = resp_json["modelVersion"]
                elif "candidates" in resp_json and resp_json["candidates"]:
                    # Model responded successfully to requested model name
                    resolved_model = model_name
                else:
                    resolved_model = "UNPROVEN"

                resp_id = resp_json.get("responseId") or f"resp_gemini_{hashlib.sha256(resp_bytes).hexdigest()[:12]}"
                
                usage_meta = resp_json.get("usageMetadata", {})
                p_tokens = usage_meta.get("promptTokenCount")
                c_tokens = usage_meta.get("candidatesTokenCount")
                t_tokens = usage_meta.get("totalTokenCount")
                if p_tokens is not None or c_tokens is not None:
                    usage_info = ProviderUsage(
                        prompt_tokens=p_tokens,
                        candidate_tokens=c_tokens,
                        total_tokens=t_tokens,
                    )

                candidates = resp_json.get("candidates", [])
                if not candidates:
                    errors.append("Gemini returned empty candidate list.")
                else:
                    text_out = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    # Parse JSON file map
                    try:
                        parsed = json.loads(text_out)
                        files_map = parsed.get("files", {})
                        if isinstance(files_map, dict):
                            for rel_path, code in files_map.items():
                                target_file = (workspace_path / rel_path).resolve()
                                # Confinement check
                                if not str(target_file).startswith(str(workspace_path.resolve())):
                                    errors.append(f"Security violation: path traversal detected '{rel_path}'")
                                    continue
                                target_file.parent.mkdir(parents=True, exist_ok=True)
                                target_file.write_text(code, encoding="utf-8")
                                files_changed.append(rel_path)
                    except Exception as pe:
                        errors.append(f"Failed to parse model file payload: {pe}")

                # Stage and commit mutations
                if files_changed:
                    _run_git(["add", "-A"], cwd=workspace_path)
                    commit_msg = f"feat(governed): {auth.objective[:50]} (attempt {auth.attempt_number})"
                    code, _, err = _run_git(["commit", "--no-verify", "-m", commit_msg], cwd=workspace_path)
                    if code != 0:
                        errors.append(f"Git commit failed: {err}")

                _, after_sha, _ = _run_git(["rev-parse", "HEAD"], cwd=workspace_path)
                if not after_sha or len(after_sha) != 40:
                    after_sha = before_sha

                provider_receipt = {
                    "request_id": req_id,
                    "response_id": resp_id,
                    "provider_name": "google",
                    "model_id": resolved_model,
                    "tokens_prompt": p_tokens,
                    "tokens_completion": c_tokens,
                    "tokens_total": t_tokens,
                }

        except Exception as e:
            errors.append(f"Gemini API execution failure: {type(e).__name__}: {str(e)}")
            after_sha = before_sha

        duration = max(0.001, time.perf_counter() - start_time)
        ended_at = datetime.now(timezone.utc).isoformat()
        exit_status = "SUCCESS" if (files_changed and not errors) else "FAILURE"
        output_digest = hashlib.sha256(f"{before_sha}:{after_sha}:{files_changed}".encode("utf-8")).hexdigest()

        return WorkerExecutionResult(
            protocol_version="1.0.0",
            run_id=auth.run_id,
            invocation_id=auth.invocation_id,
            worker_id=auth.worker_id,
            requested_provider="gemini",
            requested_model=auth.requested_model,
            resolved_provider="google",
            resolved_model=resolved_model,
            provider_invocation_id=req_id,
            modality=WorkerEvidenceModality.EMPIRICAL,
            started_at=started_at,
            ended_at=ended_at,
            duration_seconds=round(duration, 3),
            exit_status=exit_status,
            usage=usage_info,
            output_digest=output_digest,
            workspace_before_sha=before_sha,
            workspace_after_sha=after_sha,
            files_changed=files_changed,
            provider_receipt=provider_receipt,
            errors=errors,
            completion_status="COMPLETED" if exit_status == "SUCCESS" else "FAILED",
        )
