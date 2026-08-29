"""
loop_engine/model package
Canonical Model Boundary & Decoupling Substrate for 10 SHADOWS.
"""

from loop_engine.model.benchmark import (
    BenchmarkDimension,
    BenchmarkResult,
    BenchmarkRunner,
    BenchmarkTask,
    EvidenceQualification,
    TaskRunRecord,
    create_canonical_benchmark_corpus,
    create_deterministic_knowledge_task,
)
from loop_engine.model.boundary import (
    DeficitDeclaration,
    DeficitType,
    EvidenceModality,
    GeminiModelAdapter,
    InferenceEffort,
    MockModelAdapter,
    MockModelProfile,
    ModelAdapter,
    ModelRequest,
    ModelResponse,
    ProviderExecutionReceipt,
    compute_provider_payload_digest,
)
from loop_engine.model.candidate_search import (
    CandidateEvaluation,
    SearchEngine,
    SearchPolicy,
    TaskDifficulty,
)
from loop_engine.model.context_compiler import (
    CompiledContext,
    ContextClass,
    ContextCompiler,
)
from loop_engine.model.deficit_protocol import (
    DeficitProvisionResult,
    DeficitResolutionLoop,
    DeficitResolver,
    InProcessDeficitResolver,
)

__all__ = [
    "DeficitDeclaration",
    "DeficitType",
    "EvidenceModality",
    "GeminiModelAdapter",
    "InferenceEffort",
    "MockModelAdapter",
    "MockModelProfile",
    "ModelAdapter",
    "ModelRequest",
    "ModelResponse",
    "ProviderExecutionReceipt",
    "compute_provider_payload_digest",
    "CompiledContext",
    "ContextClass",
    "ContextCompiler",
    "DeficitProvisionResult",
    "DeficitResolutionLoop",
    "DeficitResolver",
    "InProcessDeficitResolver",
    "CandidateEvaluation",
    "SearchEngine",
    "SearchPolicy",
    "TaskDifficulty",
    "BenchmarkDimension",
    "BenchmarkResult",
    "BenchmarkRunner",
    "BenchmarkTask",
    "EvidenceQualification",
    "TaskRunRecord",
    "create_canonical_benchmark_corpus",
    "create_deterministic_knowledge_task",
]
