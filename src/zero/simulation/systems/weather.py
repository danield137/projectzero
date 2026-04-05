import random

from sim.ecs.system import System
from zero.simulation.components import (
    EntitiesConfigComponent,
    StatsComponent,
    WeatherConditionsComponent,
)
from zero.simulation.entities import EntityTypes
from zero.simulation.functional import stat_ops


class WeatherSystem(System):
    """Responsible for weather conditions"""

    def generate_weather_conditions(self, config: EntitiesConfigComponent) -> WeatherConditionsComponent:
        temperature = random.randint(
            config[EntityTypes.WEATHER][WeatherConditionsComponent]["temperature"]["min"],
            config[EntityTypes.WEATHER][WeatherConditionsComponent]["temperature"]["max"],
        )
        precipitation = random.randint(
            config[EntityTypes.WEATHER][WeatherConditionsComponent]["precipitation"]["min"],
            config[EntityTypes.WEATHER][WeatherConditionsComponent]["precipitation"]["max"],
        )
        sunlight = random.randint(
            config[EntityTypes.WEATHER][WeatherConditionsComponent]["sunlight"]["min"],
            config[EntityTypes.WEATHER][WeatherConditionsComponent]["sunlight"]["max"],
        )
        return WeatherConditionsComponent(precipitation, temperature, sunlight)

    def update(self, simulation_time: int):
        # TODO: not sure if we need this to happen every update, or on setup.
        # Right now configuration is immutable, so this might not be needed.
        # In the future, we might want to allow changing the configuration mid-simulation.
        config = self.ecs.get_singleton_component(EntitiesConfigComponent)
        weather_entities = self.ecs.get_entities_with_typed_component(WeatherConditionsComponent)
        if not weather_entities:
            raise ValueError("No weather entity found")
        # currently only global weather exists
        weather = next(weather_entities)
        weather_conditions = self.ecs.get_typed_component(weather, WeatherConditionsComponent)

        if not weather_conditions:
            raise ValueError("No weather conditions found")
        # on earth, we have 4 seasons, each with different weather conditions.
        # for simplicity sake, we will have only one season, and the weather will change randomly.
        # however, to make it somewhat more realistic, we will have a 60% chance of having the same
        # weather conditions as the previous day.
        if random.random() < 0.6:
            # keep the same weather conditions as the previous day
            return
        # otherwise, generate new weather conditions
        # TODO: technically, weather is affected by: planet distance from the sun, planet tilt,
        # atmospheric pressure, humidity, wind, topography, etc.
        # so, in theory, the min/max values below should be derived from the planet's properties,
        # and the specific tile we are on, but for now, we will keep it simple.
        new_weather_conditions = self.generate_weather_conditions(config)
        self.ecs.update_typed_component(weather, new_weather_conditions)
        # update the stats
        stats = self.ecs.get_singleton_component(StatsComponent)
        stat_ops.record_precipitation(stats, new_weather_conditions.precipitation)
        if new_weather_conditions.sunlight > 0:
            stat_ops.inc_sunny(stats)
        self.ecs.update_typed_singleton_component(stats)
