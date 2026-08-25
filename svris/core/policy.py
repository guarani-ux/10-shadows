"""Deterministic Verification Policy Engine.

Replaces model confidence with mechanical verification rules based on trust tiers,
exact quote evidence spans, and independent support.
"""

from typing import Dict, Any, Tuple


class VerificationPolicy:
    POLICY_VERSION = "2026.08.1"

    @classmethod
    def evaluate(
        cls,
        trust_tier: str,
        relationship_state: str,
        quote_verified: bool,
        independent_sources: int = 1,
    ) -> Tuple[str, Dict[str, Any]]:
        """Evaluates truth state deterministically.

        Returns (new_state, basis_dict).
        """
        basis: Dict[str, Any] = {
            "policy_version": cls.POLICY_VERSION,
            "trust_tier": trust_tier,
            "relationship_state": relationship_state,
            "quote_verified": quote_verified,
            "independent_sources": independent_sources,
        }

        # Untrusted sources alone can NEVER promote to VERIFIED
        if trust_tier == "UNTRUSTED_RETRIEVAL":
            if independent_sources >= 2 and quote_verified and relationship_state == "SUPPORTS":
                basis["reason"] = "Corroborated by multiple independent untrusted sources"
                return "VERIFIED", basis
            basis["reason"] = "UNTRUSTED_RETRIEVAL source without independent corroboration"
            return "UNVERIFIED", basis

        # Verified Primary or Authoritative Secondary
        if relationship_state == "SUPPORTS":
            if quote_verified:
                basis["reason"] = "Supported by verified source with exact quote match"
                return "VERIFIED", basis
            else:
                basis["reason"] = "Supported by source but quote span could not be mechanically verified"
                return "UNVERIFIED", basis

        if relationship_state == "CONTRADICTS":
            basis["reason"] = "Explicit contradiction detected"
            return "CONTRADICTED", basis

        basis["reason"] = f"Relationship '{relationship_state}' does not establish positive support"
        return "UNVERIFIED", basis
