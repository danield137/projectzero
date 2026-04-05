from __future__ import annotations

import math
from collections.abc import Iterator
from dataclasses import dataclass
from typing import ClassVar, cast

from simz.ai.memory import Memory
from simz.common import logging
from simz.common.enum import MonotonicEnum
from simz.config import get_global_config
from simz.ecs.core import ECS
from simz.ecs.system import System
from zero.ai.brains import get_memory_engine
from zero.simulation.components import (
    ActivityComponent,
    BrainComponent,
    CauseOfDeath,
    EatingActivity,
    EdibleComponent,
    EntitiesConfigComponent,
    GrowthComponent,
    HungerComponent,
    MemoryComponent,
    StatsComponent,
    WellbeingComponent,
    WellbeingConditionComponent,
)
from zero.simulation.entities import EntityTypes
from zero.simulation.functional import stat_ops
from zero.simulation.functional.stat_ops import EntityType

logger = logging.get_logger()


class HungerLevel(MonotonicEnum):
    H0_STUFFED = 0  # Recently ate; stomach painfully full
    H1_VERY_FULL = 1  # Completely satiated; not thinking about food
    H2_FULL = 2  # Comfortable and content
    H3_SATISFIED = 3  # Not hungry, but could snack
    H4_NEUTRAL = 4  # Slight emptiness, food becomes noticeable
    H5_PECKISH = 5  # Slightly hungry, thinking about next meal
    H6_HUNGRY = 6  # Definitely hungry
    H7_VERY_HUNGRY = 7  # Irritable, stomach growling
    H8_RAVENOUS = 8  # Hunger dominates thoughts
    H9_STARVING = 9  # Desperate, health at risk


class HungerMath:
    gain_rate_weight: ClassVar[float] = 1.0
    loss_rate_weight: ClassVar[float] = 1.0

    @classmethod
    def gain_rate(cls, hunger: float) -> float:
        inv = 1.0 / cls.gain_rate_weight
        return cls.gain_rate_weight * (0.05 * inv + 0.15 * inv / (1 + math.exp(-1.2 * (hunger - 7))))

    @classmethod
    def loss_rate(cls, hunger: float) -> float:
        inv = 1.0 / cls.loss_rate_weight
        return cls.loss_rate_weight * (-0.3 * inv / (1 + math.exp(-0.9 * (hunger - 5))))


@dataclass(slots=True)
class HungerAspect:
    entity: int
    entity_type: str
    hunger: HungerComponent
    wellbeing: WellbeingComponent
    config: EntitiesConfigComponent
    mem: MemoryComponent
    brain: BrainComponent
    memory_engine: Memory

    # TODO: this is a performance bottleneck. creating a new object every time is expensive.
    # Some possible solutions:
    # 1. Use a pool of HungerAspect objects and reuse them. Removes memory allocation overhead, but still needs assignment.
    # 2. Use a static functions instead of using an instance method. This would be less readable, but more performant.
    # 3. Use lower-level constructs like rust's structs, and reference components directly.
    #    This struct would be optimized away during compilation, thus zero overhead.
    @staticmethod
    def bind(eid: int, ecs: ECS):
        hunger = ecs.get_typed_component(eid, HungerComponent)
        wellbeing = ecs.get_typed_component(eid, WellbeingComponent)
        config = ecs.get_singleton_component(EntitiesConfigComponent)
        mem = ecs.get_typed_component(eid, MemoryComponent)
        brain = ecs.get_typed_component(eid, BrainComponent)
        memory_engine = get_memory_engine(brain.brain_type)
        entity_type = ecs.entities_by_id[eid]
        HungerMath.loss_rate_weight = config[entity_type][HungerComponent]["loss_rate_weight"]
        HungerMath.gain_rate_weight = config[entity_type][HungerComponent]["gain_rate_weight"]

        return HungerAspect(eid, entity_type, hunger, wellbeing, config, mem, brain, memory_engine)

    def is_hungry(self) -> bool:
        return self.wellbeing.hungry is not None

    def is_starving(self) -> bool:
        return self.wellbeing.starving is not None

    def adjust_hunger_naturally(self):
        delta = HungerMath.gain_rate(self.hunger.value)
        self._apply_hunger_change(delta)

    def forget_food(self, food: int, debug_entity_id: int | None = None):
        if self.mem.data.exists(f"food_{food}"):
            if debug_entity_id and self.entity == debug_entity_id:
                logger.debug("Entity %s forgetting food %s", self.entity, food)
            self.memory_engine.forget(self.mem.data, f"food_{food}")

    def adjust_hunger_from_eating(self, nutrition_multiplier: float = 1.0):
        delta = HungerMath.loss_rate(self.hunger.value) * nutrition_multiplier
        if get_global_config().debug_entity_id and self.entity == get_global_config().debug_entity_id:
            logger.debug(
                f"eid:{self.entity} ,Adjusting hunger from eating: {self.hunger.value} -> {self.hunger.value + delta} (multiplier: {nutrition_multiplier})"
            )
        self._apply_hunger_change(delta)

    def _apply_hunger_change(self, delta: float):
        if delta > 0 and self.hunger.value > HungerLevel.H9_STARVING.value:
            return
        self.hunger.set_clamped_value(self.hunger.value + delta)

    def reset_starving(self):
        self.wellbeing.starving = None

    def reset_hungry(self):
        self.wellbeing.hungry = None

    def should_hunger_turn_to_starving(self, simulation_time: int) -> bool:
        # TODO: this logic is somewhat flawed. hunger is set to be anything greater than H5_PECKISH,
        # but starving is seemingly calculated as being hungry for a set amount of time (even though it is also a level).
        # This means that if an entity is hungry for a long time, it will become starving, regardless of its level.
        # This feels wrong, as we are mixing duration and level.
        # This has two action items:
        # 1. Change this function to check if the hunger level has been static for a certain amount of time AND
        #    the hunger level is STARVING. It makes sense to make this a health condition if the "feeling" persists for a while.
        # 2. Maybe change the way levels are increased/decreased to be less linear.
        #    This would mean that values would gravitate towards a certain level (say, in the common case, H4_NEUTRAL),
        #    and progress towards the extreme slows down as it approaches the edge. a.k.a. a sigmoid function, with say c=0.5.
        duration = simulation_time - cast(WellbeingConditionComponent, self.wellbeing.hungry).since
        return duration > self.config[self.entity_type][HungerComponent]["time_to_starve"]

    def mark_starving_since(self, simulation_time: int):
        self.wellbeing.starving = WellbeingConditionComponent(since=simulation_time)

    def mark_hungry_since(self, simulation_time: int):
        self.wellbeing.hungry = WellbeingConditionComponent(since=simulation_time)


