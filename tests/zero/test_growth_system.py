from simz.ecs.core import ECS
from zero.simulation.components import GrowthComponent
from zero.simulation.entities import EntitiesFactory
from zero.simulation.systems.growth import GrowthSystem


def test_growth_rate(ecs: ECS) -> None:
    """Test that entities grow at the expected rate."""
    # Arrange
    gs = GrowthSystem()
    gs.init_system(ecs)

    # Create a plant entity (plants use growth, not animals)
    eid = ecs.create_entity(*EntitiesFactory.create_plant("Test_Plant"))

    # Get the initial size and growth rate
    growth = ecs.get_typed_component(eid, GrowthComponent)
    initial_size = growth.size
    growth_rate = growth.growth_rate

    # Act
    gs.update(1)

    # Assert
    growth_after = ecs.get_typed_component(eid, GrowthComponent)
    expected_size = initial_size + growth_rate
    assert growth_after.size == expected_size, f"Expected size {expected_size}, got {growth_after.size}"


def test_plant_growth(ecs: ECS) -> None:
    """Test that plants grow according to their specific rate."""
    # Arrange
    gs = GrowthSystem()
    gs.init_system(ecs)

    # Create a plant entity
    eid = ecs.create_entity(*EntitiesFactory.create_plant("Test_Plant"))

    # Get the initial size and growth rate
    growth = ecs.get_typed_component(eid, GrowthComponent)
    initial_size = growth.size
    growth_rate = growth.growth_rate

    # Act
    gs.update(1)

    # Assert
    growth_after = ecs.get_typed_component(eid, GrowthComponent)
    expected_size = initial_size + growth_rate
    assert growth_after.size == expected_size, f"Expected size {expected_size}, got {growth_after.size}"


def test_multiple_growth_cycles(ecs: ECS) -> None:
    """Test that growth accumulates value_over multiple updates."""
    # Arrange
    gs = GrowthSystem()
    gs.init_system(ecs)

    # Create a plant entity
    eid = ecs.create_entity(*EntitiesFactory.create_plant("Test_Plant"))

    # Get initial values
    growth = ecs.get_typed_component(eid, GrowthComponent)
    initial_size = growth.size
    growth_rate = growth.growth_rate

    # Act - run for multiple cycles
    num_cycles = 5
    for i in range(num_cycles):
        gs.update(i)

    # Assert
    growth_after = ecs.get_typed_component(eid, GrowthComponent)
    expected_size = initial_size + (growth_rate * num_cycles)
    assert growth_after.size == expected_size, f"Expected size {expected_size}, got {growth_after.size}"
