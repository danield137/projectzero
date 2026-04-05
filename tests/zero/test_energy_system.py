import math
from typing import Set

from sim.common.math import EPSILON
from sim.ecs.core import ECS
from zero.simulation.components import (
    ActivityComponent,
    EnergyComponent,
    SleepingActivity,
    WellbeingComponent,
    WellbeingConditionComponent,
)
from zero.simulation.entities import EntitiesFactory
from zero.simulation.systems.energy import EnergyLevel, EnergySystem

# Define energy levels for testing since they're not defined in the actual module


def test_energy_decrease_every_step(ecs: ECS):
    """Test that energy decreases with each system update."""
    # Arrange
    es = EnergySystem()
    es.init_system(ecs)
    eid = ecs.create_entity(*EntitiesFactory.create_animal("Animal_1"))
    energy = ecs.get_typed_component(eid, EnergyComponent)
    initial_energy = energy.value

    # Act
    es.update(1)

    # Assert
    energy = ecs.get_typed_component(eid, EnergyComponent)
    assert energy.value < initial_energy, "Energy level did not decrease as expected."


def test_energy_levels(ecs: ECS):
    """Test that energy level transitions through states correctly."""
    # Arrange
    es = EnergySystem()
    es.init_system(ecs)
    eid = ecs.create_entity(*EntitiesFactory.create_animal("Animal_1"))

    # Track energy level changes through simulation
    expected_levels = set(range(EnergyLevel.E0_EXHAUSTED, EnergyLevel.E9_ENERGETIC + 1))
    actual_levels: Set[int] = set()

    test = EnergyComponent(10 - EPSILON)
    print(f"Initial Energy Level: {test.value}, max: {test.max}, min: {test.min}")
    # Act - run simulation until we've seen all energy levels
    for turn in range(300):  # Limit to avoid infinite loop
        if len(actual_levels) == len(expected_levels):
            break

        energy = ecs.get_typed_component(eid, EnergyComponent)
        print(f"Turn {turn}: Energy Level: {energy.value}")
        energy_level = math.floor(energy.value)
        actual_levels.add(energy_level)
        print(f"Turn {turn}: Energy Level: {energy_level}")
        es.update(turn)

    # Assert
    assert (
        actual_levels == expected_levels
    ), f"Not all energy levels observed. Missing: {expected_levels - actual_levels}"


def test_sleeping_to_restore_energy(ecs: ECS):
    """Test that sleeping restores energy."""
    # Arrange
    es = EnergySystem()
    es.init_system(ecs)
    eid = ecs.create_entity(*EntitiesFactory.create_animal("Animal_1"))

    # Reduce energy first
    energy = ecs.get_typed_component(eid, EnergyComponent)
    energy.value = 3.0  # Set to a low value
    ecs.update_typed_component(eid, energy)

    # Start sleeping
    activity = ecs.get_typed_component(eid, ActivityComponent)
    activity.activity = SleepingActivity(since=0)
    ecs.update_typed_component(eid, activity)

    energy_before = ecs.get_typed_component(eid, EnergyComponent).value

    # Act
    es.update(1)

    # Assert
    energy_after = ecs.get_typed_component(eid, EnergyComponent).value
    assert energy_after > energy_before, "Energy should increase while sleeping"


def test_tired_condition(ecs: ECS):
    """Test that low energy creates tired condition."""
    # Arrange
    es = EnergySystem()
    es.init_system(ecs)
    eid = ecs.create_entity(*EntitiesFactory.create_animal("Animal_1"))

    # Set energy to just above tired threshold
    energy = ecs.get_typed_component(eid, EnergyComponent)
    energy.value = EnergyLevel.E5_NORMAL
    ecs.update_typed_component(eid, energy)

    # Act - reduce energy to trigger tired condition
    es.update(0)

    # Assert - check for tired condition
    wellbeing = ecs.get_typed_component(eid, WellbeingComponent)
    assert wellbeing.tired is None, "Should not be tired yet"

    # Now set energy below tired threshold
    energy = ecs.get_typed_component(eid, EnergyComponent)
    energy.value = EnergyLevel.E2_TIRED
    ecs.update_typed_component(eid, energy)

    # Update system again
    es.update(1)  # this should lower the energy level enough to trigger tired condition

    # Check for tired condition
    wellbeing = ecs.get_typed_component(eid, WellbeingComponent)
    assert wellbeing.tired is not None, "Should be tired now"
    assert isinstance(wellbeing.tired, WellbeingConditionComponent), "Tired condition should be added"
