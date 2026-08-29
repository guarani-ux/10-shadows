import pytest

from loop_engine.slicer.slicer_engine import AutonomousSlicerEngine


def test_autonomous_slicer_engine():
    engine = AutonomousSlicerEngine()
    dag = engine.slice_engineering_goal(
        goal_description="Build a rate-limited API gateway",
        goal_id="goal_gateway",
        base_package_name="gateway",
    )

    assert dag.goal_id == "goal_gateway"
    assert len(dag.slices) == 3

    order = dag.get_execution_order()
    assert len(order) == 3
    assert order[0].slice_number == 1
    assert "core.py" in order[0].target_module
    assert order[1].slice_number == 2
    assert "schema.py" in order[1].target_module
    assert order[2].slice_number == 3
    assert "runner.py" in order[2].target_module
