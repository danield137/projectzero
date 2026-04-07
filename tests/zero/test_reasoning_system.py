from typing import Any, Dict, cast

from zero.ai.primitive import PrimitiveGoal
from tigen.ecs.core import ECS
from zero.simulation.components import (
    BrainComponent,
    DietComponent,
    EnergyComponent,
    HungerComponent,
    MemoryComponent,
    PregnancyComponent,
    WellbeingComponent,
)
from zero.simulation.entities import EntitiesFactory
from zero.simulation.systems.reasoning import ReasoningSystem


def test_goal_selection_reproduce_conditions(ecs: ECS):
    """Test that reproduction goal selection respects all conditions."""
    # Arrange
    rs = ReasoningSystem()
    rs.init_system(ecs)

    # Create entity
    eid = ecs.create_entity(*EntitiesFactory.create_animal("Animal_1"))

    def set_conditions(hunger_val: float, energy_val: float, is_pregnant: bool) -> PrimitiveGoal:
        hunger = ecs.get_typed_component(eid, HungerComponent)
        energy = ecs.get_typed_component(eid, EnergyComponent)
        wellbeing = ecs.get_typed_component(eid, WellbeingComponent)

        # Set values
        hunger.value = hunger_val  # Normalized in ReasoningAspect.bind
        energy.value = energy_val  # Normalized in ReasoningAspect.bind
        wellbeing.pregnancy = PregnancyComponent(since=0, offsprings=1, mate=1) if is_pregnant else None

        # Update components
        ecs.update_typed_component(eid, hunger)
        ecs.update_typed_component(eid, energy)
        ecs.update_typed_component(eid, wellbeing)

        # Process entity
        rs.update(0)
        brain = ecs.get_typed_component(eid, BrainComponent)
        return brain.current_goal

    # Test ideal conditions
    assert set_conditions(3.0, 9.0, False) == PrimitiveGoal.REPRODUCE, "Should reproduce when conditions ideal"

    # Test when hungry
    assert set_conditions(9.0, 9.0, False) != PrimitiveGoal.REPRODUCE, "Should not reproduce when hungry"

    # Test when low energy
    assert set_conditions(3.0, 1.0, False) != PrimitiveGoal.REPRODUCE, "Should not reproduce when tired"

    # Test when pregnant
    assert set_conditions(3.0, 9.0, True) != PrimitiveGoal.REPRODUCE, "Should not reproduce when pregnant"


def test_cannibalism_blocked_by_default(ecs: ECS):
    """Test that same-species cannibalism is blocked when allow_cannibalism=False."""
    # arrange
    rs = ReasoningSystem()
    rs.init_system(ecs)

    # Create two humans
    human1_id = ecs.create_entity(*EntitiesFactory.create_human("Human1"))
    human2_id = ecs.create_entity(*EntitiesFactory.create_human("Human2"))

    # Verify cannibalism is disabled by default
    human1_diet = ecs.get_typed_component(human1_id, DietComponent)
    assert not human1_diet.allow_cannibalism, "Cannibalism should be disabled by default"

    # Set human1 to be very hungry (should trigger food search)
    hunger = ecs.get_typed_component(human1_id, HungerComponent)
    hunger.value = 8.5  # Very hungry
    ecs.update_typed_component(human1_id, hunger)

    # Run reasoning system to populate memory with valid food choices
    rs.update(0)

    # Get human1's memory to verify human2 is not added as food
    memory = ecs.get_typed_component(human1_id, MemoryComponent)

    # Check that human2 is not in memory as food due to cannibalism restriction
    human2_in_memory = False
    for fact in memory.data.all():
        if fact.tag == "food" and cast(Dict[str, Any], fact.value).get("id") == human2_id:
            human2_in_memory = True
            break

    assert not human2_in_memory, "Human2 should not be added to memory as food due to cannibalism restriction"


