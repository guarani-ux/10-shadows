from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class VerticalSliceTask(BaseModel):
    """An irreducible, testable vertical slice in a DAG."""

    slice_id: str = Field(description="e.g. 'slice_1_core_engine'")
    slice_number: int = Field(ge=1, le=10)
    title: str = Field(min_length=3)
    objective: str = Field(min_length=10)
    target_module: str = Field(description="Target file path to create/modify")
    target_test: str = Field(description="Test file path to verify the slice")
    dependencies: List[str] = Field(default_factory=list, description="IDs of preceding slices that must pass first")
    invariants: List[str] = Field(default_factory=list, description="Structural rules this slice must not violate")


class SliceDAG(BaseModel):
    """The complete directed acyclic graph decomposing a macro goal."""

    goal_id: str
    goal_description: str
    slices: List[VerticalSliceTask] = Field(min_length=1, max_length=10)

    def get_execution_order(self) -> List[VerticalSliceTask]:
        """Returns topological ordering of slices based on dependencies."""
        executed = set()
        order = []
        remaining = list(self.slices)

        while remaining:
            progress = False
            for s in list(remaining):
                if all(dep in executed for dep in s.dependencies):
                    order.append(s)
                    executed.add(s.slice_id)
                    remaining.remove(s)
                    progress = True
            if not progress and remaining:
                raise ValueError(f"Cyclic dependency detected in SliceDAG among: {[s.slice_id for s in remaining]}")

        return order
