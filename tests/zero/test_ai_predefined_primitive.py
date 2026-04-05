from simz.ai.memory import MemoryData, PerfectMemory
from zero.ai.actions import MatingAction
from zero.ai.context import PrimitiveBrainContext
from zero.ai.primitive import (
    PrimitiveGoal,
    PrimitiveGoalSelector,
    PrimitivePlanner,
)


def test_plan_reproduce():
    """Test planning for reproduction goal"""
    # Arrange
    ctx = PrimitiveBrainContext(
        simulation_time=0,
        etype="animal",
        eid=1,
        hunger=0.3,
        energy=0.8,
        is_pregnant=False,
        memory_data=MemoryData(),
        memory_engine=PerfectMemory(),
        rules=None,
    )
    planner = PrimitivePlanner()

    # Act
    plan = planner.make_plan(ctx, PrimitiveGoal.REPRODUCE)

    # Assert
    assert len(plan) == 1, "Should return single MatingAction"
    assert isinstance(plan[0], MatingAction), "Action should be MatingAction"
    assert plan[0].partner_id == -1, "Partner ID should be -1 (deferred to ReproductionSystem)"


def test_goal_selection_with_balanced_needs():
    """Test goal selection when all needs are in moderate range"""
    # Arrange
    ctx = PrimitiveBrainContext(
        0,
        etype="animal",
        eid=1,
        hunger=0.5,  # Moderate hunger
        energy=0.5,  # Moderate energy
        is_pregnant=False,  # Not pregnant
        memory_data=MemoryData(),
        memory_engine=PerfectMemory(),
        rules=None,  # No specific world rules
    )
    selector = PrimitiveGoalSelector()

    # Act
    goal = selector.select_goal(ctx)

    # Assert
    assert goal in PrimitiveGoal.all(), "Should select a valid goal when needs are balanced"
