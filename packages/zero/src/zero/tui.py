from __future__ import annotations

import contextlib
import curses
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

from zero.simulation.components import SummarizedStatsComponent

if TYPE_CHECKING:
    from tigen.app import App

from tigen.ecs.system import System


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

    def __init__(self, sim: App):
        self.sim = sim
        self.stdscr: curses.window | None = None
        self.world_stats = WorldStats()
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
        self._last_render_time: float = 0.0
        self._refresh_interval_ms: float = 0.0

    def start(self):
        """Initialize curses and set up the screen."""
        if self._started:
            return

        # Save terminal state
        self.stdscr = curses.initscr()
        curses.noecho()
        curses.cbreak()
        with contextlib.suppress(curses.error):
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

    def update_world_stats(self):
        """Update world statistics from the simulation."""
        try:
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

            # Entity averages — read directly from ECS components (StatsComponent gets reset each tick)
            from zero.simulation.components import EnergyComponent, HungerComponent

            animal_hunger_sum, animal_energy_sum = 0.0, 0.0
            animal_eids = self.sim.ecs.entities_by_type.get(EntityTypes.ANIMAL)
            if animal_eids is not None:
                for eid in animal_eids:
                    animal_hunger_sum += self.sim.ecs.get_typed_component(eid, HungerComponent).value
                    animal_energy_sum += self.sim.ecs.get_typed_component(eid, EnergyComponent).value

            human_hunger_sum, human_energy_sum = 0.0, 0.0
            human_eids = self.sim.ecs.entities_by_type.get(EntityTypes.HUMAN)
            if human_eids is not None:
                for eid in human_eids:
                    human_hunger_sum += self.sim.ecs.get_typed_component(eid, HungerComponent).value
                    human_energy_sum += self.sim.ecs.get_typed_component(eid, EnergyComponent).value

            self.world_stats.avg_animal_hunger = animal_hunger_sum / animal_count if animal_count else 0.0
            self.world_stats.avg_human_hunger = human_hunger_sum / human_count if human_count else 0.0
            self.world_stats.avg_animal_energy = animal_energy_sum / animal_count if animal_count else 0.0
            self.world_stats.avg_human_energy = human_energy_sum / human_count if human_count else 0.0

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

        now = time.time()
        if self._last_render_time > 0:
            self._refresh_interval_ms = (now - self._last_render_time) * 1000
        self._last_render_time = now
        self.update_world_stats()

        try:
            self.stdscr.clear()
            max_y, max_x = self.stdscr.getmaxyx()

            # Layout: 70% game data (left), 30% perf data (right)
            perf_width = max(28, max_x * 30 // 100)
            game_width = max_x - perf_width - 1  # 1 col for vertical separator
            game_col = 1
            perf_col = game_width + 2  # after separator

            # Title bar
            title = f"Project Zero  ─  Tick: {tick:,}"
            with contextlib.suppress(curses.error):
                self.stdscr.addstr(0, game_col, title, curses.A_BOLD | curses.color_pair(3))

            # Draw vertical separator
            for r in range(1, max_y - 1):
                with contextlib.suppress(curses.error):
                    self.stdscr.addstr(r, game_width + 1, "│", curses.A_DIM)

            # ── Left panel: Game data ──
            row = 2
            row = self._draw_population_section(row, game_col, game_width - 1)
            row += 1
            row = self._draw_vitals_section(row, game_col, game_width - 1)
            row += 1
            row = self._draw_goals_section(row, game_col, game_width - 1)
            row += 1
            self._draw_weather_compact(row, game_col, game_width - 1)

            # ── Right panel: Perf data ──
            row_r = 2
            row_r = self._draw_perf_section(row_r, perf_col, perf_width - 1)

            # Footer
            if max_y - 1 > 0:
                self._draw_centered(max_y - 1, " [q] quit ", curses.A_DIM)

            self.stdscr.refresh()

            # Check for quit key
            try:
                key = self.stdscr.getch()
                if key == ord("q") or key == ord("Q"):
                    self._running = False
            except curses.error:
                pass

        except curses.error:
            pass

    def _safe_addstr(self, row: int, col: int, text: str, attr: int = 0, max_col: int = 0):
        """Write text clipped to max_col (or screen width) to prevent overflow."""
        if not self.stdscr:
            return
        max_y, max_x = self.stdscr.getmaxyx()
        if row >= max_y or col >= max_x:
            return
        limit = min(max_x, max_col) if max_col > 0 else max_x
        avail = limit - col
        if avail <= 0:
            return
        with contextlib.suppress(curses.error):
            self.stdscr.addstr(row, col, text[:avail], attr)

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

    def _draw_section_header(self, row: int, col: int, title: str, width: int = 0):
        """Draw a section header with a horizontal rule."""
        if not self.stdscr:
            return
        max_y, max_x = self.stdscr.getmaxyx()
        if row >= max_y:
            return
        if width == 0:
            width = max_x - col - 1
        rule_len = max(0, width - len(title) - 3)
        with contextlib.suppress(curses.error):
            self.stdscr.addstr(row, col, f"── {title} ", curses.A_BOLD | curses.color_pair(4))
            self.stdscr.addstr("─" * rule_len, curses.A_DIM | curses.color_pair(4))

    def _draw_perf_section(self, start_row: int, col: int, width: int) -> int:
        """Draw performance metrics: wall-clock, cpu-clock, per-system times."""
        if not self.stdscr:
            return start_row
        max_y, _ = self.stdscr.getmaxyx()

        row = start_row
        self._draw_section_header(row, col, "Perf", width)
        row += 1

        m = self.sim.measurements
        meta_keys = {"wall", "cpu"}

        wall_ms = m.get("wall", 0) * 1000
        cpu_ms = m.get("cpu", 0) * 1000

        if wall_ms > 0 and row < max_y:
            tps = 1000 / wall_ms
            with contextlib.suppress(curses.error):
                self.stdscr.addstr(row, col + 2, f"{'Wall:':<8} {wall_ms:.2f}ms  ({tps:.0f} ticks/sec)", curses.A_DIM)
            row += 1

        if cpu_ms > 0 and row < max_y:
            with contextlib.suppress(curses.error):
                self.stdscr.addstr(row, col + 2, f"{'CPU:':<8} {cpu_ms:.2f}ms", curses.A_DIM)
            row += 1

        if row < max_y and self._refresh_interval_ms > 0:
            with contextlib.suppress(curses.error):
                if self._refresh_interval_ms >= 1000:
                    self.stdscr.addstr(row, col + 2, f"{'Refresh:':<8} {self._refresh_interval_ms / 1000:.1f}s", curses.A_DIM)
                else:
                    self.stdscr.addstr(row, col + 2, f"{'Refresh:':<8} {self._refresh_interval_ms:.0f}ms", curses.A_DIM)
            row += 1

        # Per-system breakdown
        system_times = {k: v * 1000 for k, v in m.items() if k not in meta_keys and v > 0}
        if system_times:
            row += 1
            if row < max_y:
                self._draw_section_header(row, col, "Systems", width)
                row += 1

            total_sys_ms = sum(system_times.values())
            sorted_systems = sorted(system_times.items(), key=lambda x: x[1], reverse=True)
            for name, ms in sorted_systems:
                if row >= max_y - 1:
                    break
                short_name = name.replace("System", "")[:9]
                pct = (ms / total_sys_ms) * 100 if total_sys_ms > 0 else 0
                with contextlib.suppress(curses.error):
                    self.stdscr.addstr(row, col + 2, f"{short_name:<9} {ms:>6.2f}ms {pct:>3.0f}%", curses.A_DIM)
                row += 1

        return row

    def _draw_weather_compact(self, row: int, col: int, width: int):
        """Draw compact weather widget on the right side."""
        if not self.stdscr:
            return
        max_y, _ = self.stdscr.getmaxyx()

        self._draw_section_header(row, col, "Weather", width)

        row += 1
        if row < max_y:
            sun_pct = self.world_stats.sunny_ratio * 100
            with contextlib.suppress(curses.error):
                self.stdscr.addstr(row, col + 2, f"{'Sun:':<8} {sun_pct:.0f}%")
        row += 1
        if row < max_y:
            with contextlib.suppress(curses.error):
                self.stdscr.addstr(row, col + 2, f"{'Rain:':<8} {self.world_stats.avg_precipitation:.1f}")

    def _draw_population_section(self, start_row: int, col: int, width: int) -> int:
        """Draw population stats in the main area."""
        if not self.stdscr:
            return start_row
        max_y, _ = self.stdscr.getmaxyx()
        max_col = col + width

        row = start_row
        self._draw_section_header(row, col, "Population", width)
        row += 1

        ws = self.world_stats

        # Column headers
        if row < max_y:
            self._safe_addstr(row, col + 2, f"{'':10} {'Count':>6}  {'Net':>5}  {'Born':>5}  {'Died':>5}", curses.A_DIM, max_col)
        row += 1

        for label, count, births, deaths in [
            ("Animal", ws.animals, ws.animal_births, ws.animal_deaths),
            ("Human", ws.humans, ws.human_births, ws.human_deaths),
        ]:
            if row >= max_y:
                break
            diff = births - deaths
            diff_str = f"+{diff}" if diff >= 0 else str(diff)
            diff_color = curses.color_pair(1) if diff > 0 else (curses.color_pair(2) if diff < 0 else 0)
            # Render with color on the Net column
            prefix = f"{label:10} {count:>6}  "
            self._safe_addstr(row, col + 2, prefix, 0, max_col)
            self._safe_addstr(row, col + 2 + len(prefix), f"{diff_str:>5}", diff_color, max_col)
            suffix = f"  {births:>5}  {deaths:>5}"
            self._safe_addstr(row, col + 2 + len(prefix) + 5, suffix, 0, max_col)
            row += 1

        # Plants
        if row < max_y:
            diff = ws.plants_generated - ws.plants_consumed
            diff_str = f"+{diff:.0f}" if diff >= 0 else f"{diff:.0f}"
            diff_color = curses.color_pair(1) if diff > 0 else (curses.color_pair(2) if diff < 0 else 0)
            prefix = f"{'Plant':10} {ws.plant_biomass:>6.0f}  "
            self._safe_addstr(row, col + 2, prefix, 0, max_col)
            self._safe_addstr(row, col + 2 + len(prefix), f"{diff_str:>5}", diff_color, max_col)
            suffix = f"  {ws.plants_generated:>5.0f}  {ws.plants_consumed:>5.0f}"
            self._safe_addstr(row, col + 2 + len(prefix) + 5, suffix, 0, max_col)
        row += 1

        return row

    def _draw_vitals_section(self, start_row: int, col: int, width: int) -> int:
        """Draw entity vitals table."""
        if not self.stdscr:
            return start_row
        max_y, _ = self.stdscr.getmaxyx()
        ws = self.world_stats
        max_col = col + width

        row = start_row
        self._draw_section_header(row, col, "Vitals (Avg)", width)
        row += 1

        # Header
        if row < max_y:
            self._safe_addstr(row, col + 2, f"{'':10} {'Hunger':>8}  {'Energy':>8}", curses.A_DIM, max_col)
        row += 1

        # Animal row
        if row < max_y:
            self._safe_addstr(row, col + 2, f"{'Animal':10} {ws.avg_animal_hunger:>8.2f}  {ws.avg_animal_energy:>8.2f}", 0, max_col)
        row += 1

        # Human row
        if row < max_y:
            self._safe_addstr(row, col + 2, f"{'Human':10} {ws.avg_human_hunger:>8.2f}  {ws.avg_human_energy:>8.2f}", 0, max_col)
        row += 1

        return row

    def _draw_goals_section(self, start_row: int, col: int, width: int) -> int:
        """Draw the activity distribution section."""
        if not self.stdscr:
            return start_row
        max_y, _ = self.stdscr.getmaxyx()
        max_col = col + width

        row = start_row
        self._draw_section_header(row, col, "Activity", width)
        row += 1

        for species, goals in self.world_stats.goals.items():
            if not goals:
                continue
            if row >= max_y:
                break

            self._safe_addstr(row, col + 2, f"{species}:", curses.A_DIM, max_col)
            row += 1

            sorted_goals = sorted(goals.items(), key=lambda x: x[1], reverse=True)
            for goal, ratio in sorted_goals:
                if row >= max_y:
                    break
                if ratio > 0.01:
                    bar_width = int(ratio * 20)
                    bar = "█" * bar_width + "░" * (20 - bar_width)
                    goal_short = goal[:10] if len(goal) > 10 else goal
                    self._safe_addstr(row, col + 4, f"{goal_short:>10}  [{bar}] {ratio * 100:4.0f}%", 0, max_col)
                    row += 1

        return row

    @property
    def is_running(self) -> bool:
        """Check if the TUI is still running (user hasn't quit)."""
        return self._running


class TUIRenderSystem(System):
    """Render system that drives the TUI dashboard.

    Register with .with_render_systems([TUIRenderSystem]) and set
    .with_refresh_rate(fps) to control how often it renders.
    Handles curses lifecycle in startup/shutdown hooks.
    """

    def __init__(self):
        self.tui: TUIDisplay | None = None
        self._app: App | None = None
        self._original_log_level: int = 0

    def startup(self, app: App) -> None:
        import logging as stdlib_logging

        self._app = app
        self.tui = TUIDisplay(app)

        # Suppress normal logging in TUI mode
        zero_logger = stdlib_logging.getLogger("zero")
        self._original_log_level = zero_logger.level
        zero_logger.setLevel(stdlib_logging.CRITICAL)

        self.tui.start()

        # Disable console logging for stats in TUI mode
        try:
            summarized_stats = self.ecs.get_singleton_component(SummarizedStatsComponent)
            summarized_stats.print_to_console = False
            self.ecs.update_typed_singleton_component(summarized_stats)
        except Exception:
            pass

    def update(self, simulation_time: int) -> None:
        assert self.tui is not None
        assert self._app is not None

        self.tui.render()

        if not self.tui.is_running:
            self._app.request_stop()

    def shutdown(self) -> None:
        import logging as stdlib_logging

        if self.tui:
            self.tui.stop()

        zero_logger = stdlib_logging.getLogger("zero")
        zero_logger.setLevel(self._original_log_level)
