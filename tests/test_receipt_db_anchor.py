from __future__ import annotations

import json

from loop_engine.execution_authority import (
    RunStatus,
    TenShadowsKernel,
    TenShadowsReceipt,
    verify_execution_receipt,
)
from loop_engine.kernel_db import KernelDatabase


def test_recomputed_receipt_digest_cannot_override_authoritative_db_record(tmp_path):
    db = KernelDatabase(db_path=tmp_path / "kernel.db")
    receipts_dir = tmp_path / "receipts"
    receipts_dir.mkdir()
    target = tmp_path / "target"
    target.mkdir()
    kernel = TenShadowsKernel(kernel_db=db, receipts_dir=receipts_dir)

    run_ctx = kernel.establish_run("trivial: receipt anchor proof", target)
    strategy, capabilities, route_digest = kernel.determine_route(run_ctx, "trivial: receipt anchor proof")
    receipt = kernel.seal_and_persist_receipt(
        run_ctx=run_ctx,
        objective="trivial: receipt anchor proof",
        target_path=target,
        starting_head=None,
        final_head=None,
        routing_strategy=strategy,
        routing_decision_digest=route_digest,
        capabilities_selected=capabilities,
        attempts=[],
        worker_invocations=[],
        artifacts_produced=[],
        verification=None,
        promotion=None,
        final_status=RunStatus.COMPLETED_UNVERIFIED,
        verification_scope="unknown",
    )

    original_valid, original_errors = verify_execution_receipt(receipt.model_dump(), kernel_db=db)
    assert original_valid is True
    assert original_errors == []

    forged_data = json.loads(receipt.model_dump_json())
    forged_data["routing_decision_digest"] = "f" * 64
    forged = TenShadowsReceipt.model_validate(forged_data)
    forged.receipt_signature = forged.compute_signature()

    forged_valid, forged_errors = verify_execution_receipt(forged.model_dump(), kernel_db=db)
    assert forged_valid is False
    assert any("authoritative persisted receipt record" in error for error in forged_errors)
