from tigen.common import logging
from tigen.ecs.system import System
from zero.simulation.components import (
    GrowthComponent,
    PhotosynthesisComponent,
    StatsComponent,
)
from zero.simulation.functional import stat_ops

logger = logging.get_logger()


class GrowthSystem(System):
    def die(self, entity: int):
        self.ecs.remove_entity(entity)

    def update(self, simulation_time: int):
        stats = self.ecs.get_singleton_component(StatsComponent)
        growables = self.ecs.get_entities_with_typed_component(GrowthComponent)

        for growable in growables:
            growth = self.ecs.get_typed_component(growable, GrowthComponent)
            if growth.size <= 0.0:
                self.die(growable)
                continue
            ps = self.ecs.get_typed_component(growable, PhotosynthesisComponent)
            if ps.value:
                growth.size += growth.growth_rate
                stat_ops.record_plants_growth(stats, growth.growth_rate)
                self.ecs.update_typed_component(growable, growth)
            stat_ops.record_plants_biomass(stats, growth.size)

        self.ecs.update_typed_singleton_component(stats)
