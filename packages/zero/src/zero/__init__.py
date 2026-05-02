from __future__ import annotations

from collections import defaultdict

from tigen.app import App, AppBuilder
from tigen.common import logging
from tigen.config import RunConfiguration
from tigen.ecs.core import ECS
from tigen.ecs.system import System

from zero.simulation.components import (
    GrowthComponent,
    LocalTimeComponent,
    NameComponent,
)
from zero.simulation.entities import EntitiesFactory, EntityTypes
from zero.simulation.systems import (
    ActuationSystem,
    EnergySystem,
    GrowthSystem,
    HealthSystem,
    HungerSystem,
    InstinctSystem,
    PerceptionSystem,
    PhotosynthesisSystem,
    PlanetSystem,
    ReasoningSystem,
    ReproductionSystem,
    StatsSystem,
    WaterSystem,
    WeatherSystem,
)

logger = logging.get_logger()

# Domain systems in execution order
ZERO_SYSTEMS: list[type[System]] = [
    # world maintaining systems
    PlanetSystem,
    HealthSystem,
    WeatherSystem,
    WaterSystem,
    # fauna and flora systems
    PhotosynthesisSystem,
    ReproductionSystem,
    EnergySystem,
    HungerSystem,
    GrowthSystem,
    # higher level systems
    PerceptionSystem,
    InstinctSystem,
    ReasoningSystem,
    ActuationSystem,
    # stats and debugging systems
    StatsSystem,
]


class ConsoleRenderSystem(System):
    living_entities: dict[str, int]

    def init_system(self, ecs: ECS):
        super().init_system(ecs)
        self.living_entities = defaultdict(int)

    def update(self, simulation_time: int):
        world_clocks = self.ecs.get_entities_with_typed_component(LocalTimeComponent)
        world_clock = next(world_clocks)
        local_time = self.ecs.get_typed_component(world_clock, LocalTimeComponent)
        day_passed = local_time.hour == 0 and local_time.day != 0
        if day_passed:
            summary: dict[str, int] = defaultdict(int)
            for eid, etype in self.ecs.entities_by_id.smart_enumerate():
                if etype == EntityTypes.PLANT:
                    summary["Food"] += int(self.ecs.get_typed_component(eid, GrowthComponent).size)
                if etype in (EntityTypes.PLANT, EntityTypes.ANIMAL, EntityTypes.HUMAN):
                    summary[etype] += 1
            keys = list(summary.keys())
            for key in keys:
                prev = self.living_entities.get(key, 0)
                current = summary[key]
                summary[f"{key} Diff"] = current - prev
                self.living_entities[key] = current


def setup_zero_world(ecs: ECS) -> None:
    logger.info("Creating static entities...")
    ecs.create_singleton_entity(*EntitiesFactory.metadata_entity())
    ecs.create_singleton_entity(*EntitiesFactory.create_config_entity())
    # Create the Earth entity
    ecs.create_entity(*EntitiesFactory.create_planet("Earth"))
    # Create a global weather entity
    ecs.create_entity(*EntitiesFactory.create_weather())
    logger.info("Creating dynamic entities...")
    # Create a few plants
    for i in range(200):
        ecs.create_entity(*EntitiesFactory.create_plant(f"Plant_{i}"))

    # Create a couple of animals
    animal_spawner = EntitiesFactory.gender_balanced_spawner(EntitiesFactory.create_animal, prefix="Animal")
    for _ in range(4):
        etype, comps = animal_spawner()
        ecs.create_entity(etype, comps)

    # Create a couple of humans
    human_spawner = EntitiesFactory.gender_balanced_spawner(EntitiesFactory.create_human, prefix="Human")
    for _ in range(2):
        etype, comps = human_spawner()
        ecs.create_entity(etype, comps)


def log_entity_summary(app: App, heading: str) -> None:
    """Log a summary of current entities in the simulation."""
    summary: dict[str, int] = defaultdict(int)
    for eid, etype in app.ecs.entities_by_id.smart_enumerate():
        if etype == EntityTypes.PLANT:
            summary["Food"] += int(app.ecs.get_typed_component(eid, GrowthComponent).size)
        if etype in (EntityTypes.PLANT, EntityTypes.ANIMAL, EntityTypes.HUMAN):
            summary[etype] += 1

    world_clock = next(app.ecs.get_entities_with_typed_component(LocalTimeComponent))
    lt = app.ecs.get_typed_component(world_clock, LocalTimeComponent)
    planet = app.ecs.get_typed_component(world_clock, NameComponent).value

    logger.info("%s - %s: Day %d, Year %d | %s", heading, planet, lt.day, lt.year, dict(summary))


def create_app(
    config: RunConfiguration | None = None,
    systems: list[type[System]] | None = None,
    render_systems: list[type[System]] | None = None,
    refresh_rate: float | None = None,
    measurements: bool = False,
) -> App:
    """Create an App configured for the zero simulation."""
    builder = (
        AppBuilder()
        .with_systems(systems or ZERO_SYSTEMS)
        .with_setup(setup_zero_world)
        .with_config(config or RunConfiguration.default())
    )
    if render_systems:
        builder.with_render_systems(render_systems)
    if refresh_rate is not None:
        builder.with_refresh_rate(refresh_rate)
    if measurements:
        builder.with_measurements()
    return builder.build()
