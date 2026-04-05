from sim.ai.memory import MemoryData, MemoryFact, PerfectMemory
from zero.ai.actions import (
    EatAction,
    ExploreAction,
    PickUpAction,
    WalkToAction,
)
from zero.ai.context import PrimitiveBrainContext
from zero.ai.primitive import PrimitivePlanner


def test_plan_eat_with_owned_food():
    # Arrange
    ctx = PrimitiveBrainContext(
        simulation_time=0,
        eid=1,
        etype="animal",
        hunger=0.9,
        energy=0.5,
        is_pregnant=False,
        memory_data=MemoryData(),
        memory_engine=PerfectMemory(),
        rules=None,
    )
    ctx.memory_data.ltm = {"food1": MemoryFact(uid="food1", tag="food", t0=0, value={"id": "food1", "owned": True})}
    planner = PrimitivePlanner()

    # Act
    plan = planner.plan_eat(ctx)

    # Assert
    assert len(plan) == 1, "Plan should contain one action when food is owned."
    assert isinstance(plan[0], EatAction), "The action should be EatAction."
    assert plan[0].food_id == "food1", "The target food ID should match the known food ID."


def test_plan_eat_with_unowned_food():
    # Arrange
    ctx = PrimitiveBrainContext(
        simulation_time=0,
        eid=1,
        etype="animal",
        hunger=0.9,
        energy=0.5,
        is_pregnant=False,
        memory_data=MemoryData(),
        memory_engine=PerfectMemory(),
        rules=None,
    )
    ctx.memory_data.ltm = {
        "food1": MemoryFact(uid="food1", tag="food", t0=0, value={"id": "food1", "location": (10, 20), "owned": False})
    }
    planner = PrimitivePlanner()

    # Act
    plan = planner.plan_eat(ctx)

    # Assert
    assert len(plan) == 3, "Plan should contain three actions when food is unowned."
    assert isinstance(plan[0], WalkToAction), "The first action should be WalkToAction."
    assert isinstance(plan[1], PickUpAction), "The second action should be PickUpAction."
    assert isinstance(plan[2], EatAction), "The third action should be EatAction."
    assert plan[2].food_id == "food1", "The target food ID should match the known food ID."


def test_plan_eat_with_no_food():
    # Arrange
    ctx = PrimitiveBrainContext(
        simulation_time=0,
        eid=1,
        etype="animal",
        hunger=0.9,
        energy=0.5,
        is_pregnant=False,
        memory_data=MemoryData(),
        memory_engine=PerfectMemory(),
        rules=None,
    )
    planner = PrimitivePlanner()

    # Act
    plan = planner.plan_eat(ctx)

    # Assert
    assert len(plan) == 1, "Plan should contain one action when no food is known."
    assert isinstance(plan[0], ExploreAction), "The action should be ExploreAction."
