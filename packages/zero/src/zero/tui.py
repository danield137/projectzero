"""
TUI (Text User Interface) dashboard for the simulation.
Displays a clean, non-scrolling dashboard with performance and world stats.
"""

from __future__ import annotations

import contextlib
import curses
import os
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

from zero.simulation.components import StatsComponent, SummarizedStatsComponent
from zero.simulation.functional import stat_ops

if TYPE_CHECKING:
    from zero import Simulation


@dataclass
class PerformanceStats:
    """Stores performance metrics for the TUI."""

    tick: int = 0
    total_time_ms: float = 0.0
    system_times: dict[str, float] = field(default_factory=dict[str, float])
    rss_mb: float = 0.0
    heap_mb: float = 0.0
    ecs_used: int = 0
    ecs_holes: int = 0
    ecs_fragmentation: float = 0.0


@dataclass
class WorldStats:
    """Stores world statistics for the TUI."""

    # Population
    animals: int = 0
    humans: int = 0
    plant_biomass: float = 0.0

    # Births/Deaths in reporting period
    animal_births: int = 0
    human_births: int = 0
    animal_deaths: int = 0
    human_deaths: int = 0

    # Plant stats
    plants_generated: float = 0.0
    plants_consumed: float = 0.0

    # Weather
    sunny_ratio: float = 0.0
    avg_precipitation: float = 0.0

    # Entity averages
    avg_animal_hunger: float = 0.0
    avg_human_hunger: float = 0.0
    avg_animal_energy: float = 0.0
    avg_human_energy: float = 0.0

    # Goals distribution per species
    goals: dict[str, dict[str, float]] = field(default_factory=dict[str, dict[str, float]])

    # Deaths distribution per species
    deaths_causes: dict[str, dict[str, float]] = field(default_factory=dict[str, dict[str, float]])


