from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import cast

from simz.ai.brain import Brain
from simz.ai.context import BrainContext
from simz.ai.memory import MemoryFact
from simz.common.enum import TriStateEnum
from simz.common.logging import get_logger
from simz.config import get_global_config
from simz.ecs.core import ECS
from simz.ecs.system import System
from zero.ai.actions import ActionStep
from zero.ai.brains import get_predefined_brain
from zero.ai.context import (
    CanEatFn,
    PrimitiveBrainContext,
    PrimitiveWorldRules,
)
from zero.ai.primitive import PrimitiveGoal
from zero.simulation.components import (
    ActivityComponent,
    BrainComponent,
    DietComponent,
    DietType,
    EdibleComponent,
    EnergyComponent,
    FoodType,
    HungerComponent,
    MemoryComponent,
    StatsComponent,
    WellbeingComponent,
)
from zero.simulation.functional import stat_ops
from zero.simulation.functional.stat_ops import EntityType

logger = get_logger()


def can_eat_predicate(eater_entity: int, food_id: int, ecs: ECS) -> TriStateEnum:
    diet = ecs.get_typed_component(eater_entity, DietComponent)
    if not ecs.entity_exists(food_id):
        return TriStateEnum.UNKNOWN
    edible_comp = ecs.get_typed_component(food_id, EdibleComponent)

    predator_species = ecs.entities_by_id[eater_entity]
    edible_species = ecs.entities_by_id[food_id]
    cannibalism = predator_species == edible_species

    if edible_comp.food_type == FoodType.PLANT:
        return TriStateEnum.from_bool(diet.diet_type in (DietType.HERBIVORE, DietType.OMNIVORE))

    if edible_comp.food_type == FoodType.MEAT:
        can_eat = diet.diet_type in (DietType.CARNIVORE, DietType.OMNIVORE)
        if can_eat:
            if cannibalism:
                return TriStateEnum.from_bool(diet.allow_cannibalism)
            return TriStateEnum.TRUE

    return TriStateEnum.FALSE


def get_can_eat_fn(ecs: ECS) -> CanEatFn:
    """
    Returns a function that checks if an entity can eat another entity based on their diet.
    This function is used to determine if an entity can consume a specific food item.
    """
    return lambda eater_entity, food_id: can_eat_predicate(eater_entity, food_id, ecs)


def precompute_edible_groups(ecs: ECS) -> dict[FoodType, dict[str, list[int]]]:
    """
    Pre-compute edible entities grouped by food type and species.
    Returns: dict[FoodType, dict[species, list[entity_ids]]]
    """
    edible_groups: dict[FoodType, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))

    for food_id in ecs.get_entities_with_typed_component(EdibleComponent):
        edible_comp = ecs.get_typed_component(food_id, EdibleComponent)
        species = ecs.entities_by_id[food_id]
        edible_groups[edible_comp.food_type][species].append(food_id)

    return edible_groups


def add_food_facts_for_eater(
    eater_id: int,
    eater_species: str,
    diet: DietComponent,
    memory: MemoryComponent,
    brain_impl: Brain[PrimitiveGoal],
    simulation_time: int,
    edible_groups: dict[FoodType, dict[str, list[int]]],
    ecs: ECS,
) -> None:
    """
    Add food facts to an eater's memory using pre-computed edible groups.
    This is the optimized replacement for manually_add_food_to_memory.
    """
    debug_entity_id = get_global_config().debug_entity_id

    # Determine which food types this eater can consume
    food_types_to_check: list[FoodType] = []
    if diet.diet_type in (DietType.HERBIVORE, DietType.OMNIVORE):
        food_types_to_check.append(FoodType.PLANT)
    if diet.diet_type in (DietType.CARNIVORE, DietType.OMNIVORE):
        food_types_to_check.append(FoodType.MEAT)

    for food_type in food_types_to_check:
        species_groups = edible_groups[food_type]

        for species, food_ids in species_groups.items():
            # Check cannibalism rules
            if species == eater_species and not diet.allow_cannibalism:
                continue

            for food_id in food_ids:
                if food_id == eater_id:  # Skip self
                    continue

                fid = f"food_{food_id}"
                if memory.data.exists(fid):  # Skip if already in memory
                    continue

                # Create memory fact only when needed
                if debug_entity_id and eater_id == debug_entity_id:
                    logger.debug("Entity %s adding food %s to memory", eater_id, food_id)

                brain_impl.memory.remember(
                    memory.data,
                    MemoryFact(
                        fid,
                        "food",
                        simulation_time,
                        {
                            "owned": True,
                            "id": food_id,
                            "location": "unknown",
                            "species": species,
                            "food_type": food_type,
                        },
                    ),
                )


def manually_add_food_to_memory(
    eid: int,
    ecs: ECS,
    brain_impl: Brain[PrimitiveGoal],
    memory: MemoryComponent,
    simulation_time: int,
    can_eat: CanEatFn,
) -> None:
    """
    Manually scan for edible entities and add them to memory.

    # TODO: this logic really belongs in the perception system.
    This is a temporary implementation until we have proper food discovery.
    DEPRECATED: Use add_food_facts_for_eater with precomputed groups for better performance.
    """
    edibles = ecs.get_entities_with_typed_component(EdibleComponent)
    for edible_id in edibles:
        if edible_id == eid:  # Skip self
            continue

        edible_comp = ecs.get_typed_component(edible_id, EdibleComponent)
        edible_species = ecs.entities_by_id[edible_id]

        if not can_eat(eid, edible_id):
            continue  # Cannot eat this entity

        fid = f"food_{edible_id}"
        if not memory.data.exists(fid):
            debug_entity_id = get_global_config().debug_entity_id
            if debug_entity_id and eid == debug_entity_id:  # Debug entity ID
                logger.debug("Entity %s adding food %s to memory", eid, edible_id)
            brain_impl.memory.remember(
                memory.data,
                MemoryFact(
                    fid,
                    "food",
                    simulation_time,
                    {
                        "owned": True,
                        "id": edible_id,
                        "location": "unknown",
                        "species": edible_species,
                        "food_type": edible_comp.food_type,
                    },
                ),
            )


