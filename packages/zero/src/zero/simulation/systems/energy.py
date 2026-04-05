from typing import cast

from simz.common import logging
from simz.common.enum import MonotonicEnum
from simz.ecs.system import System
from zero.simulation.components import (
    ActivityComponent,
    EnergyComponent,
    EntitiesConfigComponent,
    HungerComponent,
    PhotosynthesisComponent,
    StatsComponent,
    WellbeingComponent,
    WellbeingConditionComponent,
)
from zero.simulation.functional import stat_ops
from zero.simulation.functional.stat_ops import EntityType

logger = logging.get_logger()


class EnergyLevel(MonotonicEnum):
    E0_EXHAUSTED = 0
    E1_VERY_TIRED = 1
    E2_TIRED = 2
    E3_FATIGUED = 3
    E4_MODERATE = 4
    E5_NORMAL = 5
    E6_FINE = 6
    E7_GOOD = 7
    E8_FRESH = 8
    E9_ENERGETIC = 9


class EnergySystem(System):
    def handle_digestive(self, entity: int, simulation_time: int):
        energy = self.ecs.get_typed_component(entity, EnergyComponent)
        hunger = self.ecs.get_typed_component(entity, HungerComponent)
        activity = self.ecs.get_typed_component(entity, ActivityComponent)
        health_conditions = self.ecs.get_typed_component(entity, WellbeingComponent)
        config = self.ecs.get_singleton_component(EntitiesConfigComponent)
        etype = cast(EntityType, self.ecs.entities_by_id[entity])
        if activity.activity.is_sleeping():
            # Sleeping recovers energy slowly
            # todo: this is a simplistic model. The more accurate way to model it is such that sleeping is
            # closely tied to the efficiency of the digestive system, and the energy consumption of the brain.
            # this would require me to track the "sleep debt", and the bigger it is, the more energy is consumed (as a multiplier > 1)
            energy_gain = 1.0
            energy.set_clamped_value(energy.value + energy_gain)
            hunger.set_clamped_value(hunger.value + 0.5)
        else:
            # TODO: differentiate between low energy activity and high energy activity ("active_drain_rate")
            energy_gain = -config[etype][EnergyComponent]["idle_drain_rate"]
            energy.set_clamped_value(energy.value + energy_gain)
            hunger.set_clamped_value(hunger.value + 1.0)

        if EnergyLevel.E2_TIRED.value_under(energy.value):
            health_conditions.tired = WellbeingConditionComponent(simulation_time)
            self.ecs.update_typed_component(entity, health_conditions)
        elif EnergyLevel.E5_NORMAL.value_over(energy.value):
            if health_conditions.tired:
                health_conditions.tired = None
                self.ecs.update_typed_component(entity, health_conditions)

        self.ecs.update_typed_component(entity, hunger)
        self.ecs.update_typed_component(entity, energy)

    def handle_photosynthesis(self, entity: int):
        # if the entity is photosynthetic, and is currently photosynthesizing, it gains energy.
        photosynth = self.ecs.get_typed_component(entity, PhotosynthesisComponent)
        energy = self.ecs.get_typed_component(entity, EnergyComponent)
        if photosynth.value:
            energy.value = energy.value + 3.0
        else:
            energy.value = energy.value - 0.5
        self.ecs.update_typed_component(entity, energy)

    def handle_sleeping(self, entity: int, simulation_time: int):
        # if the entity is sleeping, it gains energy.
        energy = self.ecs.get_typed_component(entity, EnergyComponent)
        activity = self.ecs.get_typed_component(entity, ActivityComponent)
        etype = cast(EntityType, self.ecs.entities_by_id[entity])
        config = self.ecs.get_singleton_component(EntitiesConfigComponent)
        sleep_gain_rate = config[etype][EnergyComponent]["sleep_gain_rate"]
        if activity.activity.is_sleeping():
            energy.value = energy.value + sleep_gain_rate
            energy.set_clamped_value(energy.value)
            # bad. we update this from multiple places, and it should be done in one place.
            self.ecs.update_typed_component(entity, energy)

    def update(self, simulation_time: int):
        energy_entities = self.ecs.get_entities_with_typed_component(EnergyComponent)
        stats = self.ecs.get_singleton_component(StatsComponent)

        for entity in energy_entities:
            # Record energy stats for this entity
            entity_type = cast(EntityType, self.ecs.entities_by_id[entity])
            energy = self.ecs.get_typed_component(entity, EnergyComponent)
            stat_ops.record_energy(stats, entity_type, energy.value)

            if self.ecs.has_typed_component(entity, HungerComponent):
                self.handle_digestive(entity, simulation_time)
            if self.ecs.has_typed_component(entity, PhotosynthesisComponent):
                self.handle_photosynthesis(entity)
            activity = self.ecs.get_typed_component(entity, ActivityComponent)
            if activity.activity.is_sleeping():
                self.handle_sleeping(entity, simulation_time)
        self.ecs.update_typed_singleton_component(stats)
