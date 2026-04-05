from __future__ import annotations

import random
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import cast

from sim.common import logging
from sim.common.math import sigmoid_probability
from sim.ecs.core import ECS
from sim.ecs.system import System
from zero.simulation.components import (
    CauseOfDeath,
    EntitiesConfigComponent,
    HealthComponent,
    LifeExpectancyComponent,
    PregnancyComponent,
    StatsComponent,
    WellbeingComponent,
    WellbeingConditionComponent,
)
from zero.simulation.entities import (
    BirthdayComponent,
    EntitiesFactory,
    EntityTypes,
    FamilyComponent,
)
from zero.simulation.functional import stat_ops
from zero.simulation.functional.stat_ops import EntityType

logger = logging.get_logger()


@dataclass(slots=True)
class HealthAspect:
    entity: int
    etype: str
    health: HealthComponent

    wellbeing: WellbeingComponent
    life_expectancy: LifeExpectancyComponent
    birthday: BirthdayComponent
    family: FamilyComponent
    config: EntitiesConfigComponent
    change: bool = field(default=False, init=False)

    @staticmethod
    def bind(ecs: ECS, entity: int) -> HealthAspect:
        etype = ecs.entities_by_id[entity]
        health = ecs.get_typed_component(entity, HealthComponent)
        wellbeing = ecs.get_typed_component(entity, WellbeingComponent)
        life_expectancy = ecs.get_typed_component(entity, LifeExpectancyComponent)
        birthday = ecs.get_typed_component(entity, BirthdayComponent)
        family = ecs.get_typed_component(entity, FamilyComponent)
        config = ecs.get_singleton_component(EntitiesConfigComponent)
        return HealthAspect(entity, etype, health, wellbeing, life_expectancy, birthday, family, config)

    def is_well_fed(self) -> bool:
        return self.wellbeing.well_fed is not None

    def is_well_rested(self) -> bool:
        return self.wellbeing.well_rested is not None

    def is_pregnant(self) -> bool:
        return self.wellbeing.pregnancy is not None

    def is_due(self, simulation_time: int) -> bool:
        assert self.wellbeing.pregnancy is not None, "Entity is not pregnant"
        duration = simulation_time - self.wellbeing.pregnancy.since
        return duration >= self.config[self.etype][PregnancyComponent]["full_term"]

    def regain_health(self):
        self.health.set_clamped_value(
            self.health.value + self.config[self.etype][HealthComponent]["regen_rate"],
        )

    def give_birth(self, child_creator: Callable[[FamilyComponent, str], int]) -> int:
        assert self.wellbeing.pregnancy is not None, "Entity is not pregnant"
        offsprings = self.wellbeing.pregnancy.offsprings
        mate = self.wellbeing.pregnancy.mate
        newborn: list[int] = []
        for i in range(int(offsprings)):
            baby_family = FamilyComponent.default((self.entity, mate))
            baby_name = f"Child_{i}[mother: {self.entity}, father:{mate}]"
            child_id = child_creator(baby_family, baby_name)
            newborn.append(child_id)

        self.family.children = (self.family.children or []) + newborn
        self.wellbeing.pregnancy = None  # reset pregnancy
        return int(offsprings)

    def has_negative_conditions(self) -> bool:
        return (
            self.wellbeing.starving is not None or self.wellbeing.hungry is not None or self.wellbeing.tired is not None
        )

    def has_positive_conditions(self) -> bool:
        return self.wellbeing.well_fed is not None or self.wellbeing.well_rested is not None

    def apply_benefits(self, simulation_time: int) -> bool:
        changed = False
        if self.wellbeing.well_fed is not None and self.wellbeing.well_rested is not None:
            self.regain_health()
            changed = True
        if self.wellbeing.well_rested is not None:
            lasted = simulation_time - self.wellbeing.well_rested.since
            if lasted > self.config[self.etype][HealthComponent]["well_rested_effect_duration"]:
                self.wellbeing.well_rested = None
                changed = True
        if self.wellbeing.well_fed is not None:
            lasted = simulation_time - self.wellbeing.well_fed.since
            if lasted > self.config[self.etype][HealthComponent]["well_fed_effect_duration"]:
                self.wellbeing.well_fed = None
                changed = True

        return changed

    def apply_penalties(self):
        starving_penalty = self.config[self.etype][HealthComponent]["starvation_penalty"]
        tired_penalty = self.config[self.etype][HealthComponent]["tired_penalty"]
        hungry_penalty = self.config[self.etype][HealthComponent]["hungry_penalty"]

        changed = False
        if self.wellbeing.starving is not None:
            self.health.set_clamped_value(self.health.value - starving_penalty)
            self.wellbeing.starving = WellbeingConditionComponent(since=self.wellbeing.starving.since)
            changed = True

        if self.wellbeing.tired is not None:
            self.health.set_clamped_value(self.health.value - tired_penalty)
            self.wellbeing.tired = WellbeingConditionComponent(since=self.wellbeing.tired.since)
            changed = True

        if self.wellbeing.hungry is not None:
            self.health.set_clamped_value(self.health.value - hungry_penalty)
            self.wellbeing.hungry = WellbeingConditionComponent(since=self.wellbeing.hungry.since)
            changed = True

        return changed


