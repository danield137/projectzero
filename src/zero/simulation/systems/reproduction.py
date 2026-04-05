import random

from sim.common import logging
from sim.ecs.core import ECS
from sim.ecs.system import System
from zero.simulation.components import (  # BirthdayComponent,
    ActivityComponent,
    EnergyComponent,
    FamilyComponent,
    Gender,
    HungerComponent,
    IdleActivity,
    MatingActivity,
    PregnancyComponent,
    ReproductiveComponent,
    WellbeingComponent,
)

logger = logging.get_logger()


def find_mate(target_gender: Gender, eid: int, ecs: ECS) -> int | None:
    etype = ecs.entities_by_id[eid]
    for candidate in ecs.get_entities_with_typed_component(ReproductiveComponent, etype):
        candidate_repro = ecs.get_typed_component(candidate, ReproductiveComponent)
        if candidate_repro.gender == target_gender and candidate != eid:
            prev_mate = ecs.get_typed_component(candidate, FamilyComponent).mate
            # TODO: IRL, this isn't required (monogamy is not a requirement for mating). Keeping it here for simplicity for now.
            if prev_mate is None:
                return candidate
            if not ecs.entity_exists(prev_mate):
                # the previous mate is dead, so we can use this candidate
                return candidate
    return None


class ReproductionSystem(System):
    def update(self, simulation_time: int):
        # TODO: this needs to be more efficient. We need to have a pair-matching algorithm the respects certain conditions
        # at the moment, we get a worse-case O(n^2) complexity, which is not ideal
        reproductive_entities = self.ecs.get_entities_with_typed_component(ReproductiveComponent)
        for entity in reproductive_entities:
            activity = self.ecs.get_typed_component(entity, ActivityComponent)
            if not isinstance(activity.activity, MatingActivity):
                continue  # only process entities that are in mating activity

            # TODO:
            # mate = activity.activity.mate
            # # Check if mate is also in mating activity
            # mate_activity = self.ecs.get_typed_component(mate, ActivityComponent)
            # if not isinstance(mate_activity.activity, MatingActivity):
            #     continue  # only proceed if both partners are in mating activity

            # Most lines below are sanity checks.
            # TODO: A better approach would be to have these preconditions as part of the activity / action itself
            # or, alternatively, an ActivityValidator that would validate the activity before it is executed.
            # I'm still not entirely sure how to structure activities / actions, and if it make sense to have them as separate entities.
            # It would seem that actions are internal and coupled with plans/goals (AI), where as Activities are more like a state of the entity,
            # that are used by other systems, so, a protocol of sorts.
            # TODO #2: Picking a mate should not be part of reproduction system. We need a social
            # interaction system that would handle coupling, friendship, etc.
            # when a mating goal is set, the plan should review the current state of the social interactions and decide on a mate.
            # There should probably be a prior step of "engaging in mating activity" that needs both parties to "agree" to mate.
            # So, the reproduction system should only handle the actual mating process, not the social interactions leading to it.
            repro = self.ecs.get_typed_component(entity, ReproductiveComponent)
            if repro.gender == "M":
                continue  # male animals can't get pregnant, so we skip them
            current_health_conditions = self.ecs.get_typed_component(entity, WellbeingComponent)
            if current_health_conditions.pregnancy is not None:
                # already pregnant
                continue
            family = self.ecs.get_typed_component(entity, FamilyComponent)
            if family.mate is None:
                # todo: social interactions need to be modeled as a separate system
                # for the sake of this initial implementation, we just couple them randomly
                potential_mate = find_mate("M", entity, self.ecs)
                if potential_mate is not None:
                    family.mate = potential_mate
                    potential_mate_family = self.ecs.get_typed_component(potential_mate, FamilyComponent)
                    potential_mate_family.mate = entity
                    self.ecs.update_typed_component(entity, family)
                    self.ecs.update_typed_component(potential_mate, potential_mate_family)
                continue
            mate = family.mate
            still_alive = self.ecs.entity_exists(mate)
            if not still_alive:
                family.mate = None
                self.ecs.update_typed_component(entity, family)
                continue
            if self.ecs.get_typed_component(mate, ReproductiveComponent).gender == repro.gender:
                continue  # same gender can't make offspring (for now at least)
            energy = self.ecs.get_typed_component(entity, EnergyComponent)
            mate_energy = self.ecs.get_typed_component(mate, EnergyComponent)
            if energy is None or mate_energy is None:
                logger.warning(
                    "Entity %s or mate [e:%s, mate e:%s] have no energy component", entity, energy, mate_energy
                )
                continue
            if energy.value < 5 or mate_energy.value < 5:
                # can't mate if either the animal or the mate doesn't have enough energy
                continue
            # Apply fertility probability check
            male_fertility = self.ecs.get_typed_component(mate, ReproductiveComponent).fertility
            female_fertility = repro.fertility
            if random.random() >= female_fertility * male_fertility:
                # Failed fertility check
                continue

            offsprings = 1.0
            hunger = self.ecs.get_typed_component(entity, HungerComponent)
            mate_hunger = self.ecs.get_typed_component(mate, HungerComponent)

            if hunger.value < 5:
                offsprings += 1.0
            if mate_hunger.value < 5:
                offsprings += 1.0
            # consider splitting out the component from the health conditions component
            pregnancy = PregnancyComponent(since=simulation_time, offsprings=offsprings, mate=mate)
            # mark pregnancy
            current_health_conditions.pregnancy = pregnancy
            self.ecs.update_typed_component(entity, current_health_conditions)
            # reset activity
            act_comp = self.ecs.get_typed_component(entity, ActivityComponent)
            act_comp.activity = IdleActivity(since=simulation_time)
            self.ecs.update_typed_component(entity, act_comp)
