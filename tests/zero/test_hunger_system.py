import math

from simz.ecs.core import ECS
from zero.simulation.components import (
    ActivityComponent,
    CauseOfDeath,
    EatingActivity,
    HungerComponent,
    StatsComponent,
    WellbeingComponent,
    WellbeingConditionComponent,
)
from zero.simulation.entities import EntitiesFactory
from zero.simulation.systems.hunger import HungerAspect, HungerLevel, HungerSystem


def test_hunger_increase_every_step(ecs: ECS) -> None:
    """Test that an entity with hunger level 0.0 does not change its state."""
    # arrange
    hs = HungerSystem()
    hs.init_system(ecs)
    eid = ecs.create_entity(*EntitiesFactory.create_animal("Animal_1"))
    hunger = ecs.get_typed_component(eid, HungerComponent)
    initial_hunger = hunger.value
    # act
    hs.update(1)
    # assert
    hunger = ecs.get_typed_component(eid, HungerComponent)
    assert hunger.value > initial_hunger, "Hunger level did not increase as expected."


def test_hunger_stages(ecs: ECS) -> None:
    """Test that an entity with hunger level 0.0 changes to hungry state."""
    # arrange
    hs = HungerSystem()
    hs.init_system(ecs)
    expected = set(range(HungerLevel.H0_STUFFED, HungerLevel.H9_STARVING))
    actual: set[int] = set()
    turn = 0
    eid = ecs.create_entity(*EntitiesFactory.create_animal("Animal_1"))
    while turn < 200 and len(actual) < len(expected):
        ha = HungerAspect.bind(eid, ecs)
        # mark visited
        rv = int(math.floor(ha.hunger.value))

        print(f"Turn {turn}: {ha.hunger.value}, {rv}")
        actual.add(rv)
        hs.update(turn)
        turn += 1
    assert expected == actual, "Hunger levels did not progress as expected."


def test_eating_to_reduce_hunger(ecs: ECS) -> None:
    hs = HungerSystem()
    hs.init_system(ecs)
    expected = set(range(HungerLevel.H0_STUFFED, HungerLevel.H9_STARVING))
    actual: set[int] = set()
    turn = 0
    eid = ecs.create_entity(*EntitiesFactory.create_animal("Animal_1"))
    # run for a while to be hungry
    while turn < 200 and len(actual) < len(expected):
        hs.update(turn)
        turn += 1

    hunger_prior = ecs.get_typed_component(eid, HungerComponent).value
    # create actual food to eat
    food_id = ecs.create_entity(*EntitiesFactory.create_plant("TestFood"))
    # now eat
    activity = ecs.get_typed_component(eid, ActivityComponent)
    activity.activity = EatingActivity(since=turn, food=food_id)
    # once again, this time we expect hunger to decrease
    hs.update(turn)
    hunger_post = ecs.get_typed_component(eid, HungerComponent).value
    # assert
    assert hunger_post < hunger_prior, "Hunger level did not decrease as expected."


def test_eating_nonexistent_food_no_effect(ecs: ECS) -> None:
    """Test that eating nonexistent food does not reduce hunger."""
    # arrange
    hs = HungerSystem()
    hs.init_system(ecs)
    eid = ecs.create_entity(*EntitiesFactory.create_animal("Animal_1"))

    # Set initial hunger
    hunger = ecs.get_typed_component(eid, HungerComponent)
    initial_hunger = 7.0  # Fairly hungry
    hunger.value = initial_hunger
    ecs.update_typed_component(eid, hunger)

    # Set eating activity with nonexistent food entity
    activity = ecs.get_typed_component(eid, ActivityComponent)
    nonexistent_food_id = 99999  # ID that definitely doesn't exist
    activity.activity = EatingActivity(since=0, food=nonexistent_food_id)
    ecs.update_typed_component(eid, activity)

    # act
    hs.update(0)

    # assert
    hunger = ecs.get_typed_component(eid, HungerComponent)
    assert hunger.value >= initial_hunger, "Hunger should not decrease when eating nonexistent food"