class TUIDisplay:
    """A curses-based TUI dashboard for the simulation."""

    def __init__(self, sim: Simulation, update_interval: int = 100):
        self.sim = sim
        self.update_interval = update_interval
        self.stdscr: curses.window | None = None
        self.perf_stats = PerformanceStats()
        self.world_stats = WorldStats()
        self.last_render_tick = -1
        self._running = True
        self._started = False
        # Track previous values for delta calculations
        self._prev_animals = 0
        self._prev_humans = 0
        self._prev_plant_biomass = 0.0
        # Track cumulative births/deaths to calculate deltas
        self._prev_animal_births_sum = 0
        self._prev_animal_deaths_sum = 0
        self._prev_human_births_sum = 0
        self._prev_human_deaths_sum = 0
        self._prev_plants_generated_sum = 0.0
        self._prev_plants_consumed_sum = 0.0

    def start(self):
        """Initialize curses and set up the screen."""
        if self._started:
            return

        # Save terminal state
        self.stdscr = curses.initscr()
        curses.noecho()
        curses.cbreak()
        curses.curs_set(0)  # Hide cursor
        self.stdscr.keypad(True)
        self.stdscr.nodelay(True)  # Non-blocking input

        # Initialize colors if available
        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_GREEN, -1)  # Good/positive
            curses.init_pair(2, curses.COLOR_RED, -1)  # Bad/negative
            curses.init_pair(3, curses.COLOR_YELLOW, -1)  # Warning/neutral
            curses.init_pair(4, curses.COLOR_CYAN, -1)  # Headers
            curses.init_pair(5, curses.COLOR_MAGENTA, -1)  # Highlights

        self._started = True

    def stop(self):
        """Clean up curses and restore terminal."""
        if not self._started:
            return

        if self.stdscr:
            self.stdscr.keypad(False)
        curses.nocbreak()
        curses.echo()
        curses.endwin()
        self._started = False

    def update_performance_stats(
        self,
        tick: int,
        durations: dict[str, list[float]],
        rss_mb: float = 0.0,
        heap_mb: float = 0.0,
        ecs_used: int = 0,
        ecs_holes: int = 0,
        ecs_fragmentation: float = 0.0,
    ):
        """Update performance statistics."""
        self.perf_stats.tick = tick

        # Calculate average times in ms
        if "total" in durations and durations["total"]:
            self.perf_stats.total_time_ms = (sum(durations["total"]) / len(durations["total"])) * 1000

        self.perf_stats.system_times = {}
        for name, times in durations.items():
            if name != "total" and times:
                self.perf_stats.system_times[name] = (sum(times) / len(times)) * 1000

        self.perf_stats.rss_mb = rss_mb
        self.perf_stats.heap_mb = heap_mb
        self.perf_stats.ecs_used = ecs_used
        self.perf_stats.ecs_holes = ecs_holes
        self.perf_stats.ecs_fragmentation = ecs_fragmentation

    def update_world_stats(self):
        """Update world statistics from the simulation."""
        try:
            unified_stats = self.sim.ecs.get_singleton_component(StatsComponent)
            summarized_stats = self.sim.ecs.get_singleton_component(SummarizedStatsComponent)

            # Count living entities directly from ECS (population in StatsComponent gets reset)
            animal_count = 0
            human_count = 0
            from zero.simulation.entities import EntityTypes

            if EntityTypes.ANIMAL in self.sim.ecs.entities_by_type:
                animal_count = len(self.sim.ecs.entities_by_type[EntityTypes.ANIMAL])
            if EntityTypes.HUMAN in self.sim.ecs.entities_by_type:
                human_count = len(self.sim.ecs.entities_by_type[EntityTypes.HUMAN])

            self.world_stats.animals = animal_count
            self.world_stats.humans = human_count
            self.world_stats.plant_biomass = summarized_stats.plant_biomass[-1] if summarized_stats.plant_biomass else 0

            # Get cumulative births/deaths from summarized stats
            curr_animal_births = sum(summarized_stats.births.get("Animal", []))
            curr_animal_deaths = sum(summarized_stats.deaths.get("Animal", []))
            curr_human_births = sum(summarized_stats.births.get("Human", []))
            curr_human_deaths = sum(summarized_stats.deaths.get("Human", []))
            curr_plants_generated = sum(summarized_stats.plants_generated)
            curr_plants_consumed = sum(summarized_stats.plants_consumed)

            # Calculate deltas since last TUI update
            self.world_stats.animal_births = curr_animal_births - self._prev_animal_births_sum
            self.world_stats.animal_deaths = curr_animal_deaths - self._prev_animal_deaths_sum
            self.world_stats.human_births = curr_human_births - self._prev_human_births_sum
            self.world_stats.human_deaths = curr_human_deaths - self._prev_human_deaths_sum
            self.world_stats.plants_generated = curr_plants_generated - self._prev_plants_generated_sum
            self.world_stats.plants_consumed = curr_plants_consumed - self._prev_plants_consumed_sum

            # Handle stats reset (when cumulative goes down, the stats were reset)
            if self.world_stats.animal_births < 0:
                self.world_stats.animal_births = curr_animal_births
            if self.world_stats.animal_deaths < 0:
                self.world_stats.animal_deaths = curr_animal_deaths
            if self.world_stats.human_births < 0:
                self.world_stats.human_births = curr_human_births
            if self.world_stats.human_deaths < 0:
                self.world_stats.human_deaths = curr_human_deaths
            if self.world_stats.plants_generated < 0:
                self.world_stats.plants_generated = curr_plants_generated
            if self.world_stats.plants_consumed < 0:
                self.world_stats.plants_consumed = curr_plants_consumed

            # Update previous cumulative sums
            self._prev_animal_births_sum = curr_animal_births
            self._prev_animal_deaths_sum = curr_animal_deaths
            self._prev_human_births_sum = curr_human_births
            self._prev_human_deaths_sum = curr_human_deaths
            self._prev_plants_generated_sum = curr_plants_generated
            self._prev_plants_consumed_sum = curr_plants_consumed

            # Weather
            self.world_stats.sunny_ratio = (
                sum(summarized_stats.sunny) / len(summarized_stats.sunny) if summarized_stats.sunny else 0
            )
            self.world_stats.avg_precipitation = (
                float(np.mean(summarized_stats.precipitation)) if summarized_stats.precipitation else 0
            )

            # Entity averages
            self.world_stats.avg_animal_hunger = stat_ops.avg_hunger(unified_stats, "Animal")
            self.world_stats.avg_human_hunger = stat_ops.avg_hunger(unified_stats, "Human")
            self.world_stats.avg_animal_energy = stat_ops.avg_energy(unified_stats, "Animal")
            self.world_stats.avg_human_energy = stat_ops.avg_energy(unified_stats, "Human")

            # Goals distribution
            self.world_stats.goals = {}
            for sp, sp_goals in summarized_stats.goal_distribution.items():
                self.world_stats.goals[sp] = {}
                for goal, values in sp_goals.items():
                    if values:
                        self.world_stats.goals[sp][goal] = float(np.mean(values))

            # Deaths distribution
            self.world_stats.deaths_causes = {}
            for sp, sp_deaths in summarized_stats.deaths_distribution.items():
                self.world_stats.deaths_causes[sp] = {}
                for cause, values in sp_deaths.items():
                    if values:
                        self.world_stats.deaths_causes[sp][cause] = float(np.mean(values))

        except Exception:
            # Stats might not be available yet
            pass

    def render(self):
        """Render the TUI dashboard."""
        if not self._started or not self.stdscr:
            return

        tick = self.sim.simulation_time

        # Only render every update_interval ticks
        if tick - self.last_render_tick < self.update_interval and self.last_render_tick >= 0:
            return

        self.last_render_tick = tick
        self.update_world_stats()

        try:
            self.stdscr.clear()
            max_y, max_x = self.stdscr.getmaxyx()

            row = 0

            # Title
            title = f" Project Zero - Simulation Dashboard (Tick: {tick:,}) "
            self._draw_centered(row, title, curses.A_BOLD | curses.color_pair(4))
            row += 2

            # Performance Section
            row = self._draw_performance_section(row, max_x)
            row += 1

            # World Stats Section
            row = self._draw_world_stats_section(row, max_x)
            row += 1

            # Goals Section
            row = self._draw_goals_section(row, max_x)
            row += 1

            # Footer
            if row < max_y - 1:
                self._draw_centered(max_y - 1, " Press 'q' to quit ", curses.A_DIM)

            self.stdscr.refresh()

            # Check for quit key
            try:
                key = self.stdscr.getch()
                if key == ord("q") or key == ord("Q"):
                    self._running = False
            except curses.error:
                pass

        except curses.error:
            # Terminal too small or other curses error
            pass

    def _draw_centered(self, row: int, text: str, attr: int = 0):
        """Draw text centered on the screen."""
        if not self.stdscr:
            return
        max_y, max_x = self.stdscr.getmaxyx()
        if row >= max_y:
            return
        col = max(0, (max_x - len(text)) // 2)
        with contextlib.suppress(curses.error):
            self.stdscr.addstr(row, col, text[: max_x - col], attr)

    def _draw_box(self, row: int, col: int, width: int, height: int, title: str = ""):
        """Draw a box with optional title."""
        if not self.stdscr:
            return
        max_y, max_x = self.stdscr.getmaxyx()

        for r in range(row, min(row + height, max_y)):
            for c in range(col, min(col + width, max_x)):
                try:
                    if r == row or r == row + height - 1:
                        if c == col:
                            self.stdscr.addch(r, c, curses.ACS_ULCORNER if r == row else curses.ACS_LLCORNER)
                        elif c == col + width - 1:
                            self.stdscr.addch(r, c, curses.ACS_URCORNER if r == row else curses.ACS_LRCORNER)
                        else:
                            self.stdscr.addch(r, c, curses.ACS_HLINE)
                    elif c == col or c == col + width - 1:
                        self.stdscr.addch(r, c, curses.ACS_VLINE)
                except curses.error:
                    pass

        if title and row < max_y:
            with contextlib.suppress(curses.error):
                self.stdscr.addstr(row, col + 2, f" {title} ", curses.A_BOLD | curses.color_pair(4))

    def _draw_performance_section(self, start_row: int, max_x: int) -> int:
        """Draw the performance section."""
        if not self.stdscr:
            return start_row
        max_y, _ = self.stdscr.getmaxyx()

        row = start_row
        with contextlib.suppress(curses.error):
            self.stdscr.addstr(row, 2, "═══ PERFORMANCE ═══", curses.A_BOLD | curses.color_pair(4))
        row += 1

        # Timing info
        if row < max_y:
            try:
                total_ms = self.perf_stats.total_time_ms
                tps = 1000 / total_ms if total_ms > 0 else 0
                self.stdscr.addstr(row, 4, f"Tick Time: {total_ms:.2f}ms ({tps:.0f} ticks/sec)")
            except curses.error:
                pass
        row += 1

        # Memory info
        if row < max_y:
            with contextlib.suppress(curses.error):
                self.stdscr.addstr(
                    row, 4, f"Memory: RSS={self.perf_stats.rss_mb:.1f}MB, Heap={self.perf_stats.heap_mb:.1f}MB"
                )
        row += 1

        # ECS info
        if row < max_y:
            try:
                frag_pct = self.perf_stats.ecs_fragmentation * 100
                self.stdscr.addstr(
                    row,
                    4,
                    f"ECS: Used={self.perf_stats.ecs_used}, Holes={self.perf_stats.ecs_holes}, Frag={frag_pct:.0f}%",
                )
            except curses.error:
                pass
        row += 1

        # System breakdown (top 5)
        if self.perf_stats.system_times:
            sorted_systems = sorted(self.perf_stats.system_times.items(), key=lambda x: x[1], reverse=True)[:5]

            if row < max_y:
                with contextlib.suppress(curses.error):
                    self.stdscr.addstr(row, 4, "Top Systems:", curses.A_DIM)
            row += 1

            for name, ms in sorted_systems:
                if row >= max_y:
                    break
                try:
                    short_name = name.replace("System", "")
                    self.stdscr.addstr(row, 6, f"{short_name}: {ms:.2f}ms")
                except curses.error:
                    pass
                row += 1

        return row

    def _draw_world_stats_section(self, start_row: int, max_x: int) -> int:
        """Draw the world statistics section."""
        if not self.stdscr:
            return start_row
        max_y, _ = self.stdscr.getmaxyx()

        row = start_row
        with contextlib.suppress(curses.error):
            self.stdscr.addstr(row, 2, "═══ WORLD STATS ═══", curses.A_BOLD | curses.color_pair(4))
        row += 1

        # Population
        if row < max_y:
            with contextlib.suppress(curses.error):
                self.stdscr.addstr(row, 4, "Population:", curses.A_UNDERLINE)
        row += 1

        ws = self.world_stats

        if row < max_y:
            try:
                animal_diff = ws.animal_births - ws.animal_deaths
                diff_str = f"+{animal_diff}" if animal_diff >= 0 else str(animal_diff)
                diff_color = (
                    curses.color_pair(1) if animal_diff > 0 else (curses.color_pair(2) if animal_diff < 0 else 0)
                )
                self.stdscr.addstr(row, 6, f"Animals: {ws.animals} (")
                self.stdscr.addstr(f"{diff_str}", diff_color)
                self.stdscr.addstr(f") [+{ws.animal_births}/-{ws.animal_deaths}]")
            except curses.error:
                pass
        row += 1

        if row < max_y:
            try:
                human_diff = ws.human_births - ws.human_deaths
                diff_str = f"+{human_diff}" if human_diff >= 0 else str(human_diff)
                diff_color = curses.color_pair(1) if human_diff > 0 else (curses.color_pair(2) if human_diff < 0 else 0)
                self.stdscr.addstr(row, 6, f"Humans:  {ws.humans} (")
                self.stdscr.addstr(f"{diff_str}", diff_color)
                self.stdscr.addstr(f") [+{ws.human_births}/-{ws.human_deaths}]")
            except curses.error:
                pass
        row += 1

        if row < max_y:
            try:
                plant_diff = ws.plants_generated - ws.plants_consumed
                diff_str = f"+{plant_diff:.1f}" if plant_diff >= 0 else f"{plant_diff:.1f}"
                diff_color = curses.color_pair(1) if plant_diff > 0 else (curses.color_pair(2) if plant_diff < 0 else 0)
                self.stdscr.addstr(row, 6, f"Plants:  {ws.plant_biomass:.1f} (")
                self.stdscr.addstr(f"{diff_str}", diff_color)
                self.stdscr.addstr(f") [+{ws.plants_generated:.1f}/-{ws.plants_consumed:.1f}]")
            except curses.error:
                pass
        row += 2

        # Entity Stats
        if row < max_y:
            with contextlib.suppress(curses.error):
                self.stdscr.addstr(row, 4, "Entity Averages:", curses.A_UNDERLINE)
        row += 1

        if row < max_y:
            with contextlib.suppress(curses.error):
                self.stdscr.addstr(
                    row, 6, f"Hunger:  Animal={ws.avg_animal_hunger:.2f}  Human={ws.avg_human_hunger:.2f}"
                )
        row += 1

        if row < max_y:
            with contextlib.suppress(curses.error):
                self.stdscr.addstr(
                    row, 6, f"Energy:  Animal={ws.avg_animal_energy:.2f}  Human={ws.avg_human_energy:.2f}"
                )
        row += 2

        # Weather
        if row < max_y:
            with contextlib.suppress(curses.error):
                self.stdscr.addstr(row, 4, "Weather:", curses.A_UNDERLINE)
        row += 1

        if row < max_y:
            try:
                sun_pct = ws.sunny_ratio * 100
                self.stdscr.addstr(row, 6, f"Sunny: {sun_pct:.0f}%  Rain: {ws.avg_precipitation:.1f}")
            except curses.error:
                pass
        row += 1

        return row

    def _draw_goals_section(self, start_row: int, max_x: int) -> int:
        """Draw the goals distribution section."""
        if not self.stdscr:
            return start_row
        max_y, _ = self.stdscr.getmaxyx()

        row = start_row
        with contextlib.suppress(curses.error):
            self.stdscr.addstr(row, 2, "═══ ACTIVITY DISTRIBUTION ═══", curses.A_BOLD | curses.color_pair(4))
        row += 1

        for species, goals in self.world_stats.goals.items():
            if not goals:
                continue
            if row >= max_y:
                break

            with contextlib.suppress(curses.error):
                self.stdscr.addstr(row, 4, f"{species}:", curses.A_UNDERLINE)
            row += 1

            # Sort goals by value
            sorted_goals = sorted(goals.items(), key=lambda x: x[1], reverse=True)
            for goal, ratio in sorted_goals:
                if row >= max_y:
                    break
                if ratio > 0.01:  # Only show if > 1%
                    try:
                        bar_width = int(ratio * 20)
                        bar = "█" * bar_width + "░" * (20 - bar_width)
                        goal_short = goal[:10] if len(goal) > 10 else goal
                        self.stdscr.addstr(row, 6, f"{goal_short:>10}: [{bar}] {ratio * 100:5.1f}%")
                    except curses.error:
                        pass
                    row += 1

        return row

    @property
    def is_running(self) -> bool:
        """Check if the TUI is still running (user hasn't quit)."""
        return self._running


def run_with_tui(
    sim: Simulation,
    max_ticks: int | None = None,
    debug_mode: bool = True,
    update_interval: int = 100,
    delay: float = 0.0,
):
    """Run the simulation with TUI display.

    Args:
        sim: The simulation instance
        max_ticks: Maximum number of ticks to run (None for unlimited)
        debug_mode: Whether to enable debug mode (memory tracking)
        update_interval: How often to update the TUI display (in ticks)
        delay: Seconds to sleep between ticks (not counted in perf metrics)
    """
    import logging as stdlib_logging
    import tracemalloc
    from collections import defaultdict

    from simz.common import logging
    from zero.simulation.components import SummarizedStatsComponent

    tui = TUIDisplay(sim, update_interval=update_interval)

    # Suppress normal logging in TUI mode
    zero_logger = stdlib_logging.getLogger("zero")
    original_level = zero_logger.level
    zero_logger.setLevel(stdlib_logging.CRITICAL)

    try:
        tui.start()

        if debug_mode:
            tracemalloc.start()

        logging.sim_time_var.set(-1)
        sim.setup_simulation()
        sim.set_starting_conditions()

        # Disable console logging for stats in TUI mode
        try:
            summarized_stats = sim.ecs.get_singleton_component(SummarizedStatsComponent)
            summarized_stats.print_to_console = False
            sim.ecs.update_typed_singleton_component(summarized_stats)
        except Exception:
            pass

        update_duration: dict[str, list[float]] = defaultdict(list)
        has_limit = max_ticks is not None and max_ticks > 0

        while tui.is_running and (not has_limit or sim.simulation_time < (max_ticks or 0)):
            tick_start = time.time()
            logging.sim_time_var.set(sim.simulation_time)

            # Update stats every interval
            if sim.simulation_time % update_interval == 0 and sim.simulation_time != 0:
                if debug_mode:
                    # Get memory stats
                    rss_mb = 0.0
                    heap_mb = 0.0
                    try:
                        import psutil

                        proc = psutil.Process(os.getpid())
                        rss_mb = proc.memory_info().rss / (1024 * 1024)
                    except Exception:
                        pass

                    try:
                        current, _peak = tracemalloc.get_traced_memory()
                        heap_mb = current / (1024 * 1024)
                    except Exception:
                        pass

                    # Get ECS stats
                    ecs_used, ecs_holes, ecs_frag = sim._ecs_memory_stats()

                    tui.update_performance_stats(
                        sim.simulation_time,
                        update_duration,
                        rss_mb=rss_mb,
                        heap_mb=heap_mb,
                        ecs_used=ecs_used,
                        ecs_holes=ecs_holes,
                        ecs_fragmentation=ecs_frag,
                    )

                update_duration = defaultdict(list)

            # Run systems
            for system in sim.system_instances.values():
                update_start = time.time()
                system.update(sim.simulation_time)
                update_duration[type(system).__name__].append(time.time() - update_start)

            # Render TUI
            tui.render()

            sim.simulation_time += 1
            update_duration["total"].append(time.time() - tick_start)

            # Sleep after recording perf metrics so delay doesn't affect timing
            if delay > 0:
                time.sleep(delay)

    finally:
        tui.stop()
        # Restore logger level
        zero_logger.setLevel(original_level)

    return sim.simulation_time
