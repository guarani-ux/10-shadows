import json
from pathlib import Path

import pytest

from loop_engine.artifacts import (
    ArtifactRecord,
    ArtifactRegistry,
    MasterAVScriptArtifact,
    ProductionPlanDAGArtifact,
    StructuredSourceArtifact,
)
from loop_engine.canonical_objective import EvidenceReference, UnknownReference
from loop_engine.herald.schema import AVTableRow, StrategicIntent, TechnicalScope, ValidatedCutDownScript
from loop_engine.kernel_db import KernelDatabase
from loop_engine.slicer.schema import VerticalSliceTask


def test_typed_semantic_handoff_schemas_and_hashing():
    """Proves typed semantic handoffs construct cleanly and compute deterministic content hashes."""
    # 1. StructuredSourceArtifact
    source_art = StructuredSourceArtifact(
        source_project_id="proj_energy_01",
        canonical_goal="Educate city residents on municipal solar microgrid.",
        target_audience="City homeowners and facility operators.",
        core_message="Clean sovereign energy storage reduces peak outages.",
        intended_audience_action="Register on the municipal portal.",
        verified_facts=[
            EvidenceReference(
                evidence_id="ev_01",
                source_description="Microgrid pilot reduced outages by 94% over 18 months.",
                confidence="DOCUMENTED_METRIC",
            )
        ],
        explicit_unknowns=[
            UnknownReference(
                unknown_id="unk_01",
                description="Substation interior clearance pending utility approval.",
                classification="ASSUMPTION_REQUIRING_APPROVAL",
                mitigation_or_approval_decision="Capture exterior perimeter with 85mm lens.",
            )
        ],
        historical_pacing_benchmarks={"corpus_avg_wpm": 148.5, "target_wpm": 150.0},
    )

    source_hash = source_art.compute_content_hash()
    assert len(source_hash) == 64

    # 2. MasterAVScriptArtifact
    script_art = MasterAVScriptArtifact(
        script_id="script_energy_01",
        source_artifact_id="art_scribe_123456",
        source_artifact_hash=source_hash,
        strategic_intent=StrategicIntent(
            project_title="Municipal Solar Microgrid",
            organizational_goal="Educate city residents on microgrid resilience.",
            target_audience_persona="Homeowners and facility operators.",
            intended_audience_action="Register on the portal.",
            core_brand_alignment="Sovereign and resilient community energy.",
            narrative_arc_type="Context -> Evidence -> Impact",
        ),
        technical_scope=TechnicalScope(
            target_runtime_seconds=60,
            target_runtime_formatted="1:00",
            target_pacing_wpm=150.0,
            total_spoken_words=148,
            actual_overall_wpm=148.0,
            production_constraints=dict(target_duration_seconds=60, target_pacing_wpm=150.0),
        ),
        verified_facts=source_art.verified_facts,
        explicit_unknowns=source_art.explicit_unknowns,
        av_table=[
            AVTableRow(
                row_index=1,
                scene_name="Scene 1 - Vulnerability",
                time_window="0:00 - 0:15",
                start_seconds=0.0,
                end_seconds=15.0,
                spoken_audio="When the primary grid goes dark, clean power remains online.",
                spoken_words_count=10,
                pacing_wpm=40.0,
                video_direction="MCU of technician with 85mm lens, 2:1 corporate natural key.",
                grounded_evidence_ids=["ev_01"],
            )
        ],
        rendered_markdown="| Section / Timecode | Spoken Human Audio | Cinematographic Video |\n| :--- | :--- | :--- |\n| 0:00 - 0:15 | Clean power remains online. | Medium shot. |",
    )

    script_hash = script_art.compute_content_hash()
    assert len(script_hash) == 64
    assert script_art.source_artifact_hash == source_hash

    # 3. ProductionPlanDAGArtifact
    plan_art = ProductionPlanDAGArtifact(
        plan_id="plan_energy_01",
        source_artifact_id="art_herald_654321",
        source_artifact_hash=script_hash,
        goal_id="goal_energy_shoot",
        goal_description="Execute production shoot for Municipal Solar Microgrid",
        ordered_tasks=[
            VerticalSliceTask(
                slice_id="slice_01",
                slice_number=1,
                title="Film Facility Establishing Shot",
                objective="Capture wide angle facility perimeter",
                target_module="production/scene_1.mp4",
                target_test="production/tests/test_scene_1.py",
                dependencies=[],
            )
        ],
        total_estimated_duration_seconds=60.0,
        critical_path=["slice_01"],
    )

    plan_hash = plan_art.compute_content_hash()
    assert len(plan_hash) == 64
    assert plan_art.source_artifact_hash == script_hash


