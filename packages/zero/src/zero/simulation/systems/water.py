from simz.ecs.system import System
from zero.simulation.components import HydrationComponent, WeatherConditionsComponent


class WaterSystem(System):
    def update(self, simulation_time: int):
        # in theory, this should handle all water related logic, e.g. evaporation, hydration, water tables, water sources, etc.
        # for now, we only need hydration for plants.
        hydratable = self.ecs.get_entities_with_typed_component(HydrationComponent)
        weather_entities = self.ecs.get_entities_with_typed_component(WeatherConditionsComponent)
        for weather in weather_entities:
            weather_conditions = self.ecs.get_typed_component(weather, WeatherConditionsComponent)
            # todo: weather should be localized, and once it will be, we will need to apply the weather conditions to the entities in the same location.
            # for now, we will just apply the global weather conditions to all entities.

            # todo2: hydration should be more complex, taking into account the type of plant, the soil, the weather, etc.
            # todo3: also, precipitation is just the probability of rain. We should materialize the probability into actual rain,
            # and then calculate the amount of water that is absorbed by the soil, and the amount that is left on the surface.

            # for now, we will just increase hydration by 5 if it's raining, and decrease it by 1 if it's not.
            if weather_conditions.precipitation > 50:
                for entity in hydratable:
                    hydration = self.ecs.get_typed_component(entity, HydrationComponent)
                    hydration.set_clamped_value(hydration.value + 5.0)
                    self.ecs.update_typed_component(entity, hydration)
            else:
                for entity in hydratable:
                    hydration = self.ecs.get_typed_component(entity, HydrationComponent)
                    hydration.set_clamped_value(hydration.value - 1.0)
                    self.ecs.update_typed_component(entity, hydration)