class HungerSystem(System):
    """
    Increase hunger value_over_time, decrease it when eating.
    """

    def update(self, simulation_time: int):
        hunger_entities: Iterator[int] = self.ecs.get_entities_with_typed_component(HungerComponent)
        stats = self.ecs.get_singleton_component(StatsComponent)
        for entity in hunger_entities:
            # TODO: this is a performance bottleneck. creating a new object every time is expensive.
            # see comment in HungerAspect.bind()s
            hunger_aspect = HungerAspect.bind(entity, self.ecs)
            activity = self.ecs.get_typed_component(entity, ActivityComponent)
            # Determine entity type to record stats properly
            entity_type = cast(EntityType, self.ecs.entities_by_id[entity])
            stat_ops.record_hunger(stats, entity_type, hunger_aspect.hunger.value)
            # Activity logic clearly separated from hunger aspect
            if activity.activity.is_eating():
                eating_activity = cast(EatingActivity, activity.activity)
                if self.ecs.entity_exists(eating_activity.food):
                    food_edible = self.ecs.get_typed_component(eating_activity.food, EdibleComponent)
                    nutrition_multiplier = food_edible.nutrition
                    if self.config.debug_entity_id and entity == self.config.debug_entity_id:
                        logger.debug(
                            f"Entity {entity} is eating: {activity.activity}, {nutrition_multiplier}, {self.ecs.entities_by_id[eating_activity.food]}"
                        )
                    hunger_aspect.adjust_hunger_from_eating(nutrition_multiplier)

                    # Handle different food sources
                    if self.ecs.entities_by_id[eating_activity.food] == EntityTypes.PLANT:
                        # Plants are consumed by reducing their size rather than being completely killed
                        growth = self.ecs.get_typed_component(eating_activity.food, GrowthComponent)
                        size_consumed = 0.1
                        growth.size = max(growth.size - size_consumed, 0.0)
                        self.ecs.update_typed_component(eating_activity.food, growth)
                        # Record food consumption for plant matter
                        stat_ops.record_plants_consumed(stats, size_consumed)
                    elif food_edible.perishable:
                        # Animals and other perishable food sources are completely consumed
                        prey_type = cast(EntityType, self.ecs.entities_by_id[eating_activity.food])
                        stat_ops.record_death(stats, prey_type, CauseOfDeath.EATEN.value)

                        # Remove the prey entity from ECS
                        self.ecs.remove_entity(eating_activity.food)
                else:
                    if self.config.debug_entity_id and entity == self.config.debug_entity_id:
                        logger.debug("Entity %s tried to eat non-existent!!!! food: %s", entity, eating_activity.food)
                    hunger_aspect.adjust_hunger_naturally()
                    hunger_aspect.forget_food(eating_activity.food, self.config.debug_entity_id)
            else:
                hunger_aspect.adjust_hunger_naturally()

            if hunger_aspect.is_starving():
                if HungerLevel.H6_HUNGRY.value_over(hunger_aspect.hunger.value):
                    hunger_aspect.reset_starving()
            elif hunger_aspect.is_hungry():
                if HungerLevel.H4_NEUTRAL.value_over(hunger_aspect.hunger.value):
                    hunger_aspect.reset_hungry()
                elif hunger_aspect.should_hunger_turn_to_starving(simulation_time):
                    hunger_aspect.mark_starving_since(simulation_time)
            elif HungerLevel.H5_PECKISH.value_under(hunger_aspect.hunger.value):
                hunger_aspect.mark_hungry_since(simulation_time)

            self.ecs.update_typed_component(entity, hunger_aspect.hunger)
            self.ecs.update_typed_component(entity, hunger_aspect.wellbeing)

        self.ecs.update_typed_singleton_component(stats)
