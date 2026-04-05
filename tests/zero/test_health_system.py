import math
from typing import Sequence, cast

from simz.ecs.component import Component
from simz.ecs.core import ECS
from zero.simulation.components import (
    EntitiesConfigComponent,
    FamilyComponent,
    HealthComponent,
    LifeExpectancyComponent,
    PregnancyComponent,
    WellbeingComponent,
    WellbeingConditionComponent,
)
from zero.simulation.entities import EntitiesFactory, EntityTypes
from zero.simulation.systems.health import HealthSystem


def create_animal_with_long_life_expectancy(name: str, life_expectancy: int = 1000) -> tuple[str, Sequence[Component]]:
    """Create an animal with a specified long life expectancy to avoid random deaths in tests."""
    entity_type, components = EntitiesFactory.create_animal(name)

    # Find and update the LifeExpectancyComponent
    for i, component in enumerate(components):
        if isinstance(component, LifeExpectancyComponent):
            cast(LifeExpectancyComponent, components[i]).value = life_expectancy

    return entity_type, components


def test_birth_ideal_conditions(ecs: ECS):
    """Test that an entity with hunger level 0.0 changes to hungry state."""
    # arrange
    hs = HealthSystem()
    hs.init_system(ecs)

    # prepare pregnant entity with long life expectancy to avoid random deaths
    eid = ecs.create_entity(*create_animal_with_long_life_expectancy("Animal_1"))
    mate_eid = ecs.create_entity(*create_animal_with_long_life_expectancy("Animal_2"))
    wellbeing = ecs.get_typed_component(eid, WellbeingComponent)
    wellbeing.pregnancy = PregnancyComponent(0, 1.0, mate=mate_eid)
    ecs.update_typed_component(eid, wellbeing)

    # act
    config = ecs.get_singleton_component(EntitiesConfigComponent)
    full_term = config[EntityTypes.ANIMAL][PregnancyComponent]["full_term"]

    for i in range(full_term):
        hs.update(i)

    # surface premature-death bug
    assert ecs.entity_exists(eid), "Pregnant mother died before term"

    hs.update(full_term)

    # assert
    wellbeing = ecs.get_typed_component(eid, WellbeingComponent)
    assert wellbeing.pregnancy is None, "Entity should not be pregnant"
    family = ecs.get_typed_component(eid, FamilyComponent)
    assert len(family.children) == 1, "Entity should have one child"
    child = ecs.entity_exists(family.children[0])
    assert child, "Child should exist"


def test_death_due_to_starvation(ecs: ECS):
    """Test that an entity dies due to starvation."""
    # arrange
    hs = HealthSystem()
    hs.init_system(ecs)

    # prepare pregnant entity
    eid = ecs.create_entity(*EntitiesFactory.create_animal("Animal_1"))
    wellbeing = ecs.get_typed_component(eid, WellbeingComponent)
    wellbeing.starving = WellbeingConditionComponent(0)

    # act
    # health_before = ecs.get_typed_component(eid, WellbeingComponent)
    current_health = ecs.get_typed_component(eid, HealthComponent).value
    starvation_penalty = ecs.get_singleton_component(EntitiesConfigComponent)[EntityTypes.ANIMAL][HealthComponent][
        "starvation_penalty"
    ]

    estimate_time_to_die = current_health / starvation_penalty
    for i in range(int(estimate_time_to_die)):
        hs.update(i)

    hs.update(int(estimate_time_to_die))  # last turn before death
    hs.update(int(estimate_time_to_die) + 1)  # death turn
    # assert
    assert ecs.entity_exists(eid) == False, "Entity should be dead"


def test_removal_of_temporary_effects(ecs: ECS):
    """Test that temporary effects are removed after a certain time."""
    # arrange
    hs = HealthSystem()
    hs.init_system(ecs)

    # prepare entity with temporary effects
    eid = ecs.create_entity(*EntitiesFactory.create_animal("Animal_1"))
    wellbeing = ecs.get_typed_component(eid, WellbeingComponent)
    wellbeing.well_fed = WellbeingConditionComponent(0)
    wellbeing.well_rested = WellbeingConditionComponent(0)
    ecs.update_typed_component(eid, wellbeing)

    wellfed_duration = ecs.get_singleton_component(EntitiesConfigComponent)[EntityTypes.ANIMAL][HealthComponent][
        "well_fed_effect_duration"
    ]
    wellrested_duration = ecs.get_singleton_component(EntitiesConfigComponent)[EntityTypes.ANIMAL][HealthComponent][
        "well_rested_effect_duration"
    ]
    max_duration = max(wellfed_duration, wellrested_duration)
    # act
    for i in range(max_duration):
        hs.update(i)

    hs.update(max_duration)  # last turn before removal
    # assert
    wellbeing = ecs.get_typed_component(eid, WellbeingComponent)
    assert wellbeing.starving is None, "Starving condition should be removed"
    assert wellbeing.hungry is None, "Hungry condition should be removed"


def test_health_penalties(ecs: ECS):
    """Test that health penalties are applied correctly."""
    # arrange
    hs = HealthSystem()
    hs.init_system(ecs)

    # prepare entity with penalties
    eid = ecs.create_entity(*EntitiesFactory.create_animal("Animal_1"))
    wellbeing = ecs.get_typed_component(eid, WellbeingComponent)
    wellbeing.starving = WellbeingConditionComponent(0)
    wellbeing.tired = WellbeingConditionComponent(0)
    wellbeing.hungry = WellbeingConditionComponent(0)
    ecs.update_typed_component(eid, wellbeing)

    # act
    hs.update(0)  # apply penalties

    # assert
    health = ecs.get_typed_component(eid, HealthComponent)
    starving_penalty = ecs.get_singleton_component(EntitiesConfigComponent)[EntityTypes.ANIMAL][HealthComponent][
        "starvation_penalty"
    ]
    tired_penalty = ecs.get_singleton_component(EntitiesConfigComponent)[EntityTypes.ANIMAL][HealthComponent][
        "tired_penalty"
    ]
    hungry_penalty = ecs.get_singleton_component(EntitiesConfigComponent)[EntityTypes.ANIMAL][HealthComponent][
        "hungry_penalty"
    ]

    expected_health = health.max - starving_penalty - tired_penalty - hungry_penalty

    assert math.isclose(
        health.value, expected_health, rel_tol=1e-9
    ), f"Expected health {expected_health}, but got {health}"
