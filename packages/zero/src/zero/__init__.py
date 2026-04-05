from __future__ import annotations

import abc
import os
import time
import tracemalloc
from collections import defaultdict
from collections.abc import Sequence
from typing import Any, cast

from termcolor import colored

from sim.common import logging
from sim.common.ds.generational import GenerationalDict
from sim.common.formatting import human_readable_bytes, human_readable_time_measurement
from sim.config import RunConfiguration, set_global_config
from sim.ecs.core import ECS
from sim.ecs.system import System
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
    ReasoningSystem,
    ReproductionSystem,
    StatsSystem,
    WaterSystem,
    WeatherSystem,
    WorldsSystem,
)

logger = logging.get_logger()


class ECSQueries:
    @staticmethod
    def get_living_entity_ids_by_type(ecs: ECS) -> dict[str, int]:
        # TODO: perhaps a cleaner approach would be to have a system that deals with living entities
        # This system can look for a "mortality" component and remove the entity if it is dead, as well as other tasks,
        # e.g. reproduction, Birthday.
        living_entity_types = [EntityTypes.PLANT, EntityTypes.ANIMAL]
        result: dict[str, int] = {}
        for entity_type in living_entity_types:
            result[entity_type] = 0
            if entity_type in ecs.entities_by_type:
                result[entity_type] = len(ecs.entities_by_type[entity_type])
        return result


class Display(abc.ABC):
    sim: Simulation

    def __init__(self, sim: Simulation):
        self.sim = sim

    @abc.abstractmethod
    def render(self): ...


class ConsoleDisplay(Display):
    living_entities: dict[str, int]

    def __init__(self, sim: Simulation):
        super().__init__(sim)
        self.living_entities = defaultdict(int)

    def render(self):
        world_clocks = self.sim.ecs.get_entities_with_typed_component(LocalTimeComponent)
        world_clock = next(world_clocks)
        local_time = self.sim.ecs.get_typed_component(world_clock, LocalTimeComponent)
        day_passed = local_time.hour == 0 and local_time.day != 0
        if day_passed:
            living_entities = cast(HealthSystem, self.sim.system_instances[HealthSystem]).all_living_entities()
            summary: dict[str, int] = defaultdict(int)
            for living_entity in living_entities:
                etype = self.sim.ecs.entities_by_id[living_entity]
                if etype == EntityTypes.PLANT:
                    summary["Food"] += int(self.sim.ecs.get_typed_component(living_entity, GrowthComponent).size)
                summary[etype] += 1
            keys = list(summary.keys())
            for key in keys:
                prev = self.living_entities.get(key, 0)
                current = summary[key]
                summary[f"{key} Diff"] = current - prev
                self.living_entities[key] = current
            # logger.info(f"{planet_name.value}::{local_time.day}d,{local_time.year}y | {json.dumps(summary)}")


