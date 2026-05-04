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

# Default clamp for elapsed time per frame (prevents spiral-of-death)
_MAX_FRAME_DT: float = 0.25
# Maximum fixed steps per frame to prevent stalls under load
_MAX_FIXED_STEPS_PER_FRAME: int = 10


class App:
    simulation_time: int
    ecs: ECS
    config: RunConfiguration
    system_instances: dict[type[System], System]
    measurements: dict[str, float]

    _fixed_systems: list[type[System]]
    _render_systems: list[type[System]]
    _fixed_instances: dict[type[System], System]
    _render_instances: dict[type[System], System]
    _setup_fn: Callable[[ECS], None]
    _stop_condition: Callable[[App], bool] | None
    _stop_requested: bool
    _measurements_enabled: bool
    _log_interval: int
    _summary_interval: int
    _ticks_per_second: float | None
    _refresh_rate: float | None
    _max_fixed_steps_per_frame: int

    def __init__(
        self,
        *,
        fixed_systems: list[type[System]],
        render_systems: list[type[System]] | None = None,
        setup_fn: Callable[[ECS], None],
        config: RunConfiguration,
        stop_condition: Callable[[App], bool] | None = None,
        log_interval: int = 100,
        summary_interval: int = 10000,
        ticks_per_second: float | None = None,
        refresh_rate: float | None = None,
        max_fixed_steps_per_frame: int = _MAX_FIXED_STEPS_PER_FRAME,
        measurements_enabled: bool = False,
    ) -> None:
        self.simulation_time = 0
        self.ecs = ECS(verbosity=logging.Verbosity.WARNING)
        self.config = config
        self.system_instances = {}
        self.measurements: dict[str, float] = {}
        self._fixed_systems = fixed_systems
        self._render_systems = render_systems or []
        self._fixed_instances = {}
        self._render_instances = {}
        self._setup_fn = setup_fn
        self._stop_condition = stop_condition
        self._stop_requested = False
        self._measurements_enabled = measurements_enabled
        self._log_interval = log_interval
        self._summary_interval = summary_interval
        self._ticks_per_second = ticks_per_second
        self._refresh_rate = refresh_rate
        self._max_fixed_steps_per_frame = max_fixed_steps_per_frame
        set_global_config(self.config)

    def request_stop(self) -> None:
        """Request the simulation loop to stop after the current iteration."""
        self._stop_requested = True

    @property
    def ticks_per_second(self) -> float | None:
        return self._ticks_per_second

    def set_ticks_per_second(self, tps: float) -> None:
        if tps <= 0:
            raise ValueError("ticks_per_second must be positive, got %s" % tps)
        self._ticks_per_second = tps

    def _should_stop(self) -> bool:
        if self._stop_requested:
            return True
        return self._stop_condition is not None and self._stop_condition(self)

    def setup(self) -> None:
        fixed_names: list[str] = []
        for system_cls in self._fixed_systems:
            system = system_cls()
            system.init_system(self.ecs)
            fixed_names.append(system_cls.__name__)
            self._fixed_instances[system_cls] = system
            self.system_instances[system_cls] = system

        render_names: list[str] = []
        for system_cls in self._render_systems:
            system = system_cls()
            system.init_system(self.ecs)
            render_names.append(system_cls.__name__)
            self._render_instances[system_cls] = system

        all_names = fixed_names + render_names
        logger.info(
            "Systems initialized: %s",
            colored(", ".join([s.replace("System", "") for s in all_names]), "light_magenta"),
        )
        if render_names:
            logger.info(
                "Render systems: %s",
                colored(", ".join([s.replace("System", "") for s in render_names]), "light_cyan"),
            )

        for system in self._fixed_instances.values():
            assert system.validate(), "System %s failed validation" % system.__class__.__name__
        for system in self._render_instances.values():
            assert system.validate(), "System %s failed validation" % system.__class__.__name__

        logger.info("Running setup...")
        self._setup_fn(self.ecs)

        # Call startup() on all systems — world is now fully populated
        for system in self._fixed_instances.values():
            system.startup(self)
        for system in self._render_instances.values():
            system.startup(self)

    def step(self) -> None:
        """Run one simulation step: fixed systems only, then increment.

        If measurements are enabled, per-system wall-clock durations are stored
        in self.measurements. Otherwise no timing overhead is incurred.
        """
        logging.sim_time_var.set(self.simulation_time)
        measuring = self._measurements_enabled

        if measuring:
            durations: dict[str, float] = {}
            wall_start = time.time()

        for system in self._fixed_instances.values():
            if measuring:
                t0 = time.time()
            system.update(self.simulation_time)
            if measuring:
                durations[type(system).__name__] = time.time() - t0

        if measuring:
            durations["wall"] = time.time() - wall_start
            durations["cpu"] = sum(v for k, v in durations.items() if k != "wall")
            self.measurements = durations

        self.simulation_time += 1

    def run(self, max_ticks: int | None = None, debug_mode: bool = True) -> None:
        if debug_mode:
            tracemalloc.start()

        logging.sim_time_var.set(-1)
        logger.info("Setting up app")
        self.setup()
        logger.info("Starting loop")

        if self._ticks_per_second is not None:
            self._run_paced(max_ticks, debug_mode)
        else:
            self._run_unpaced(max_ticks, debug_mode)

    def _run_unpaced(self, max_ticks: int | None, debug_mode: bool) -> None:
        """Unbounded sim loop. Fixed systems run as fast as possible.

        If render systems are registered and refresh_rate is set, render is
        gated on wall-clock time (runs at most refresh_rate times/sec).
        Otherwise render systems run every iteration.
        """
        update_duration: dict[str, list[float]] = defaultdict(list)
        has_limit = max_ticks is not None and max_ticks > 0
        has_render = len(self._render_instances) > 0
        render_interval = 1.0 / self._refresh_rate if self._refresh_rate else 0.0
        last_render_time = 0.0

        try:
            while not has_limit or self.simulation_time < cast(int, max_ticks):
                if self._should_stop():
                    break

                if self.simulation_time % self._log_interval == 0 and self.simulation_time != 0:
                    if debug_mode:
                        self._log_timings(update_duration)
                        self._log_memory()
                    update_duration = defaultdict(list)

                if self.simulation_time % self._summary_interval == 0:
                    logger.info("Simulation time: %d", self.simulation_time)

                # --- Fixed step ---
                self.step()
                if self._measurements_enabled:
                    for name, d in self.measurements.items():
                        update_duration[name].append(d)

                # --- Render (wall-clock gated if refresh_rate is set) ---
                if has_render:
                    now = time.monotonic()
                    if render_interval <= 0 or (now - last_render_time) >= render_interval:
                        for system in self._render_instances.values():
                            system.update(self.simulation_time)
                        last_render_time = now
        finally:
            self._cleanup_all()

        if has_limit:
            logger.info("Simulation completed after %d ticks", self.simulation_time)
            if debug_mode:
                self._log_timings(update_duration, prefix="FINAL TIMINGS", color="green")
                self._log_memory()

    def _run_paced(self, max_ticks: int | None, debug_mode: bool) -> None:
        """Paced loop: fixed systems run at ticks_per_second, render once per frame."""
        assert self._ticks_per_second is not None
        frame_dt = 1.0 / self._refresh_rate if self._refresh_rate else 0.0
        accumulator = 0.0
        last = time.monotonic()
        has_limit = max_ticks is not None and max_ticks > 0
        has_render = len(self._render_instances) > 0

        update_duration: dict[str, list[float]] = defaultdict(list)

        try:
            while True:
                now = time.monotonic()
                elapsed = min(now - last, _MAX_FRAME_DT)
                last = now

                # --- Fixed schedule: accumulator-driven ---
                accumulator += elapsed
                steps_this_frame = 0
                fixed_dt = 1.0 / self._ticks_per_second

                while accumulator >= fixed_dt and steps_this_frame < self._max_fixed_steps_per_frame:
                    if has_limit and self.simulation_time >= cast(int, max_ticks):
                        break
                    if self._should_stop():
                        return

                    logging.sim_time_var.set(self.simulation_time)

                    # Per-tick bookkeeping
                    if self.simulation_time % self._log_interval == 0 and self.simulation_time != 0:
                        if debug_mode:
                            self._log_timings(update_duration)
                            self._log_memory()
                        update_duration = defaultdict(list)

                    if self.simulation_time % self._summary_interval == 0:
                        logger.info("Simulation time: %d", self.simulation_time)

                    # Run fixed systems
                    measuring = self._measurements_enabled
                    if measuring:
                        wall_start = time.time()

                    for system in self._fixed_instances.values():
                        if measuring:
                            t0 = time.time()
                        system.update(self.simulation_time)
                        if measuring:
                            name = type(system).__name__
                            key = ("fixed:" + name) if has_render else name
                            update_duration[key].append(time.time() - t0)

                    if measuring:
                        wall_total = time.time() - wall_start
                        update_duration.setdefault("wall", []).append(wall_total)
                        self.measurements = {
                            k: v[-1] for k, v in update_duration.items() if v
                        }

                    self.simulation_time += 1
                    accumulator -= fixed_dt
                    steps_this_frame += 1

                # Check exit after fixed batch
                if has_limit and self.simulation_time >= cast(int, max_ticks):
                    break
                if self._should_stop():
                    break

                # --- Render schedule: once per frame ---
                for system in self._render_instances.values():
                    update_start = time.time()
                    system.update(self.simulation_time)
                    update_duration["render:" + type(system).__name__].append(
                        time.time() - update_start
                    )

                # --- Pace to target refresh rate ---
                if frame_dt > 0:
                    sleep_time = frame_dt - (time.monotonic() - now)
                    if sleep_time > 0:
                        time.sleep(sleep_time)

        finally:
            self._cleanup_all()

        if has_limit:
            logger.info("Simulation completed after %d ticks", self.simulation_time)
            if debug_mode:
                self._log_timings(update_duration, prefix="FINAL TIMINGS", color="green")
                self._log_memory()

    def _cleanup_all(self) -> None:
        for system in self._fixed_instances.values():
            system.shutdown()
        for system in self._render_instances.values():
            system.shutdown()

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
        summary = ""
        for name, d in durations.items():
            if not d:
                continue
            avg = human_readable_time_measurement(sum(d) / len(d))
            if name in ("wall", "cpu"):
                summary += "%s: %s  " % (name.capitalize(), avg)
            else:
                parts.append("%s: %s" % (name, avg))

        if summary or parts:
            message = "%s(%d):: %s%s" % (
                prefix,
                self.simulation_time,
                summary,
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
    _fixed_systems: list[type[System]] | None
    _render_systems: list[type[System]] | None
    _used_with_systems: bool
    _setup_fn: Callable[[ECS], None] | None
    _config: RunConfiguration | None
    _stop_condition: Callable[[App], bool] | None
    _log_interval: int
    _summary_interval: int
    _ticks_per_second: float | None
    _refresh_rate: float | None
    _max_fixed_steps_per_frame: int
    _measurements_enabled: bool

    def __init__(self) -> None:
        self._fixed_systems = None
        self._render_systems = None
        self._used_with_systems = False
        self._setup_fn = None
        self._config = None
        self._stop_condition = None
        self._log_interval = 100
        self._summary_interval = 10000
        self._ticks_per_second = None
        self._refresh_rate = None
        self._max_fixed_steps_per_frame = _MAX_FIXED_STEPS_PER_FRAME
        self._measurements_enabled = False

    def with_systems(self, systems: list[type[System]]) -> AppBuilder:
        """Register systems as fixed (simulation) systems.

        This is an alias for with_fixed_systems(). Cannot be combined with
        with_fixed_systems() — use one or the other.
        """
        if self._fixed_systems is not None:
            raise ValueError(
                "Cannot call both with_systems() and with_fixed_systems(). "
                "Use one or the other."
            )
        self._fixed_systems = systems
        self._used_with_systems = True
        return self

    def with_fixed_systems(self, systems: list[type[System]]) -> AppBuilder:
        """Register systems for the fixed (simulation) schedule.

        Fixed systems advance the world state and run once per simulation tick.
        Cannot be combined with with_systems() — use one or the other.
        """
        if self._used_with_systems:
            raise ValueError(
                "Cannot call both with_systems() and with_fixed_systems(). "
                "Use one or the other."
            )
        self._fixed_systems = systems
        return self

    def with_render_systems(self, systems: list[type[System]]) -> AppBuilder:
        """Register systems for the render schedule.

        Render systems observe/display world state. They run once per frame,
        after all fixed systems have completed for that frame.
        """
        self._render_systems = systems
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

    def with_ticks_per_second(self, tps: float) -> AppBuilder:
        """Set the target simulation tick rate in ticks per real second.

        When set, the run() loop uses wall-clock pacing with an accumulator
        to maintain a steady simulation rate. Fixed systems may run 0..N times
        per frame to catch up.

        When not set (default), the loop runs as fast as possible.
        """
        if tps <= 0:
            raise ValueError("ticks_per_second must be positive, got %s" % tps)
        self._ticks_per_second = tps
        return self

    def with_refresh_rate(self, fps: float) -> AppBuilder:
        """Set the target frame rate for render systems in frames per second.

        Controls how often render systems run. Works in both modes:
        - Without ticks_per_second: sim runs unbounded, render is wall-clock gated.
        - With ticks_per_second: full paced mode with accumulator and frame sleep.

        When not set, render systems run every iteration.
        """
        if fps <= 0:
            raise ValueError("refresh_rate must be positive, got %s" % fps)
        self._refresh_rate = fps
        return self

    def with_max_fixed_steps_per_frame(self, n: int) -> AppBuilder:
        """Set the max fixed steps allowed in one frame.

        Higher values let debug/fast-forward modes catch up at high tick rates.
        Lower values protect interactive apps from long stalls when fixed systems
        get expensive.
        """
        if n <= 0:
            raise ValueError("max_fixed_steps_per_frame must be positive, got %s" % n)
        self._max_fixed_steps_per_frame = n
        return self

    def with_measurements(self) -> AppBuilder:
        """Enable per-system timing measurements.

        When enabled, each step() records per-system wall-clock durations in
        app.measurements. Useful for profiling and TUI display.
        When not enabled (default), no timing overhead is incurred.
        """
        self._measurements_enabled = True
        return self

    def build(self) -> App:
        if self._fixed_systems is None:
            raise ValueError("Fixed systems are required: call .with_systems() or .with_fixed_systems()")
        if self._setup_fn is None:
            raise ValueError("setup function is required: call .with_setup()")

        return App(
            fixed_systems=self._fixed_systems,
            render_systems=self._render_systems,
            setup_fn=self._setup_fn,
            config=self._config or RunConfiguration.default(),
            stop_condition=self._stop_condition,
            log_interval=self._log_interval,
            summary_interval=self._summary_interval,
            ticks_per_second=self._ticks_per_second,
            refresh_rate=self._refresh_rate,
            max_fixed_steps_per_frame=self._max_fixed_steps_per_frame,
            measurements_enabled=self._measurements_enabled,
        )
