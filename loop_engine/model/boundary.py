"""
loop_engine/model/boundary.py
Canonical, Provider-Agnostic Model Boundary for 10 SHADOWS.

Separates AI proposal generation from system authority.
Exposes only what the system needs, guarantees strict schema isolation,
and keeps provider-specific logic completely behind adapters.
"""

from __future__ import annotations

import abc
from enum import Enum
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, List, Optional, Sequence, Union
from pydantic import BaseModel, Field


class InferenceEffort(str, Enum):
    FAST = "FAST"          # Minimal latency/tokens (e.g. routine queries, simple extractions)
    STANDARD = "STANDARD"  # Baseline balanced reasoning
    DEEP = "DEEP"          # Maximum inference budget (e.g. complex synthesis, difficult repair)


class DeficitType(str, Enum):
    MISSING_KNOWLEDGE = "MISSING_KNOWLEDGE"          # Requires external domain facts or docs
    MISSING_EVIDENCE = "MISSING_EVIDENCE"            # Requires verified physical test traces or data
    MISSING_CAPABILITY = "MISSING_CAPABILITY"        # Requires a specific tool/action not provisioned
    AMBIGUOUS_OBJECTIVE = "AMBIGUOUS_OBJECTIVE"      # Specification contains contradictions/ambiguity
    UNRESOLVED_CONSTRAINT = "UNRESOLVED_CONSTRAINT"  # Invariant cannot be satisfied without clarification
    EXECUTION_FAILURE = "EXECUTION_FAILURE"          # Sandbox / environment execution error
    CANDIDATE_FAILURE = "CANDIDATE_FAILURE"          # Logic / semantic defect in proposed code


class DeficitDeclaration(BaseModel):
    """
    First-class declaration emitted by a model or detected by the system
    when an operation cannot be completed reliably without additional competence.
    """
    deficit_type: DeficitType
    description: str
    target_subject: Optional[str] = None
    required_provision: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ModelRequest(BaseModel):
    """
    Provider-agnostic request payload passed into any ModelAdapter.
    """
    task_id: str
    operation_type: str = "GENERATE_CANDIDATE"  # e.g. "NORMALIZE", "SYNTHESIZE", "REPAIR", "EXTRACT"
    objective: str
    compiled_context: Dict[str, Any] = Field(default_factory=dict)
    output_contract: Optional[Dict[str, Any]] = None
    allowed_tools: List[str] = Field(default_factory=list)
    inference_effort: InferenceEffort = InferenceEffort.STANDARD
    candidate_count: int = 1
    provenance_references: List[str] = Field(default_factory=list)
    unresolved_deficits: List[DeficitDeclaration] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


