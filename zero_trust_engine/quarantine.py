"""
zero_trust_engine/quarantine.py
Re-exports the canonical QuarantineManager from loop_engine.quarantine.
"""

from loop_engine.quarantine import QuarantineManager, PathTraversalEscapeError

__all__ = ["QuarantineManager", "PathTraversalEscapeError"]
