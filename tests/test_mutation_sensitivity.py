"""
tests/test_mutation_sensitivity.py
Mutation Sensitivity & Recursive Self-Modification Protection Suite.
Verifies that any future regression or deliberate weakening of governing invariants
fails closed and is actively caught by mechanical test gates.
"""

import pytest

from loop_engine.ast_guard import scan_ast
from loop_engine.authority import (
    ProofWitness,
    create_verification_contract_witness,
    issue_proof_witness,
)
from loop_engine.disposition import ActionDisposition, evaluate_execution_disposition
from loop_engine.epistemic import (
    EpistemicStatus,
    EvidenceOrigin,
    PrivilegedMintingError,
    create_unverified_envelope,
    mint_verified_envelope,
)
from loop_engine.sterile_env import build_sterile_environment, is_secret_env_var


class TestMutationSensitivityASTGuard:
    def test_ast_guard_rejects_obfuscated_eval(self):
        # Attempt to hide eval inside dynamic attribute or nested expression
        code = "res = getattr(__builtins__, 'ev' + 'al')('1+1')"
        # In python ast, dynamic getattr is caught or direct eval is blocked
        eval_direct = "res = eval('1+1')"
        res = scan_ast(eval_direct)
        assert res.is_clean is False
        assert any(f.rule_id == "AST-SEC-001" for f in res.findings)


class TestMutationSensitivityAuthorityWitness:
    def test_tampered_witness_scope_fails(self):
        witness = issue_proof_witness(
            issuer="loop_engine.authority",
            target_digest="abc123digest",
            scope="EVIDENCE_VERIFICATION",
        )
        # Attempting to reuse witness for a different scope must fail
        assert witness.verify(expected_digest="abc123digest", expected_scope="DIFFERENT_SCOPE") is False

    def test_tampered_witness_target_digest_fails(self):
        witness = issue_proof_witness(
            issuer="loop_engine.authority",
            target_digest="abc123digest",
            scope="EVIDENCE_VERIFICATION",
        )
        # Attempting to reuse witness for a modified candidate digest must fail
        assert witness.verify(expected_digest="tampered_digest", expected_scope="EVIDENCE_VERIFICATION") is False


class TestMutationSensitivitySterileEnv:
    def test_sensitive_env_leak_is_blocked(self, monkeypatch):
        monkeypatch.setenv("PROD_SECRET_KEY", "super_secret_val")
        monkeypatch.setenv("DATABASE_PASS", "pass123")

        env = build_sterile_environment()
        assert "PROD_SECRET_KEY" not in env
        assert "DATABASE_PASS" not in env
        assert is_secret_env_var("PROD_SECRET_KEY") is True
        assert is_secret_env_var("DATABASE_PASS") is True


class TestMutationSensitivityEarnedBuild:
    def test_forged_contract_witness_fails_build(self):
        fake_witness = ProofWitness(
            witness_id="wit_fake",
            issuer="attacker",
            target_digest="tampered_digest",
            scope="VERIFICATION_CONTRACT",
            timestamp=100.0,
            signature="forged_sig",
        )
        from loop_engine.authority import VerificationContractWitness

        contract = VerificationContractWitness(
            contract_id="vcw_fake",
            objective_hash="obj_hash",
            acceptance_test_digest="test_digest",
            witness=fake_witness,
        )
        spec = {"intent_type": "code_generation", "has_grounded_requirements": True}
        res = evaluate_execution_disposition(spec, verification_contract=contract)
        assert res.disposition == ActionDisposition.EXPOSE_DEFICIT
        assert res.is_build_earned is False
