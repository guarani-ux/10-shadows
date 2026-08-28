"""
tests/test_model_degradation_mutations.py
Model Degradation & Authority Safety Mutation Tests (10 SHADOWS).

Demonstrates that model degradation results in more system work (re-compilation, search, repair)
rather than silent false success, and proves that AI models have zero authority to mint privileged truth.
"""

from loop_engine.model.boundary import (
    DeficitDeclaration,
    DeficitType,
    MockModelAdapter,
    MockModelProfile,
    ModelRequest,
    ModelResponse,
)
from loop_engine.model.candidate_search import (
    CandidateEvaluation,
    SearchEngine,
    TaskDifficulty,
)
from loop_engine.model.context_compiler import ContextCompiler
from loop_engine.schema import State
from loop_engine.kernel_db import KernelDatabase, PrivilegedStateMutationProhibitedError


def test_model_omits_constraint_survives_in_canonical_context():
    compiler = ContextCompiler()
    compiled = compiler.compile(
        objective="Transfer funds",
        constraints=["Check balance before debit", "Sign transaction with HSM"],
    )
    # The constraint exists physically in the compiled context regardless of what the model emits
    assert "Check balance before debit" in compiled.authoritative["constraints"]
    assert "Sign transaction with HSM" in compiled.authoritative["constraints"]


def test_model_claims_success_without_evidence_rejected_by_authority():
    """
    Authority Safety: A model claiming 'VERIFIED_TRUE' cannot bypass the Physical Verifier Gate
    or create privileged state in KernelDatabase.
    """
    adv_adapter = MockModelAdapter(profile=MockModelProfile.ADVERSARIAL)
    req = ModelRequest(task_id="task_hack_auth", objective="Fake privileged access")
    resp = adv_adapter.execute(req)

    # Even though model returned status='VERIFIED_TRUE', evaluator marks it invalid
    eval_res = SearchEngine._default_evaluator(resp.candidate_payload)
    assert eval_res.is_valid is False

    # And attempting to directly write to DB is blocked
    db = KernelDatabase()
    import pytest
    with pytest.raises(PrivilegedStateMutationProhibitedError):
        db.transition_proposal_state("task_hack_auth", State.CANDIDATE_SEALED, State.VERIFIED)


def test_model_disagreement_resolved_by_physical_evidence():
    """
    When a model emits 3 candidate alternatives that disagree,
    the system ranks them using physical evaluation rather than model self-confidence.
    """
    compiler = ContextCompiler()
    engine = SearchEngine(context_compiler=compiler)

    candidates = [
        {"status": "CONFIDENT_100", "code": "def run(): raise RuntimeError()"},  # Bad
        {"status": "CONFIDENT_99", "code": "def run(): return 'flawed_uncompensated_v0'"},  # Incomplete
        {"status": "LOW_CONFIDENCE", "code": "def run(): return 'valid_working_impl'"},  # Valid!
    ]

    custom_adapter = MockModelAdapter(
        custom_handler=lambda r: ModelResponse(
            task_id=r.task_id,
            candidate_payload=candidates[0],
            structured_alternatives=candidates[1:],
            model_identifier="test-disagree",
            provider="mock",
        )
    )

    base_req = ModelRequest(task_id="task_disagree", objective="Select correct candidate")
    winning_eval, all_evals, calls = engine.execute_search(
        adapter=custom_adapter,
        base_request=base_req,
        objective="Select correct candidate",
        difficulty=TaskDifficulty.HIGH,
    )

    # The valid candidate with lowest model self-confidence won because of physical evidence!
    assert winning_eval.is_valid is True
    assert winning_eval.payload["code"] == "def run(): return 'valid_working_impl'"
