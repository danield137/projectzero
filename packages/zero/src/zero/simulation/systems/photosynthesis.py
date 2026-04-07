from tigen.common import logging
from tigen.ecs.system import System
from zero.simulation.components import (
    HydrationComponent,
    PhotosynthesisComponent,
    WeatherConditionsComponent,
)

logger = logging.get_logger()


class PhotosynthesisSystem(System):
    def update(self, simulation_time: int):
        relevant_entities = self.ecs.get_entities_with_typed_component(PhotosynthesisComponent)

        # Get weather conditions if available
        weather_entities = list(self.ecs.get_entities_with_typed_component(WeatherConditionsComponent))
        if not weather_entities:
            logger.warning("No weather entities found. Assuming default good weather conditions.")
            has_sun = True
        else:
            # todo: for now, we only have one weather entity. In the future, we might have multiple weather entities
            local_weather = weather_entities[0]
            local_weather_conditions = self.ecs.get_typed_component(local_weather, WeatherConditionsComponent)
            has_sun = local_weather_conditions.sunlight > 0
        for entity in relevant_entities:
            hydration = self.ecs.get_typed_component(entity, HydrationComponent)
            if has_sun and hydration and hydration.value > 0:
                self.ecs.update_typed_component(entity, PhotosynthesisComponent(True))
            else:
                self.ecs.update_typed_component(entity, PhotosynthesisComponent(False))
