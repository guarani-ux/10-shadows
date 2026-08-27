"""
zero_trust_engine/db.py
Re-exports the unified authoritative KernelDatabase from loop_engine.kernel_db.
Eliminates duplicate database authorities.
"""

from loop_engine.kernel_db import (
    KernelDatabase,
    KERNEL_DB_PATH,
    ProposalAlreadySealedError,
    IllegalStateTransitionError,
    ReceiptNotFoundError,
    ReceiptMismatchError,
)

# For backward compatibility within zero_trust_engine
StateDatabase = KernelDatabase

__all__ = [
    "KernelDatabase",
    "StateDatabase",
    "KERNEL_DB_PATH",
    "ProposalAlreadySealedError",
    "IllegalStateTransitionError",
    "ReceiptNotFoundError",
    "ReceiptMismatchError",
]