def test_eating_to_remove_starving(ecs: ECS) -> None:
    hs = HungerSystem()
    hs.init_system(ecs)
    turn = 0
    eid = ecs.create_entity(*EntitiesFactory.create_animal())

    # make entity starving
    hunger = ecs.get_typed_component(eid, HungerComponent)
    hunger.value = HungerLevel.H9_STARVING
    ecs.update_typed_component(eid, hunger)
    wellbeing = ecs.get_typed_component(eid, WellbeingComponent)
    wellbeing.starving = WellbeingConditionComponent(turn)
    ecs.update_typed_component(eid, wellbeing)

    # mimic a few turn of starvation
    hs.update(turn)
    turn += 1

    # create actual food to eat and mark entity as eating
    food_id = ecs.create_entity(*EntitiesFactory.create_plant("TestFood"))
    activity = ecs.get_typed_component(eid, ActivityComponent)
    activity.activity = EatingActivity(since=turn, food=food_id)

    # ACT
    # wait until hunger level drops enough to remove starving condition
    while turn < 200:
        ha = HungerAspect.bind(eid, ecs)
        if HungerLevel.H6_HUNGRY.value_under(ha.hunger.value):
            break
        # mimic a few turns of eating
        print(f"Turn {turn}: {ha.hunger.value}, hunger {ha.hunger.value}")
        hs.update(turn)
        turn += 1

    # ASSERT - we expect the starving condition to be removed
    wellbeing = ecs.get_typed_component(eid, WellbeingComponent)
    assert wellbeing.starving is None, "Starving condition was not removed after eating."


def test_food_chain_nutrition_differences(ecs: ECS) -> None:
    """Test that animals eating plants vs animals eating meat have different nutrition effects."""
    # arrange
    hs = HungerSystem()
    hs.init_system(ecs)

    # Create test entities
    animal_id = ecs.create_entity(*EntitiesFactory.create_animal("TestAnimal"))
    plant_id = ecs.create_entity(*EntitiesFactory.create_plant("TestPlant"))  # nutrition = 2.0
    meat_id = ecs.create_entity(*EntitiesFactory.create_animal("TestMeat"))  # nutrition = 4.0

    initial_hunger = 8.0  # Very hungry

    # Test 1: Animal eats plant (lower nutrition)
    hunger = ecs.get_typed_component(animal_id, HungerComponent)
    hunger.value = initial_hunger
    ecs.update_typed_component(animal_id, hunger)

    activity = ecs.get_typed_component(animal_id, ActivityComponent)
    activity.activity = EatingActivity(since=0, food=plant_id)
    ecs.update_typed_component(animal_id, activity)

    hs.update(0)
    hunger_after_plant = ecs.get_typed_component(animal_id, HungerComponent).value
    plant_reduction = initial_hunger - hunger_after_plant

    # Test 2: Reset and eat meat (higher nutrition)
    hunger = ecs.get_typed_component(animal_id, HungerComponent)
    hunger.value = initial_hunger  # Reset to same starting point
    ecs.update_typed_component(animal_id, hunger)

    activity = ecs.get_typed_component(animal_id, ActivityComponent)
    activity.activity = EatingActivity(since=0, food=meat_id)
    ecs.update_typed_component(animal_id, activity)

    hs.update(0)
    hunger_after_meat = ecs.get_typed_component(animal_id, HungerComponent).value
    meat_reduction = initial_hunger - hunger_after_meat

    # assert - meat should provide more hunger reduction than plants
    assert (
        meat_reduction > plant_reduction
    ), f"Meat (reduction: {meat_reduction:.3f}) should reduce hunger more than plants (reduction: {plant_reduction:.3f})"
    assert plant_reduction > 0, "Plants should still reduce hunger"
    assert meat_reduction > 0, "Meat should reduce hunger"
    print(f"Plant reduction: {plant_reduction:.3f}, Meat reduction: {meat_reduction:.3f}")