def test_artifact_registry_idempotency_and_event_ledger(tmp_path):
    """Proves ArtifactRegistry enforces 8-tuple idempotency and records append-only events."""
    db_file = tmp_path / "scratch" / "test_kernel.db"
    storage_dir = tmp_path / "scratch" / "artifacts"
    kdb = KernelDatabase(db_path=db_file)
    registry = ArtifactRegistry(kernel_db=kdb, storage_dir=storage_dir)

    source_art = StructuredSourceArtifact(
        source_project_id="proj_solar_01",
        canonical_goal="Educate residents on solar microgrids",
        target_audience="Homeowners",
        core_message="Clean power storage",
        intended_audience_action="Register on portal",
    )

    # 1. Stage Artifact (Attempt 1)
    rec1 = registry.stage_artifact(
        artifact_obj=source_art,
        run_id="child_run_scribe_01",
        parent_run_id="parent_route_001",
        producing_shadow_id=6,
        domain_code="scribe",
        step_id="step_source_structuring",
        route_plan_hash="plan_hash_abc123",
        source_artifact_hash="root_objective_hash_000",
        source_commit="cac1a8053abf80880bf32b54f05c0c001b5a4af9",
        producer_version="1.0.0",
        validator_policy_fingerprint="scribe_policy_v1",
    )

    assert rec1.current_state == "STAGED"
    assert Path(rec1.storage_path).exists()

    # 2. Stage Identical Artifact (Attempt 2 - Idempotency Check)
    rec2 = registry.stage_artifact(
        artifact_obj=source_art,
        run_id="child_run_scribe_01",
        parent_run_id="parent_route_001",
        producing_shadow_id=6,
        domain_code="scribe",
        step_id="step_source_structuring",
        route_plan_hash="plan_hash_abc123",
        source_artifact_hash="root_objective_hash_000",
        source_commit="cac1a8053abf80880bf32b54f05c0c001b5a4af9",
        producer_version="1.0.0",
        validator_policy_fingerprint="scribe_policy_v1",
    )

    assert rec1.artifact_id == rec2.artifact_id
    assert rec1.idempotency_key == rec2.idempotency_key

    # Invariant: Must have exactly 1 record in artifacts table
    with kdb.get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM artifacts;").fetchone()[0]
        assert count == 1

    # 3. Transition State: STAGED -> VERIFIED -> PROMOTED
    registry.transition_state(
        artifact_id=rec1.artifact_id,
        to_state="VERIFIED",
        reason="PASSED_SCRIBE_STRUCTURE_AUDIT",
        actor_domain="svris",
        validator_results={"status": "PASS", "score": 1.0},
    )

    registry.transition_state(
        artifact_id=rec1.artifact_id,
        to_state="PROMOTED",
        reason="PROMOTED_TO_NEXT_STEP",
        actor_domain="router",
    )

    # 4. Verify Append-Only History Ledger
    history = registry.get_artifact_history(rec1.artifact_id)
    assert len(history) == 3
    assert history[0]["to_state"] == "STAGED"
    assert history[1]["to_state"] == "VERIFIED"
    assert history[2]["to_state"] == "PROMOTED"


def test_artifact_registry_restart_recovery_environment_binding(tmp_path):
    """Proves restart recovery returns verified artifact only if complete verification environment matches."""
    db_file = tmp_path / "scratch" / "test_kernel.db"
    storage_dir = tmp_path / "scratch" / "artifacts"
    kdb = KernelDatabase(db_path=db_file)
    registry = ArtifactRegistry(kernel_db=kdb, storage_dir=storage_dir)

    source_art = StructuredSourceArtifact(
        source_project_id="proj_solar_01",
        canonical_goal="Educate residents on solar microgrids",
        target_audience="Homeowners",
        core_message="Clean power storage",
        intended_audience_action="Register on portal",
    )

    rec = registry.stage_artifact(
        artifact_obj=source_art,
        run_id="child_run_scribe_01",
        parent_run_id="parent_route_001",
        producing_shadow_id=6,
        domain_code="scribe",
        step_id="step_source_structuring",
        route_plan_hash="plan_hash_abc123",
        source_artifact_hash="root_objective_hash_000",
        source_commit="cac1a8053abf80880bf32b54f05c0c001b5a4af9",
        producer_version="1.0.0",
        validator_policy_fingerprint="scribe_policy_v1",
    )

    # Invariant: Unverified artifact must NOT be returned for resume
    cached = registry.find_verified_artifact(
        parent_run_id="parent_route_001",
        route_plan_hash="plan_hash_abc123",
        step_id="step_source_structuring",
        source_artifact_hash="root_objective_hash_000",
        source_commit="cac1a8053abf80880bf32b54f05c0c001b5a4af9",
        producer_version="1.0.0",
        validator_policy_fingerprint="scribe_policy_v1",
        output_schema_version="1.0.0",
    )
    assert cached is None

    # Promote artifact to VERIFIED
    registry.transition_state(
        artifact_id=rec.artifact_id,
        to_state="VERIFIED",
        reason="PASSED_VERIFICATION",
        actor_domain="svris",
    )

    # Exact match: Must return cached record
    cached_ok = registry.find_verified_artifact(
        parent_run_id="parent_route_001",
        route_plan_hash="plan_hash_abc123",
        step_id="step_source_structuring",
        source_artifact_hash="root_objective_hash_000",
        source_commit="cac1a8053abf80880bf32b54f05c0c001b5a4af9",
        producer_version="1.0.0",
        validator_policy_fingerprint="scribe_policy_v1",
        output_schema_version="1.0.0",
    )
    assert cached_ok is not None
    assert cached_ok.artifact_id == rec.artifact_id

    # Environment alteration: Source commit changed -> Must return None (cache miss)
    cached_commit_changed = registry.find_verified_artifact(
        parent_run_id="parent_route_001",
        route_plan_hash="plan_hash_abc123",
        step_id="step_source_structuring",
        source_artifact_hash="root_objective_hash_000",
        source_commit="different_commit_sha_12345678901234567890",
        producer_version="1.0.0",
        validator_policy_fingerprint="scribe_policy_v1",
        output_schema_version="1.0.0",
    )
    assert cached_commit_changed is None

    # Environment alteration: Validator policy changed -> Must return None (cache miss)
    cached_policy_changed = registry.find_verified_artifact(
        parent_run_id="parent_route_001",
        route_plan_hash="plan_hash_abc123",
        step_id="step_source_structuring",
        source_artifact_hash="root_objective_hash_000",
        source_commit="cac1a8053abf80880bf32b54f05c0c001b5a4af9",
        producer_version="1.0.0",
        validator_policy_fingerprint="strict_policy_v2_updated",
        output_schema_version="1.0.0",
    )
    assert cached_policy_changed is None