def test_cannibalism_allowed_when_enabled(ecs: ECS):
    """Test that same-species cannibalism works when allow_cannibalism=True."""
    # arrange
    rs = ReasoningSystem()
    rs.init_system(ecs)

    # Create two humans
    human1_id = ecs.create_entity(*EntitiesFactory.create_human("Human1"))
    human2_id = ecs.create_entity(*EntitiesFactory.create_human("Human2"))

    # Enable cannibalism for human1
    human1_diet = ecs.get_typed_component(human1_id, DietComponent)
    human1_diet.allow_cannibalism = True
    ecs.update_typed_component(human1_id, human1_diet)

    # Set human1 to be very hungry (should trigger food search)
    hunger = ecs.get_typed_component(human1_id, HungerComponent)
    hunger.value = 8.5  # Very hungry
    ecs.update_typed_component(human1_id, hunger)

    # Run reasoning system to populate memory with valid food choices
    rs.update(0)

    # Get human1's memory to verify human2 is added as food when cannibalism is allowed
    memory = ecs.get_typed_component(human1_id, MemoryComponent)

    # Check that human2 is in memory as food when cannibalism is allowed
    human2_in_memory = False
    for fact in memory.data.all():
        if fact.tag == "food" and cast(Dict[str, Any], fact.value).get("id") == human2_id:
            human2_in_memory = True
            break

    assert human2_in_memory, "Human2 should be added to memory as food when cannibalism is allowed"


def test_diet_restrictions_herbivore_animals(ecs: ECS):
    """Test that herbivore animals cannot see other animals as food."""
    # arrange
    rs = ReasoningSystem()
    rs.init_system(ecs)

    # Create herbivore animal and another animal
    animal1_id = ecs.create_entity(*EntitiesFactory.create_animal("Animal1"))
    animal2_id = ecs.create_entity(*EntitiesFactory.create_animal("Animal2"))

    # Verify animal1 is herbivore
    animal1_diet = ecs.get_typed_component(animal1_id, DietComponent)
    assert animal1_diet.diet_type.value == "Herbivore", "Animal should be herbivore by default"

    # Set animal1 to be very hungry (should trigger food search)
    hunger = ecs.get_typed_component(animal1_id, HungerComponent)
    hunger.value = 8.5  # Very hungry
    ecs.update_typed_component(animal1_id, hunger)

    # Run reasoning system to populate memory with valid food choices
    rs.update(0)

    # Get animal1's memory to verify animal2 is not added as food (diet restriction)
    memory = ecs.get_typed_component(animal1_id, MemoryComponent)

    # Check that animal2 is not in memory as food due to diet restriction
    animal2_in_memory = False
    for fact in memory.data.all():
        if fact.tag == "food" and cast(Dict[str, Any], fact.value).get("id") == animal2_id:
            animal2_in_memory = True
            break

    assert not animal2_in_memory, "Animal2 should not be added to memory as food for herbivore Animal1"


def test_omnivore_humans_can_eat_both_plants_and_animals(ecs: ECS):
    """Test that omnivore humans can see both plants and animals as food."""
    # arrange
    rs = ReasoningSystem()
    rs.init_system(ecs)

    # Create human, plant, and animal
    human_id = ecs.create_entity(*EntitiesFactory.create_human("Human"))
    plant_id = ecs.create_entity(*EntitiesFactory.create_plant("Plant"))
    animal_id = ecs.create_entity(*EntitiesFactory.create_animal("Animal"))

    # Verify human is omnivore
    human_diet = ecs.get_typed_component(human_id, DietComponent)
    assert human_diet.diet_type.value == "Omnivore", "Human should be omnivore by default"

    # Set human to be very hungry (should trigger food search)
    hunger = ecs.get_typed_component(human_id, HungerComponent)
    hunger.value = 8.5  # Very hungry
    ecs.update_typed_component(human_id, hunger)

    # Run reasoning system to populate memory with valid food choices
    rs.update(0)

    # Get human's memory to verify both plant and animal are added as food
    memory = ecs.get_typed_component(human_id, MemoryComponent)

    plant_in_memory = False
    animal_in_memory = False
    for fact in memory.data.all():
        if fact.tag == "food":
            fact_value = cast(Dict[str, Any], fact.value)
            if fact_value.get("id") == plant_id:
                plant_in_memory = True
            elif fact_value.get("id") == animal_id:
                animal_in_memory = True

    assert plant_in_memory, "Plant should be added to memory as food for omnivore human"
    assert animal_in_memory, "Animal should be added to memory as food for omnivore human"