class HealthSystem(System):
    def all_living_entities(self) -> Iterator[int]:
        yield from self.ecs.get_entities_with_typed_component(LifeExpectancyComponent)

    def handle_death(self, ha: HealthAspect, simulation_time: int) -> tuple[bool, str | None]:
        if ha.health.value == 0:
            self.ecs.remove_entity(ha.entity)
            return True, CauseOfDeath.LOW_HEALTH.value

        age = simulation_time - ha.birthday.value
        life_expectancy = ha.life_expectancy.value

        # Avoid old-age deaths for young entities (less than 50% of life expectancy)
        if age < life_expectancy * 0.5:
            return False, None

        death_probability = sigmoid_probability(x=age, midpoint=life_expectancy, growth_rate=0.1)

        if random.random() < death_probability:
            self.ecs.remove_entity(ha.entity)
            return True, CauseOfDeath.OLD_AGE.value
        return False, None

    def handle_birth(self, ha: HealthAspect, simulation_time: int) -> int:
        mate = cast(PregnancyComponent, ha.wellbeing.pregnancy).mate
        born = ha.give_birth(lambda family, name: create_child(self.ecs, ha.etype, family, name, simulation_time))
        if born > 0:
            self.ecs.update_typed_component(ha.entity, ha.family)
            if mate and self.ecs.entity_exists(mate):
                mates_family = self.ecs.get_typed_component(mate, FamilyComponent)
                mates_family.children = ha.family.children
                self.ecs.update_typed_component(mate, mates_family)
        return born

    def update(self, simulation_time: int):
        stats = self.ecs.get_singleton_component(StatsComponent)
        # todo: we need to replace this with a managed memory data structure
        for entity in self.all_living_entities():
            stat_ops.set_living_count(stats, stats.living + 1)
            ha = HealthAspect.bind(self.ecs, entity)

            died, cause = self.handle_death(ha, simulation_time)
            if died and cause:
                entity_type = cast(EntityType, ha.etype)
                stat_ops.record_death(stats, entity_type, cause)
                continue  # Entity died; skip further processing.

            # Count this living entity in population stats
            entity_type = cast(EntityType, self.ecs.entities_by_id[entity])
            stat_ops.inc_population(stats, entity_type)

            changed = False
            if ha.has_positive_conditions():
                changed |= ha.apply_benefits(simulation_time)

            if ha.has_negative_conditions():
                changed |= ha.apply_penalties()

            if ha.is_pregnant() and ha.is_due(simulation_time):
                births = self.handle_birth(ha, simulation_time)
                for _ in range(births):
                    stat_ops.inc_births(stats, entity_type)
                changed = True

            # could be better tuned to only update if the health value changed
            if changed:
                self.ecs.update_typed_component(entity, ha.wellbeing)
                self.ecs.update_typed_component(entity, ha.health)

        self.ecs.update_typed_singleton_component(stats)


# TODO: Not sure where this needs to be.
# This used to be in the LifeSystem (what is now the HealthSystem) and it made sense.
# HealthSystem was made so that it makes more sense to handle both health related conditions, and birth/death.
# It could be it would make sense to split those two systems again, but for now, let's keep it simple.
def create_child(ecs: ECS, etype: str, baby_family: FamilyComponent, name: str, simulation_time: int) -> int:
    if etype == EntityTypes.HUMAN:
        child_type, child_comp = EntitiesFactory.create_human(name, family=baby_family, birthday=simulation_time)
    elif etype == EntityTypes.ANIMAL:
        child_type, child_comp = EntitiesFactory.create_animal(name, family=baby_family, birthday=simulation_time)
    else:
        raise ValueError(f"Unknown entity type: {etype}")
    return ecs.create_entity(child_type, child_comp)
