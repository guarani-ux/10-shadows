"""
tests/test_deficit_protocol.py
Tests for First-Class Deficit Protocol & Resolution Loop (10 SHADOWS).
"""

from loop_engine.model.boundary import (
    DeficitDeclaration,
    DeficitType,
    MockModelAdapter,
    MockModelProfile,
    ModelRequest,
    ModelResponse,
)
from loop_engine.model.context_compiler import ContextCompiler
from loop_engine.model.deficit_protocol import (
    DeficitResolutionLoop,
    InProcessDeficitResolver,
)


def test_deficit_resolution_provisions_knowledge_and_retries():
    compiler = ContextCompiler()
    resolver = InProcessDeficitResolver(
        knowledge_base={"section_179d": "The 2026 inflation multiplier is 1.15; rate is 0.50 per sqft."}
    )
    loop = DeficitResolutionLoop(context_compiler=compiler, resolver=resolver)

    # Setup adapter that initially declares a deficit, then produces code once knowledge is provisioned
    call_count = 0

    def custom_handler(req: ModelRequest) -> ModelResponse:
        nonlocal call_count
        call_count += 1
        has_knowledge = "section_179d" in req.compiled_context.get("AUTHORITATIVE", {}).get("knowledge", {})
        if not has_knowledge:
            return ModelResponse(
                task_id=req.task_id,
                declared_deficits=[
                    DeficitDeclaration(
                        deficit_type=DeficitType.MISSING_KNOWLEDGE,
                        description="Needs Section 179D formula",
                        required_provision="section_179d",
                    )
                ],
                model_identifier="mock-weak",
                provider="mock",
            )
        return ModelResponse(
            task_id=req.task_id,
            candidate_payload={"code": "def calc(): return 0.50 * 1.15\n", "status": "SUCCESS"},
            model_identifier="mock-weak",
            provider="mock",
        )

    adapter = MockModelAdapter(custom_handler=custom_handler)
    base_req = ModelRequest(task_id="task_def_01", objective="Compute 179D deduction")

    final_resp, cycles, history = loop.run_with_deficit_resolution(
        adapter=adapter,
        base_request=base_req,
        objective="Compute 179D deduction",
    )

    assert cycles == 1
    assert len(history) == 1
    assert history[0].is_resolved is True
    assert final_resp.candidate_payload.get("status") == "SUCCESS"
    assert call_count == 2


def test_unresolvable_deficit_halts_without_infinite_loop():
    compiler = ContextCompiler()
    resolver = InProcessDeficitResolver(knowledge_base={})  # Empty knowledge base
    loop = DeficitResolutionLoop(context_compiler=compiler, resolver=resolver, max_deficit_cycles=2)

    def deficit_handler(req: ModelRequest) -> ModelResponse:
        return ModelResponse(
            task_id=req.task_id,
            declared_deficits=[
                DeficitDeclaration(
                    deficit_type=DeficitType.MISSING_CAPABILITY,
                    description="Requires quantum annealing processor",
                    required_provision="quantum_annealer",
                )
            ],
            model_identifier="mock-weak",
            provider="mock",
        )

    adapter = MockModelAdapter(custom_handler=deficit_handler)
    base_req = ModelRequest(task_id="task_unres", objective="Solve TSP with quantum annealer")

    final_resp, cycles, history = loop.run_with_deficit_resolution(
        adapter=adapter,
        base_request=base_req,
        objective="Solve TSP",
    )

    assert cycles == 0
    assert len(final_resp.declared_deficits) == 1
    assert final_resp.declared_deficits[0].required_provision == "quantum_annealer"
