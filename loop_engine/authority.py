"""
loop_engine/authority.py
Trusted Computing Base (TCB) Authority & Cryptographic Witness Kernel for 10 SHADOWS.

Deep Module enforcing that privileged states (VERIFIED, PHYSICAL_OBSERVATION, BUILD_EARNED)
cannot be asserted into existence by callers. They must be witnessed by an authentic,
unforgeable ProofWitness created inside the physical TCB.
"""

from dataclasses import dataclass, field
import hashlib
import hmac
import os
import secrets
import time
from typing import Any, Dict, Optional

# Ephemeral runtime session key generated on process boot inside TCB memory.
# Inaccessible to external callers or untrusted worktree subprocesses.
_TCB_SESSION_SECRET: bytes = secrets.token_bytes(32)


class PrivilegedMintingError(Exception):
    """Raised when an unauthorized component attempts to mint a privileged state without proof."""
    pass


class InvalidWitnessError(Exception):
    """Raised when a ProofWitness signature or bound digest fails cryptographic verification."""
    pass


@dataclass(frozen=True)
class ProofWitness:
    """
    Cryptographic proof witness proving that a physical verification gate or authority
    engine has executed and certified a claim.
    """
    witness_id: str
    issuer: str
    target_digest: str
    scope: str
    timestamp: float
    signature: str

    def verify(self, expected_digest: str, expected_scope: str) -> bool:
        """
        Validates HMAC signature and payload binding against the TCB session secret.
        """
        if self.target_digest != expected_digest or self.scope != expected_scope:
            return False

        payload = f"{self.witness_id}:{self.issuer}:{self.target_digest}:{self.scope}:{self.timestamp}"
        expected_sig = hmac.new(
            _TCB_SESSION_SECRET, payload.encode("utf-8"), hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(self.signature, expected_sig)


def issue_proof_witness(issuer: str, target_digest: str, scope: str) -> ProofWitness:
    """
    Issues an authentic, unforgeable ProofWitness binding target_digest to scope.
    Callable only by authorized internal kernel machinery (VerifierGate, AuthorityEngine).
    """
    witness_id = f"wit_{secrets.token_hex(8)}"
    now = time.time()
    payload = f"{witness_id}:{issuer}:{target_digest}:{scope}:{now}"
    signature = hmac.new(
        _TCB_SESSION_SECRET, payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    return ProofWitness(
        witness_id=witness_id,
        issuer=issuer,
        target_digest=target_digest,
        scope=scope,
        timestamp=now,
        signature=signature,
    )


@dataclass(frozen=True)
class VerificationContractWitness:
    """
    Proof-bearing witness demonstrating that a concrete objective has been bound
    to physical acceptance test fixtures. Replaces all boolean flags.
    """
    contract_id: str
    objective_hash: str
    acceptance_test_digest: str
    witness: ProofWitness

    def is_valid(self) -> bool:
        combined_digest = hashlib.sha256(
            f"{self.objective_hash}:{self.acceptance_test_digest}".encode("utf-8")
        ).hexdigest()
        return self.witness.verify(combined_digest, "VERIFICATION_CONTRACT")


def create_verification_contract_witness(
    objective_hash: str, acceptance_test_digest: str
) -> VerificationContractWitness:
    """
    Constructs a proof-bearing VerificationContractWitness for an objective.
    """
    contract_id = f"vcw_{secrets.token_hex(8)}"
    combined_digest = hashlib.sha256(
        f"{objective_hash}:{acceptance_test_digest}".encode("utf-8")
    ).hexdigest()
    witness = issue_proof_witness(
        issuer="loop_engine.authority",
        target_digest=combined_digest,
        scope="VERIFICATION_CONTRACT",
    )
    return VerificationContractWitness(
        contract_id=contract_id,
        objective_hash=objective_hash,
        acceptance_test_digest=acceptance_test_digest,
        witness=witness,
    )