def test_human_omnivore_food_chain(ecs: ECS) -> None:
    """Test that humans can eat both plants and animals."""
    # arrange
    hs = HungerSystem()
    hs.init_system(ecs)

    # Create test entities
    human_id = ecs.create_entity(*EntitiesFactory.create_human("TestHuman"))
    plant_id = ecs.create_entity(*EntitiesFactory.create_plant("TestPlant"))
    animal_id = ecs.create_entity(*EntitiesFactory.create_animal("TestAnimal"))

    initial_hunger = 7.0

    # Test 1: Human eats plant
    hunger = ecs.get_typed_component(human_id, HungerComponent)
    hunger.value = initial_hunger
    ecs.update_typed_component(human_id, hunger)

    activity = ecs.get_typed_component(human_id, ActivityComponent)
    activity.activity = EatingActivity(since=0, food=plant_id)
    ecs.update_typed_component(human_id, activity)

    hs.update(0)
    hunger_after_plant = ecs.get_typed_component(human_id, HungerComponent).value
    plant_reduction = initial_hunger - hunger_after_plant

    # Test 2: Reset and human eats animal
    hunger = ecs.get_typed_component(human_id, HungerComponent)
    hunger.value = initial_hunger
    ecs.update_typed_component(human_id, hunger)

    activity = ecs.get_typed_component(human_id, ActivityComponent)
    activity.activity = EatingActivity(since=0, food=animal_id)
    ecs.update_typed_component(human_id, activity)

    hs.update(0)
    hunger_after_animal = ecs.get_typed_component(human_id, HungerComponent).value
    animal_reduction = initial_hunger - hunger_after_animal

    # assert - both should reduce hunger, with animal being more nutritious
    assert plant_reduction > 0, "Humans should be able to eat plants"
    assert animal_reduction > 0, "Humans should be able to eat animals"
    assert (
        animal_reduction > plant_reduction
    ), f"Animal meat (reduction: {animal_reduction:.3f}) should be more nutritious than plants (reduction: {plant_reduction:.3f})"


def test_prey_killing_when_eaten(ecs: ECS) -> None:
    """Test that perishable prey is killed when eaten and death is recorded."""
    # arrange
    hs = HungerSystem()
    hs.init_system(ecs)

    # Create predator (human) and prey (animal)
    human_id = ecs.create_entity(*EntitiesFactory.create_human("TestHuman"))
    animal_id = ecs.create_entity(*EntitiesFactory.create_animal("TestAnimal"))

    # Get initial death count
    stats = ecs.get_singleton_component(StatsComponent)
    from zero.simulation.functional import stat_ops

    initial_deaths = stat_ops.deaths_total(stats, "Animal")

    # Set human to be eating the animal
    hunger = ecs.get_typed_component(human_id, HungerComponent)
    hunger.value = 8.0  # Very hungry
    ecs.update_typed_component(human_id, hunger)

    activity = ecs.get_typed_component(human_id, ActivityComponent)
    activity.activity = EatingActivity(since=0, food=animal_id)
    ecs.update_typed_component(human_id, activity)

    # Verify animal exists before eating
    assert ecs.entity_exists(animal_id), "Animal should exist before being eaten"

    # act
    hs.update(0)

    # assert
    # Verify animal was removed (killed)
    assert not ecs.entity_exists(animal_id), "Animal should be removed when eaten"

    # Verify death was recorded with correct cause
    updated_stats = ecs.get_singleton_component(StatsComponent)
    final_deaths = stat_ops.deaths_total(updated_stats, "Animal")
    assert final_deaths == initial_deaths + 1, "Death should be recorded for Animal species"
    assert updated_stats.deaths["Animal"][CauseOfDeath.EATEN.value] == 1, "Death should be recorded as EATEN"

    # Verify human's hunger was reduced
    updated_hunger = ecs.get_typed_component(human_id, HungerComponent)
    assert updated_hunger.value < 8.0, "Human hunger should be reduced after eating"
