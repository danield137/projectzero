from __future__ import annotations

import os
import time
import tracemalloc
from collections import defaultdict
from collections.abc import Callable
from typing import cast

from termcolor import colored

from tigen.common import logging
from tigen.common.ds.generational import Container
from tigen.common.formatting import human_readable_bytes, human_readable_time_measurement
from tigen.config import RunConfiguration, set_global_config
from tigen.ecs.core import ECS
from tigen.ecs.system import System

logger = logging.get_logger()


class App:
    simulation_time: int
    ecs: ECS
    config: RunConfiguration
    system_instances: dict[type[System], System]

    _systems: list[type[System]]
    _setup_fn: Callable[[ECS], None]
    _stop_condition: Callable[[App], bool] | None
    _log_interval: int
    _summary_interval: int

    def __init__(
        self,
        *,
        systems: list[type[System]],
        setup_fn: Callable[[ECS], None],
        config: RunConfiguration,
        stop_condition: Callable[[App], bool] | None = None,
        log_interval: int = 100,
        summary_interval: int = 10000,
    ) -> None:
        self.simulation_time = 0
        self.ecs = ECS(verbosity=logging.Verbosity.WARNING)
        self.config = config
        self.system_instances = {}
        self._systems = systems
        self._setup_fn = setup_fn
        self._stop_condition = stop_condition
        self._log_interval = log_interval
        self._summary_interval = summary_interval
        set_global_config(self.config)

    def setup(self) -> None:
        systems_initialized: list[str] = []
        for system_cls in self._systems:
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

        logger.info("Running setup...")
        self._setup_fn(self.ecs)

    def tick(self) -> dict[str, float]:
        logging.sim_time_var.set(self.simulation_time)
        durations: dict[str, float] = {}
        tick_start = time.time()

        for system in self.system_instances.values():
            update_start = time.time()
            system.update(self.simulation_time)
            durations[type(system).__name__] = time.time() - update_start

        self.simulation_time += 1
        durations["total"] = time.time() - tick_start
        return durations

    def run(self, max_ticks: int | None = None, debug_mode: bool = True) -> None:
        if debug_mode:
            tracemalloc.start()

        logging.sim_time_var.set(-1)
        logger.info("Setting up app")
        self.setup()
        logger.info("Starting loop")

        update_duration: dict[str, list[float]] = defaultdict(list)
        has_limit = max_ticks is not None and max_ticks > 0

        try:
            while not has_limit or self.simulation_time < cast(int, max_ticks):
                if self._stop_condition is not None and self._stop_condition(self):
                    break

                if self.simulation_time % self._log_interval == 0 and self.simulation_time != 0:
                    if debug_mode:
                        self._log_timings(update_duration)
                        self._log_memory()
                    update_duration = defaultdict(list)

                if self.simulation_time % self._summary_interval == 0:
                    logger.info("Simulation time: %d", self.simulation_time)

                durations = self.tick()
                for name, d in durations.items():
                    update_duration[name].append(d)
        finally:
            for system in self.system_instances.values():
                system.cleanup()

        if has_limit:
            logger.info("Simulation completed after %d ticks", self.simulation_time)
            if debug_mode:
                self._log_timings(update_duration, prefix="FINAL TIMINGS", color="green")
                self._log_memory()

    def ecs_memory_stats(self) -> tuple[int, int, float]:
        total_used = 0
        total_holes = 0
        max_fragmentation = 0.0

        containers_to_check: list[Container] = []
        containers_to_check.append(self.ecs.entities_by_id)
        for container in self.ecs.components_by_type.values():
            containers_to_check.append(container)
        containers_to_check.append(self.ecs.components_by_entity)

        for container in containers_to_check:
            total_slots = container.capacity()
            holes = container.free_slots()
            used = container.used_slots()
            total_used += used
            total_holes += holes
            if total_slots > 0:
                fragmentation = holes / total_slots
                max_fragmentation = max(max_fragmentation, fragmentation)

        return total_used, total_holes, max_fragmentation

    def _log_timings(
        self, durations: dict[str, list[float]], *, prefix: str = "TIMINGS", color: str | None = "grey"
    ) -> None:
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

    def _log_memory(self) -> None:
        try:
            try:
                import psutil

                proc = psutil.Process(os.getpid())
                rss = human_readable_bytes(proc.memory_info().rss)
            except ImportError:
                try:
                    import resource

                    rss = human_readable_bytes(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024)
                except (ImportError, AttributeError):
                    rss = "N/A"

            try:
                current, _ = tracemalloc.get_traced_memory()
                heap = human_readable_bytes(current)
            except RuntimeError:
                heap = "N/A"

            used, holes, max_frag = self.ecs_memory_stats()
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


class AppBuilder:
    _systems: list[type[System]] | None
    _setup_fn: Callable[[ECS], None] | None
    _config: RunConfiguration | None
    _stop_condition: Callable[[App], bool] | None
    _log_interval: int
    _summary_interval: int

    def __init__(self) -> None:
        self._systems = None
        self._setup_fn = None
        self._config = None
        self._stop_condition = None
        self._log_interval = 100
        self._summary_interval = 10000

    def with_systems(self, systems: list[type[System]]) -> AppBuilder:
        self._systems = systems
        return self

    def with_setup(self, fn: Callable[[ECS], None]) -> AppBuilder:
        self._setup_fn = fn
        return self

    def with_config(self, config: RunConfiguration) -> AppBuilder:
        self._config = config
        return self

    def with_stop_condition(self, fn: Callable[[App], bool]) -> AppBuilder:
        self._stop_condition = fn
        return self

    def with_log_interval(self, n: int) -> AppBuilder:
        self._log_interval = n
        return self

    def with_summary_interval(self, n: int) -> AppBuilder:
        self._summary_interval = n
        return self

    def build(self) -> App:
        if self._systems is None:
            raise ValueError("systems are required: call .with_systems()")
        if self._setup_fn is None:
            raise ValueError("setup function is required: call .with_setup()")

        return App(
            systems=self._systems,
            setup_fn=self._setup_fn,
            config=self._config or RunConfiguration.default(),
            stop_condition=self._stop_condition,
            log_interval=self._log_interval,
            summary_interval=self._summary_interval,
        )