class Simulation:
    simulation_time: int = 0
    ecs: ECS
    config: RunConfiguration
    systems: list[type[System]] = [
        # world maintaining systems
        WorldsSystem,
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
    system_instances: dict[type[System], System] = {}

    def __init__(self, config: RunConfiguration | None = None):
        self.ecs = ECS(verbosity=logging.Verbosity.WARNING)
        self.config = config or RunConfiguration.default()
        set_global_config(self.config)

    def _log_timings(
        self, durations: dict[str, list[float]], *, prefix: str = "TIMINGS", color: str | None = "grey"
    ) -> None:
        """Log performance metrics for systems"""
        if not durations:
            return
        parts: list[str] = []
        total = ""
        for name, d in durations.items():
            if not d:
                continue
            avg = human_readable_time_measurement(sum(d) / len(d))
            if name == "total":
                total = "Total: %s" % avg
            else:
                parts.append("%s: %s" % (name, avg))

        if total or parts:
            message = "%s(%d):: %s%s%s" % (
                prefix,
                self.simulation_time,
                total,
                ", " if total and parts else "",
                ", ".join(parts),
            )
            logger.debug(colored(message, color))

    def _ecs_memory_stats(self) -> tuple[int, int, float]:
        """Calculate ECS memory fragmentation statistics"""
        total_used = 0
        total_holes = 0
        max_fragmentation = 0.0

        # Check all generational containers in the ECS
        containers_to_check: Sequence[GenerationalDict[int, Any]] = []
        containers_to_check.append(self.ecs.entities_by_id)

        # Add all entity type containers
        for container in self.ecs.entities_by_type.values():
            containers_to_check.append(container)

        # Add all component type containers
        for container in self.ecs.components_by_type.values():
            containers_to_check.append(container)

        containers_to_check.append(self.ecs.components_by_entity)

        for container in containers_to_check:
            gen_container = container._container if hasattr(container, "_container") else container
            if hasattr(gen_container, "_items") and hasattr(gen_container, "_free_indices"):
                total_slots = len(gen_container._items)
                holes = len(gen_container._free_indices)
                used = total_slots - holes

                total_used += used
                total_holes += holes

                if total_slots > 0:
                    fragmentation = holes / total_slots
                    max_fragmentation = max(max_fragmentation, fragmentation)

        return total_used, total_holes, max_fragmentation

    def _log_memory(self) -> None:
        """Log memory usage and ECS fragmentation statistics"""
        try:
            # Try to get process memory info
            try:
                import psutil

                proc = psutil.Process(os.getpid())
                rss = human_readable_bytes(proc.memory_info().rss)
            except ImportError:
                # Fallback to resource module on Unix systems
                try:
                    import resource

                    rss = human_readable_bytes(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024)
                except (ImportError, AttributeError):
                    rss = "N/A"

            # Get tracemalloc heap info if available
            try:
                current, _ = tracemalloc.get_traced_memory()
                heap = human_readable_bytes(current)
            except RuntimeError:
                # tracemalloc not started
                heap = "N/A"

            # Get ECS fragmentation stats
            used, holes, max_frag = self._ecs_memory_stats()
            total_slots = used + holes
            avg_frag = (holes / total_slots * 100) if total_slots > 0 else 0

            message = "MEM(%d):: RSS: %s, heap: %s | ECS used: %s, holes: %s (%.0f%%), max_frag: %.0f%%" % (
                self.simulation_time,
                rss,
                heap,
                f"{used:,}",
                f"{holes:,}",
                avg_frag,
                max_frag * 100,
            )
            logger.debug(colored(message, "cyan"))

        except Exception as e:
            logger.debug(colored("MEM(%d):: Error getting memory stats: %s" % (self.simulation_time, e), "red"))

    def _log_entity_summary(self, heading: str) -> None:
        """Log a summary of current entities in the simulation"""
        living = cast(HealthSystem, self.system_instances[HealthSystem]).all_living_entities()
        summary: dict[str, int] = defaultdict(int)
        for eid in living:
            etype = self.ecs.entities_by_id[eid]
            if etype == EntityTypes.PLANT:
                summary["Food"] += int(self.ecs.get_typed_component(eid, GrowthComponent).size)
            summary[etype] += 1

        world_clock = next(self.ecs.get_entities_with_typed_component(LocalTimeComponent))
        lt = self.ecs.get_typed_component(world_clock, LocalTimeComponent)
        planet = self.ecs.get_typed_component(world_clock, NameComponent).value

        logger.info("%s - %s: Day %d, Year %d | %s", heading, planet, lt.day, lt.year, dict(summary))

    def setup_simulation(self):
        systems_initialized: list[str] = []
        for system_cls in self.systems:
            system = system_cls()
            system.init_system(self.ecs)
            systems_initialized.append(system_cls.__name__)
            self.system_instances[system_cls] = system

        logger.info(
            "Systems initialized: %s",
            colored(", ".join([s.replace("System", "") for s in systems_initialized]), "light_magenta"),
        )

        for system in self.system_instances.values():
            assert system.validate(), "System %s failed validation" % system.__class__.__name__

    def set_starting_conditions(self):
        logger.info("Creating static entities...")
        # TODO: I don't like this approach. I tend to forget that there is such a thing as a metadata entity.
        # Effectively, these components are all part of a stats system, but they don't really make up an entity per se.
        self.ecs.create_singleton_entity(*EntitiesFactory.metadata_entity())
        self.ecs.create_singleton_entity(*EntitiesFactory.create_config_entity())
        # Create the Earth entity (World)
        self.ecs.create_entity(*EntitiesFactory.create_world("Earth"))
        # Create a global weather entity
        self.ecs.create_entity(*EntitiesFactory.create_weather())
        logger.info("Creating dynamic entities...")
        # Create a few plants
        for i in range(200):
            self.ecs.create_entity(*EntitiesFactory.create_plant(f"Plant_{i}"))

        # Create a couple of animals
        animal_spawner = EntitiesFactory.gender_balanced_spawner(EntitiesFactory.create_animal, prefix="Animal")
        for _ in range(4):
            etype, comps = animal_spawner()
            self.ecs.create_entity(etype, comps)

        # Create a couple of humans
        human_spawner = EntitiesFactory.gender_balanced_spawner(EntitiesFactory.create_human, prefix="Human")
        for _ in range(2):
            etype, comps = human_spawner()
            self.ecs.create_entity(etype, comps)

    def run(self, max_ticks: int | None = None, debug_mode: bool = True):
        # Start memory tracing if in debug mode
        if debug_mode:
            tracemalloc.start()

        # gui = SimulationGUI()
        display = ConsoleDisplay(self)
        logging.sim_time_var.set(-1)
        logger.info("Setting up simulation")
        self.setup_simulation()
        logger.info("Setting starting conditions")
        self.set_starting_conditions()
        logger.info("Starting loop")

        update_duration: dict[str, list[float]] = defaultdict(list)
        has_limit = max_ticks is not None and max_ticks > 0
        while not has_limit or self.simulation_time < cast(int, max_ticks):
            tick_start = time.time()
            logging.sim_time_var.set(self.simulation_time)
            if self.simulation_time % 100 == 0 and self.simulation_time != 0:
                if debug_mode:
                    self._log_timings(update_duration)
                    self._log_memory()
                update_duration = defaultdict(list)

            if self.simulation_time % 10000 == 0:
                logger.info("Simulation time: %d", self.simulation_time)
            for system in self.system_instances.values():
                update_start = time.time()
                # In the current implementation, systems are allowed to make immediate changes to the ECS
                # this has drawbacks, e.g. if a system removes an entity, the next system will not see it.
                # this means, order of systems matters, and they become harder to parallelize (need to break them into disjoined groups).
                # The other approach is to batch all changes and apply them after all systems have run.
                # this makes reasoning easier, but needs to carefully manBirthday conflicts,
                # e.g. if an is to be removed, but also to create another entity (in which case they cancel out / or we define an order).
                system.update(self.simulation_time)
                update_duration[type(system).__name__].append(time.time() - update_start)
            display.render()
            self.simulation_time += 1
            update_duration["total"].append(time.time() - tick_start)
            # sleep(0.01)

        # If we exited due to a limit, print final summary
        if has_limit:
            logger.info("Simulation completed after %d ticks", self.simulation_time)
            if debug_mode:
                self._log_timings(update_duration, prefix="FINAL TIMINGS", color="green")
                self._log_memory()
                self._log_entity_summary("Final state")