@dataclass(slots=True)
class ReasoningAspect:
    """
    Holds the components needed for reasoning.
    Binds to an ECS instance to gather the components and then
    uses the AI engine (PrimitiveBrain) to decide the next action.
    """

    activity: ActivityComponent
    health_conditions: WellbeingComponent
    energy: EnergyComponent
    hunger: HungerComponent
    brain: BrainComponent
    brain_impl: Brain[PrimitiveGoal]
    memory: MemoryComponent
    ctx: BrainContext
    simulation_time: int

    @staticmethod
    def bind(
        eid: int, ecs: ECS, simulation_time: int, edible_groups: dict[FoodType, dict[str, list[int]]]
    ) -> ReasoningAspect:
        activity = ecs.get_typed_component(eid, ActivityComponent)
        health_conditions = ecs.get_typed_component(eid, WellbeingComponent)
        energy = ecs.get_typed_component(eid, EnergyComponent)
        hunger = ecs.get_typed_component(eid, HungerComponent)
        brain = ecs.get_typed_component(eid, BrainComponent)
        brain_impl = get_predefined_brain(brain.brain_type)
        memory = ecs.get_typed_component(eid, MemoryComponent)
        is_pregnant = health_conditions.pregnancy is not None

        rules = PrimitiveWorldRules(
            can_eat=get_can_eat_fn(ecs),
        )
        add_food_facts_for_eater(
            eid,
            ecs.entities_by_id[eid],  # Get species from entity ID
            ecs.get_typed_component(eid, DietComponent),
            memory,
            brain_impl,
            simulation_time,
            edible_groups,
            ecs,
        )
        # manually_add_food_to_memory(eid, ecs, brain_impl, memory, simulation_time, rules.can_eat)

        ctx = PrimitiveBrainContext(
            simulation_time=simulation_time,
            eid=eid,
            etype=ecs.entities_by_id[eid],
            hunger=hunger.value / 10.0,
            energy=energy.value / 10.0,
            is_pregnant=is_pregnant,
            memory_data=memory.data,
            memory_engine=brain_impl.memory,
            rules=rules,
        )
        return ReasoningAspect(
            activity, health_conditions, energy, hunger, brain, brain_impl, memory, ctx, simulation_time
        )

    def select_goal(self) -> PrimitiveGoal:
        # Delegate decision-making to PrimitiveBrain.
        return self.brain_impl.goal_selector.select_goal(self.ctx)

    def plan(self, goal: PrimitiveGoal) -> list[ActionStep]:
        # Delegate planning to PrimitiveBrain.
        return self.brain_impl.planner.make_plan(self.ctx, goal)


def is_same_plan(plan1: Sequence[ActionStep], plan2: Sequence[ActionStep]) -> bool:
    """Compare plans by their action types and field values."""
    if len(plan1) != len(plan2):
        return False
    for a, b in zip(plan1, plan2):
        if a.__class__.__name__ != b.__class__.__name__ or json.dumps(asdict(a)) != json.dumps(asdict(b)):
            return False
    return True


class ReasoningSystem(System):
    def update(self, simulation_time: int):
        # Get unified stats component
        stats = self.ecs.get_singleton_component(StatsComponent)

        # Pre-compute edible groups once for all thinking entities
        edible_groups = precompute_edible_groups(self.ecs)

        # Process all entities with an ActivityComponent.
        thinking_entities = self.ecs.get_entities_with_typed_component(BrainComponent)
        for entity in thinking_entities:
            ra = ReasoningAspect.bind(entity, self.ecs, simulation_time, edible_groups)

            # Record goal statistics using unified stats
            entity_type = cast(EntityType, self.ecs.entities_by_id[entity])
            stat_ops.record_goal(stats, entity_type, ra.brain.current_goal)

            # Decide the next activity using our encapsulated decision logic.
            new_goal = ra.select_goal()
            new_plan = ra.plan(new_goal)
            if self.config.debug_entity_id is not None and entity == self.config.debug_entity_id:
                logger.debug(
                    "Entity %s selected goal: %s, plan: %s, energy=%s, hunger=%s, pregnant=%s",
                    entity,
                    new_goal,
                    [step.__repr__() for step in new_plan],
                    ra.energy.value,
                    ra.hunger.value,
                    ra.health_conditions.pregnancy is not None,
                )
            current_plan = cast(Sequence[ActionStep], ra.brain.current_plan)
            if new_goal != ra.brain.current_goal or not is_same_plan(new_plan, current_plan):
                ra.brain.current_goal = new_goal
                ra.brain.current_plan = new_plan
                self.ecs.update_typed_component(entity, ra.brain)

        # Update unified stats component
        self.ecs.update_typed_singleton_component(stats)
