import pytest

from loop_engine.slicer.schema import SliceDAG, VerticalSliceTask


def test_slice_dag_topological_sort():
    s1 = VerticalSliceTask(
        slice_id="slice_1",
        slice_number=1,
        title="Core Module",
        objective="Create core baseline class implementation",
        target_module="core.py",
        target_test="test_core.py",
        dependencies=[],
    )
    s2 = VerticalSliceTask(
        slice_id="slice_2",
        slice_number=2,
        title="Schema Layer",
        objective="Create validation contracts and models",
        target_module="schema.py",
        target_test="test_schema.py",
        dependencies=["slice_1"],
    )
    s3 = VerticalSliceTask(
        slice_id="slice_3",
        slice_number=3,
        title="Domain Runner",
        objective="Integrate core and schema into autonomous runner",
        target_module="runner.py",
        target_test="test_runner.py",
        dependencies=["slice_2"],
    )

    dag = SliceDAG(
        goal_id="goal_100",
        goal_description="Build a new domain module",
        slices=[s3, s1, s2],
    )

    execution_order = dag.get_execution_order()
    ordered_ids = [s.slice_id for s in execution_order]
    assert ordered_ids == ["slice_1", "slice_2", "slice_3"]


def test_slice_dag_detects_cycles():
    s1 = VerticalSliceTask(
        slice_id="slice_1",
        slice_number=1,
        title="Slice 1",
        objective="Execute first cycle work item",
        target_module="m1.py",
        target_test="t1.py",
        dependencies=["slice_2"],
    )
    s2 = VerticalSliceTask(
        slice_id="slice_2",
        slice_number=2,
        title="Slice 2",
        objective="Execute second cycle work item",
        target_module="m2.py",
        target_test="t2.py",
        dependencies=["slice_1"],
    )

    dag = SliceDAG(
        goal_id="goal_cycle",
        goal_description="Cyclic goal",
        slices=[s1, s2],
    )

    with pytest.raises(ValueError, match="Cyclic dependency detected"):
        dag.get_execution_order()