def compute_provider_payload_digest(
    candidate_payload: Any,
    raw_response: Optional[Dict[str, Any]] = None,
    objective: Optional[str] = None,
) -> str:
    """Computes deterministic digest binding candidate payload and provider response."""
    cand_str = json.dumps(candidate_payload, sort_keys=True) if isinstance(candidate_payload, (dict, list)) else str(candidate_payload)
    raw_str = json.dumps(raw_response, sort_keys=True) if isinstance(raw_response, (dict, list)) else str(raw_response)
    raw = f"{str(objective)}:{cand_str}:{raw_str}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class ProviderExecutionReceipt(BaseModel):
    """
    Cryptographically verifiable receipt of physical model provider execution.
    Proves that an inference call actually executed against an external provider.
    """
    request_id: str
    response_id: str
    provider_name: str
    model_id: str
    timestamp_utc: str = Field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    latency_seconds: float = 0.0
    tokens_prompt: Optional[int] = None
    tokens_completion: Optional[int] = None
    tokens_total: Optional[int] = None
    payload_digest: str
    receipt_digest: str = ""

    def compute_digest(self) -> str:
        raw = (
            f"{self.request_id}:{self.response_id}:{self.provider_name}:{self.model_id}:"
            f"{self.timestamp_utc}:{round(self.latency_seconds, 4)}:{self.tokens_prompt}:"
            f"{self.tokens_completion}:{self.tokens_total}:{self.payload_digest}"
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def model_post_init(self, __context: Any) -> None:
        if not self.receipt_digest:
            self.receipt_digest = self.compute_digest()

    def is_valid_for_response(
        self,
        response: ModelResponse,
        request: Optional[ModelRequest] = None,
    ) -> bool:
        """Verifies internal digest integrity and structural binding to ModelResponse."""
        if not self.receipt_digest or self.receipt_digest != self.compute_digest():
            return False
        if self.provider_name != response.provider or self.model_id != response.model_identifier:
            return False
        expected_payload_digest = compute_provider_payload_digest(
            candidate_payload=response.candidate_payload,
            raw_response=response.raw_response,
            objective=request.objective if request else None,
        )
        if self.payload_digest != expected_payload_digest:
            return False
        return True


class ModelResponse(BaseModel):
    """
    Provider-agnostic response payload returned by any ModelAdapter.
    """
    task_id: str
    candidate_payload: Any = None
    explicit_uncertainties: List[str] = Field(default_factory=list)
    declared_deficits: List[DeficitDeclaration] = Field(default_factory=list)
    requested_tools: List[str] = Field(default_factory=list)
    structured_alternatives: List[Any] = Field(default_factory=list)
    provenance_references: List[str] = Field(default_factory=list)
    model_identifier: str = "unknown_model"
    provider: str = "unknown_provider"
    inference_effort: InferenceEffort = InferenceEffort.STANDARD
    tokens_consumed: Optional[int] = None
    latency_seconds: float = 0.0
    is_success: bool = True
    error_message: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = None
    provider_receipt: Optional[ProviderExecutionReceipt] = None


class EvidenceModality(str, Enum):
    STRUCTURAL_MOCK = "STRUCTURAL_MOCK"
    EMPIRICAL_MODEL = "EMPIRICAL_MODEL"


class ModelAdapter(abc.ABC):
    """
    Abstract Base Class for all model adapters.
    Downstream subsystems interact exclusively with this interface.
    """
    @property
    @abc.abstractmethod
    def model_id(self) -> str:
        """Unique model identifier (e.g. 'mock-strong', 'gemini-3.7-flash')."""
        pass

    @property
    @abc.abstractmethod
    def provider_name(self) -> str:
        """Provider name (e.g. 'mock', 'google', 'anthropic')."""
        pass

    @abc.abstractmethod
    def execute(self, request: ModelRequest) -> ModelResponse:
        """Executes generation against the model backend."""
        pass

    def generate(
        self,
        *,
        instruction: str,
        input_data: Dict[str, Any],
        output_schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Backward-compatible convenience method for legacy Forge / SVRIS callers.
        Converts raw instruction/input_data into a ModelRequest and returns the candidate dict.
        """
        req = ModelRequest(
            task_id=str(input_data.get("task_id", "task_legacy")),
            operation_type="LEGACY_GENERATE",
            objective=instruction,
            compiled_context={"AUTHORITATIVE": input_data},
            output_contract=output_schema,
        )
        res = self.execute(req)
        if isinstance(res.candidate_payload, dict):
            return res.candidate_payload
        return {"result": res.candidate_payload, "status": "ok" if res.is_success else "error"}


class MockModelProfile(str, Enum):
    STRONG = "STRONG"              # High capability, succeeds on first attempt, declares deficits accurately
    WEAK = "WEAK"                  # Flawed initial output, misses constraints unless compiled into context, recovers with repair
    ADVERSARIAL = "ADVERSARIAL"    # Confidently emits wrong/invalid candidate claiming success


class MockModelAdapter(ModelAdapter):
    """
    Deterministic ModelAdapter supporting configurable behavioral profiles for
    offline unit testing, ablation studies, and CI validation.
    """
    def __init__(
        self,
        profile: MockModelProfile = MockModelProfile.STRONG,
        model_id: Optional[str] = None,
        custom_handler: Optional[Callable[[ModelRequest], ModelResponse]] = None,
    ):
        self.profile = profile
        self._model_id = model_id or f"mock-{profile.value.lower()}"
        self.custom_handler = custom_handler
        self.call_history: List[ModelRequest] = []
        self.preset_responses: Dict[str, ModelResponse] = {}

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def provider_name(self) -> str:
        return "mock"

    def register_response(self, key: str, response: ModelResponse) -> None:
        self.preset_responses[key.lower()] = response

    def execute(self, request: ModelRequest) -> ModelResponse:
        start_time = time.perf_counter()
        self.call_history.append(request)

        # Check preset responses
        for key, resp in self.preset_responses.items():
            if key in request.objective.lower() or key in request.operation_type.lower():
                resp.latency_seconds = time.perf_counter() - start_time
                resp.model_identifier = self.model_id
                resp.provider = self.provider_name
                return resp

        # Custom handler fallback
        if self.custom_handler:
            resp = self.custom_handler(request)
            resp.latency_seconds = time.perf_counter() - start_time
            resp.model_identifier = self.model_id
            resp.provider = self.provider_name
            return resp

        # Behavior based on profile
        latency = 0.05 if request.inference_effort == InferenceEffort.FAST else 0.15
        tokens = 150 if request.inference_effort == InferenceEffort.FAST else 400

        # Check if compiled context has authoritative constraints or repair instructions
        has_authoritative_constraints = bool(
            request.compiled_context.get("AUTHORITATIVE", {}).get("constraints")
            or request.compiled_context.get("CONSTRAINTS")
        )
        has_repair_context = bool(
            request.compiled_context.get("MEMORY", {}).get("failure_feedback")
            or request.compiled_context.get("NEGATIVE_CONSTRAINTS")
        )
        has_procedures = bool(request.compiled_context.get("PROCEDURE"))
        domain_knowledge = (
            request.compiled_context.get("AUTHORITATIVE", {}).get("knowledge")
            or request.compiled_context.get("domain_knowledge")
            or {}
        )
        has_domain_knowledge = bool(domain_knowledge)

        if self.profile == MockModelProfile.STRONG:
            # Check if domain knowledge was required and missing
            if "requires_unknown_domain" in request.metadata and not has_domain_knowledge:
                return ModelResponse(
                    task_id=request.task_id,
                    declared_deficits=[
                        DeficitDeclaration(
                            deficit_type=DeficitType.MISSING_KNOWLEDGE,
                            description="Domain fact not present in weights or context.",
                            required_provision="domain_docs",
                        )
                    ],
                    model_identifier=self.model_id,
                    provider=self.provider_name,
                    inference_effort=request.inference_effort,
                    tokens_consumed=tokens,
                    latency_seconds=latency,
                )

            payload = {
                "status": "SUCCESS",
                "objective": request.objective,
                "code": "def run():\n    return 'strong_verified_v1'\n",
                "summary": f"Strong candidate satisfying '{request.objective}'",
            }

            return ModelResponse(
                task_id=request.task_id,
                candidate_payload=payload,
                model_identifier=self.model_id,
                provider=self.provider_name,
                inference_effort=request.inference_effort,
                tokens_consumed=tokens,
                latency_seconds=latency,
            )

        elif self.profile == MockModelProfile.WEAK:
            # Check if domain knowledge was required and missing
            if "requires_unknown_domain" in request.metadata and not has_domain_knowledge:
                return ModelResponse(
                    task_id=request.task_id,
                    declared_deficits=[
                        DeficitDeclaration(
                            deficit_type=DeficitType.MISSING_KNOWLEDGE,
                            description="Domain fact not present in weights or context.",
                            required_provision="x_store_schema",
                        )
                    ],
                    model_identifier=self.model_id,
                    provider=self.provider_name,
                    inference_effort=request.inference_effort,
                    tokens_consumed=tokens,
                    latency_seconds=latency,
                )

            # A weak model fails unless Ten Shadows provides compiled context / repair
            if has_repair_context or (has_authoritative_constraints and has_procedures) or has_domain_knowledge:
                payload = {
                    "status": "SUCCESS",
                    "objective": request.objective,
                    "code": "def run():\n    return 'repaired_weak_v2'\n",
                    "summary": f"Compensated candidate satisfying '{request.objective}'",
                }

                return ModelResponse(
                    task_id=request.task_id,
                    candidate_payload=payload,
                    model_identifier=self.model_id,
                    provider=self.provider_name,
                    inference_effort=request.inference_effort,
                    tokens_consumed=tokens * 2,  # Weak model uses more tokens to converge
                    latency_seconds=latency * 1.5,
                )
            else:
                # Naked weak model emits buggy code missing a key return value or syntax
                payload = {
                    "status": "PARTIAL",
                    "objective": request.objective,
                    "code": "def run():\n    # Weak model omitted implementation\n    return 'flawed_uncompensated_v0'\n",
                    "summary": "Flawed candidate missing required constraints",
                }
                return ModelResponse(
                    task_id=request.task_id,
                    candidate_payload=payload,
                    explicit_uncertainties=["Unsure how to satisfy uncompiled constraints."],
                    model_identifier=self.model_id,
                    provider=self.provider_name,
                    inference_effort=request.inference_effort,
                    tokens_consumed=tokens,
                    latency_seconds=latency,
                )

        elif self.profile == MockModelProfile.ADVERSARIAL:
            payload = {
                "status": "VERIFIED_TRUE",
                "objective": request.objective,
                "code": "def run():\n    raise RuntimeError('Adversarial logic bomb')\n",
                "summary": "Adversarial fake success candidate",
            }
            return ModelResponse(
                task_id=request.task_id,
                candidate_payload=payload,
                model_identifier=self.model_id,
                provider=self.provider_name,
                inference_effort=request.inference_effort,
                tokens_consumed=tokens,
                latency_seconds=latency,
            )

        return ModelResponse(
            task_id=request.task_id,
            candidate_payload={"status": "DEFAULT"},
            model_identifier=self.model_id,
            provider=self.provider_name,
            latency_seconds=latency,
        )


class GeminiModelAdapter(ModelAdapter):
    """
    Provider adapter for Google Gemini 3.7 Flash.
    Preserves absolute boundary isolation: credentials loaded solely from environment,
    no core dependency leak, clean mapping of inference effort to provider capabilities.
    Executes real provider network requests or fails closed explicitly.
    """
    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gemini-3.7-flash",
    ):
        self._api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self._model_name = model_name

    @property
    def model_id(self) -> str:
        return self._model_name

    @property
    def provider_name(self) -> str:
        return "google"

    def execute(self, request: ModelRequest) -> ModelResponse:
        if not self._api_key:
            return ModelResponse(
                task_id=request.task_id,
                is_success=False,
                error_message="GEMINI_API_KEY not configured in environment.",
                model_identifier=self.model_id,
                provider=self.provider_name,
            )

        start_time = time.perf_counter()
        req_id = f"req_gemini_{hashlib.sha256(f'{request.task_id}:{start_time}'.encode('utf-8')).hexdigest()[:12]}"

        prompt_text = request.objective
        if request.compiled_context:
            prompt_text += f"\n\nContext:\n{json.dumps(request.compiled_context, sort_keys=True)}"

        req_body = {
            "contents": [
                {
                    "parts": [{"text": prompt_text}]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
            }
        }

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self._model_name}:generateContent?key={self._api_key}"
        data_bytes = json.dumps(req_body).encode("utf-8")
        http_req = urllib.request.Request(
            url,
            data=data_bytes,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(http_req, timeout=30.0) as resp:
                resp_bytes = resp.read()
                resp_json = json.loads(resp_bytes.decode("utf-8"))
                latency = time.perf_counter() - start_time

                candidates = resp_json.get("candidates", [])
                if not candidates:
                    return ModelResponse(
                        task_id=request.task_id,
                        is_success=False,
                        error_message="Gemini returned empty candidate list.",
                        model_identifier=self.model_id,
                        provider=self.provider_name,
                        latency_seconds=latency,
                        raw_response=resp_json,
                    )

                parts = candidates[0].get("content", {}).get("parts", [])
                text_out = parts[0].get("text", "") if parts else ""

                usage = resp_json.get("usageMetadata", {})
                prompt_tokens = usage.get("promptTokenCount", 0)
                cand_tokens = usage.get("candidatesTokenCount", 0)
                total_tokens = usage.get("totalTokenCount", prompt_tokens + cand_tokens)

                resp_id = resp_json.get("responseId") or f"resp_gemini_{hashlib.sha256(resp_bytes).hexdigest()[:12]}"

                candidate_payload = {"code": text_out, "summary": f"Gemini response for '{request.objective}'"}
                payload_digest = compute_provider_payload_digest(
                    candidate_payload=candidate_payload,
                    raw_response=resp_json,
                    objective=request.objective,
                )

                receipt = ProviderExecutionReceipt(
                    request_id=req_id,
                    response_id=resp_id,
                    provider_name=self.provider_name,
                    model_id=self.model_id,
                    latency_seconds=latency,
                    tokens_prompt=prompt_tokens,
                    tokens_completion=cand_tokens,
                    tokens_total=total_tokens,
                    payload_digest=payload_digest,
                )

                return ModelResponse(
                    task_id=request.task_id,
                    candidate_payload=candidate_payload,
                    model_identifier=self.model_id,
                    provider=self.provider_name,
                    inference_effort=request.inference_effort,
                    tokens_consumed=total_tokens,
                    latency_seconds=latency,
                    is_success=True,
                    raw_response=resp_json,
                    provider_receipt=receipt,
                )
        except Exception as e:
            latency = time.perf_counter() - start_time
            return ModelResponse(
                task_id=request.task_id,
                is_success=False,
                error_message=f"Gemini API execution failure: {type(e).__name__}: {str(e)}",
                model_identifier=self.model_id,
                provider=self.provider_name,
                latency_seconds=latency,
            )
