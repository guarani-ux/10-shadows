"""
tests/test_context_compiler.py
Tests for the Deterministic Context Compiler (10 SHADOWS).
"""

from loop_engine.canonical_objective import CanonicalObjective
from loop_engine.capability import CapabilityContract
from loop_engine.context import RunContext
from loop_engine.model.boundary import DeficitDeclaration, DeficitType
from loop_engine.model.context_compiler import ContextClass, ContextCompiler


def test_context_compiler_preserves_authority_classes():
    compiler = ContextCompiler(
        governance_rules={"strike_ceiling": 3},
        procedures_registry={"tdd": "1. Write test -> 2. Write code -> 3. Verify"},
    )

    run_ctx = RunContext.create(
        task_id="task_ctx_01",
        shadow_id=1,
        domain_code="ALCHEMIST",
        raw_objective="Synthesize unit test",
    )

    cap_contract = CapabilityContract(
        capability_id="cap_ast_01",
        domain="python",
        supported_objective_types=("code_generation",),
        input_schema_digest="in_hash",
        output_schema_digest="out_hash",
    )

    compiled = compiler.compile(
        objective="Synthesize unit test",
        run_context=run_ctx,
        constraints=["Zero mutable globals", "Deterministic execution"],
        verified_evidence=[{"evidence_id": "ev_01", "trace": "Passed AST gate"}],
        applicable_procedure="tdd",
        failure_history=[
            {
                "signature": "SIG_SYNTAX_ERR",
                "classification": "CANDIDATE_FAILURE",
                "root_cause": "Missing colon on line 12",
                "negative_constraint": "DO NOT REPEAT: Syntax error on class def",
            }
        ],
        available_tools=[cap_contract],
        declared_deficits=[
            DeficitDeclaration(
                deficit_type=DeficitType.MISSING_KNOWLEDGE,
                description="Needs Section 179D rules",
            )
        ],
    )

    as_dict = compiled.to_dict()
    assert ContextClass.AUTHORITATIVE.value in as_dict
    assert ContextClass.STATE.value in as_dict
    assert ContextClass.PROCEDURE.value in as_dict
    assert ContextClass.MEMORY.value in as_dict
    assert ContextClass.TOOLS.value in as_dict
    assert ContextClass.UNCERTAINTY.value in as_dict

    # Check that Authoritative context contains constraints and evidence
    assert "Zero mutable globals" in as_dict["AUTHORITATIVE"]["constraints"]
    assert as_dict["AUTHORITATIVE"]["verified_evidence"][0]["evidence_id"] == "ev_01"

    # Check Memory context contains distilled failures
    assert as_dict["MEMORY"]["failure_feedback"][0]["signature"] == "SIG_SYNTAX_ERR"
    assert "DO NOT REPEAT: Syntax error on class def" in as_dict["MEMORY"]["negative_constraints"]

    # Check Procedure contains externalized methodology
    assert as_dict["PROCEDURE"]["name"] == "tdd"

    # Check deterministic digest
    assert len(compiled.context_digest) == 64
    assert compiled.context_digest == compiled.compute_digest()


def test_context_compiler_with_canonical_objective():
    compiler = ContextCompiler()
    obj = CanonicalObjective(
        objective_id="obj_canon_01",
        description="Refactor authentication seam",
        desired_outcome="Subprocess tests return 0",
        objective_type="general_execution",
        forbidden_actions=["direct_production_write"],
    )

    compiled = compiler.compile(objective=obj, constraints=["Preserve constant-time comparison"])
    auth = compiled.authoritative
    assert auth["objective_id"] == "obj_canon_01"
    assert auth["description"] == "Refactor authentication seam"
    assert "Preserve constant-time comparison" in auth["constraints"]
    assert "direct_production_write" in auth["forbidden_actions"]
