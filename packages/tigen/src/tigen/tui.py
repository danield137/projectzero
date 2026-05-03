"""Configurable TUI dashboard framework for tigen.

Provides a declarative API for building curses-based dashboards that render
as part of the engine's render schedule.

Example usage:

    from tigen.tui import TUIDashboard, Panel, Metric, Table, BarGroup, Bar

    dashboard = TUIDashboard(
        title="My Simulation",
        context=lambda app: {"pop": count_entities(app.ecs)},
        panels=[
            Panel("Stats", [
                Metric("Population", lambda ctx: ctx["pop"]),
            ]),
        ],
    )

    AppBuilder()
        .with_fixed_systems([...])
        .with_render_systems([dashboard.create_render_system()])
        .with_refresh_rate(10)
        .with_measurements()
        .build()
"""

from __future__ import annotations

import contextlib
import curses
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from tigen.ecs.system import System

if TYPE_CHECKING:
    from tigen.app import App
    from tigen.ecs.core import ECS


# ---------------------------------------------------------------------------
# Widget types
# ---------------------------------------------------------------------------


@dataclass
class Metric:
    """Single labeled value. fn receives the context dict, returns displayable value."""

    label: str
    fn: Callable[[dict[str, Any]], Any]
    fmt: str = ""

    def format_value(self, ctx: dict[str, Any]) -> str:
        val = self.fn(ctx)
        if self.fmt:
            return format(val, self.fmt)
        if isinstance(val, float):
            return f"{val:.2f}"
        return str(val)


@dataclass
class Bar:
    """A single bar in a bar chart."""

    label: str
    ratio: float  # 0.0 to 1.0


@dataclass
class BarGroup:
    """A named group of bars."""

    label: str
    bars: list[Bar]


@dataclass
class BarChart:
    """Horizontal bar chart widget. fn returns list of BarGroups."""

    fn: Callable[[dict[str, Any]], list[BarGroup]]
    bar_width: int = 20


@dataclass
class Table:
    """Aligned columnar table. fn returns list of rows (list of strings)."""

    headers: list[str]
    fn: Callable[[dict[str, Any]], list[list[str]]]


@dataclass
class TextBlock:
    """Custom text widget. fn returns pre-rendered lines for the available width.

    Use for domain-specific displays (ASCII maps, event logs, card grids, etc.)
    without exposing curses to user code.
    """

    fn: Callable[[dict[str, Any], int], list[str]]


# Widget union type
Widget = Metric | BarChart | Table | TextBlock


@dataclass
class Panel:
    """A named group of widgets rendered with a section header."""

    title: str
    widgets: list[Widget]


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


def _default_context(ecs: ECS) -> dict[str, Any]:
    return {}


@dataclass
class TUIDashboard:
    """Configurable TUI dashboard.

    Args:
        title: Dashboard title shown in the header bar.
        panels: List of panels to display in the game-data area.
        context: Callable that produces a context dict from the ECS each frame.
                 All widget fns receive this dict instead of raw ECS.
        perf_panel: Whether to auto-show a perf panel when measurements are
                    enabled. Defaults to True.
        perf_details: Whether to show detailed rolling stats (avg, p95, peak)
                     next to perf counters. Defaults to False.
    """

    title: str
    panels: list[Panel]
    context: Callable[[ECS], dict[str, Any]] = field(default_factory=lambda: _default_context)
    perf_panel: bool = True
    perf_details: bool = False

    def create_render_system(self) -> type[System]:
        """Create a System class that renders this dashboard."""
        dashboard = self

        class _DashboardRenderSystem(System):
            def __init__(self) -> None:
                self._dashboard_renderer: _DashboardRenderer | None = None
                self._app: App | None = None

            def startup(self, app: App) -> None:
                self._app = app
                self._dashboard_renderer = _DashboardRenderer(
                    dashboard, target_fps=app._refresh_rate, perf_details=dashboard.perf_details
                )
                self._dashboard_renderer.start()

            def update(self, simulation_time: int) -> None:
                assert self._dashboard_renderer is not None
                assert self._app is not None

                ctx = dashboard.context(self.ecs)
                self._dashboard_renderer.render(
                    simulation_time=self._app.simulation_time,
                    measurements=self._app.measurements,
                    ctx=ctx,
                )

                if not self._dashboard_renderer.is_running:
                    self._app.request_stop()

            def shutdown(self) -> None:
                if self._dashboard_renderer:
                    self._dashboard_renderer.stop()

        _DashboardRenderSystem.__name__ = "TUIDashboardSystem"
        _DashboardRenderSystem.__qualname__ = "TUIDashboardSystem"
        return _DashboardRenderSystem


# ---------------------------------------------------------------------------
# Renderer (curses internals)
# ---------------------------------------------------------------------------


class _DashboardRenderer:
    """Manages curses lifecycle and rendering for a TUIDashboard."""

    def __init__(self, dashboard: TUIDashboard, target_fps: float | None = None, perf_details: bool = False) -> None:
        self.dashboard = dashboard
        self.target_fps = target_fps
        self.perf_details = perf_details
        self.stdscr: curses.window | None = None
        self._running = True
        self._started = False
        self._last_render_time: float = 0.0
        self._refresh_interval_ms: float = 0.0
        self._histories: dict[str, list[float]] = {}
        self._history_max: int = 200

    def start(self) -> None:
        if self._started:
            return
        self.stdscr = curses.initscr()
        curses.noecho()
        curses.cbreak()
        with contextlib.suppress(curses.error):
            curses.curs_set(0)
        self.stdscr.keypad(True)
        self.stdscr.nodelay(True)
        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_GREEN, -1)
            curses.init_pair(2, curses.COLOR_RED, -1)
            curses.init_pair(3, curses.COLOR_YELLOW, -1)
            curses.init_pair(4, curses.COLOR_CYAN, -1)
            curses.init_pair(5, curses.COLOR_MAGENTA, -1)
        self._started = True

    def stop(self) -> None:
        if not self._started:
            return
        if self.stdscr:
            self.stdscr.keypad(False)
        curses.nocbreak()
        curses.echo()
        curses.endwin()
        self._started = False

    @property
    def is_running(self) -> bool:
        return self._running

    def render(self, simulation_time: int, measurements: dict[str, float], ctx: dict[str, Any]) -> None:
        if not self._started or not self.stdscr:
            return

        now = time.time()
        if self._last_render_time > 0:
            self._refresh_interval_ms = (now - self._last_render_time) * 1000
        self._last_render_time = now

        try:
            self.stdscr.clear()
            max_y, max_x = self.stdscr.getmaxyx()

            # Layout: game panels left, perf right, vertical separator
            perf_width = max(28, max_x * 30 // 100)
            game_width = max_x - perf_width - 1
            game_col = 1
            perf_col = game_width + 2

            # Title
            title = f"{self.dashboard.title}  ─  Tick: {simulation_time:,}"
            with contextlib.suppress(curses.error):
                self.stdscr.addstr(0, game_col, title, curses.A_BOLD | curses.color_pair(3))

            # Vertical separator
            for r in range(1, max_y - 1):
                with contextlib.suppress(curses.error):
                    self.stdscr.addstr(r, game_width + 1, "│", curses.A_DIM)

            # Game panels
            row = 2
            for panel in self.dashboard.panels:
                if row >= max_y - 2:
                    break
                row = self._draw_panel(panel, ctx, row, game_col, game_width - 1)
                row += 2  # spacing between panels

            # Perf panel (auto)
            if self.dashboard.perf_panel and measurements:
                self._draw_perf(measurements, 2, perf_col, perf_width - 1)

            # Footer
            if max_y - 1 > 0:
                footer = " [q] quit "
                footer_col = max(0, (max_x - len(footer)) // 2)
                with contextlib.suppress(curses.error):
                    self.stdscr.addstr(max_y - 1, footer_col, footer, curses.A_DIM)

            self.stdscr.refresh()

            # Quit key
            try:
                key = self.stdscr.getch()
                if key in (ord("q"), ord("Q")):
                    self._running = False
            except curses.error:
                pass

        except curses.error:
            pass

    # -- Panel / widget rendering ------------------------------------------

    def _draw_panel(self, panel: Panel, ctx: dict[str, Any], start_row: int, col: int, width: int) -> int:
        if not self.stdscr:
            return start_row
        max_y, _ = self.stdscr.getmaxyx()

        row = start_row
        self._draw_header(row, col, panel.title, width)
        row += 1

        for widget in panel.widgets:
            if row >= max_y - 2:
                break
            if isinstance(widget, Metric):
                row = self._draw_metric(widget, ctx, row, col, width)
            elif isinstance(widget, Table):
                row = self._draw_table(widget, ctx, row, col, width)
            elif isinstance(widget, BarChart):
                row = self._draw_barchart(widget, ctx, row, col, width)
            elif isinstance(widget, TextBlock):
                row = self._draw_text_block(widget, ctx, row, col, width)

        return row

    def _draw_metric(self, metric: Metric, ctx: dict[str, Any], row: int, col: int, width: int) -> int:
        if not self.stdscr:
            return row
        max_y, _ = self.stdscr.getmaxyx()
        if row >= max_y:
            return row
        try:
            val = metric.format_value(ctx)
        except Exception:
            val = "?"
        with contextlib.suppress(curses.error):
            self.stdscr.addstr(row, col + 2, f"{metric.label + ':':<12} {val}", curses.A_DIM)
        return row + 1

    def _draw_table(self, table: Table, ctx: dict[str, Any], row: int, col: int, width: int) -> int:
        if not self.stdscr:
            return row
        max_y, _ = self.stdscr.getmaxyx()
        max_col = col + width

        # Headers
        if row < max_y:
            header_str = "    ".join(f"{h:>8}" for h in table.headers)
            self._safe_addstr(row, col + 2, header_str, curses.A_DIM, max_col)
            row += 1

        # Rows
        try:
            rows = table.fn(ctx)
        except Exception:
            rows = []
        for cells in rows:
            if row >= max_y - 1:
                break
            row_str = "    ".join(f"{c:>8}" for c in cells)
            self._safe_addstr(row, col + 2, row_str, 0, max_col)
            row += 1

        return row

    def _draw_barchart(self, chart: BarChart, ctx: dict[str, Any], row: int, col: int, width: int) -> int:
        if not self.stdscr:
            return row
        max_y, _ = self.stdscr.getmaxyx()
        max_col = col + width

        try:
            groups = chart.fn(ctx)
        except Exception:
            groups = []

        for group in groups:
            if row >= max_y - 1:
                break
            self._safe_addstr(row, col + 2, f"{group.label}:", curses.A_DIM, max_col)
            row += 1
            for bar in group.bars:
                if row >= max_y - 1:
                    break
                filled = int(bar.ratio * chart.bar_width)
                empty = chart.bar_width - filled
                bar_str = "█" * filled + "░" * empty
                label = bar.label[:10]
                self._safe_addstr(row, col + 4, f"{label:>10}  [{bar_str}] {bar.ratio * 100:4.0f}%", 0, max_col)
                row += 1

        return row

    def _draw_text_block(self, widget: TextBlock, ctx: dict[str, Any], row: int, col: int, width: int) -> int:
        if not self.stdscr:
            return row
        max_y, _ = self.stdscr.getmaxyx()
        max_col = col + width

        try:
            lines = widget.fn(ctx, width - 2)
        except Exception:
            lines = ["?"]

        for line in lines:
            if row >= max_y - 1:
                break
            self._safe_addstr(row, col + 2, line, 0, max_col)
            row += 1

        return row

    # -- Perf panel --------------------------------------------------------

    def _draw_perf(self, measurements: dict[str, float], start_row: int, col: int, width: int) -> int:
        if not self.stdscr:
            return start_row
        max_y, _ = self.stdscr.getmaxyx()
        meta_keys = {"wall", "cpu"}
        details = self.perf_details

        row = start_row
        self._draw_header(row, col, "Perf", width)
        row += 1

        wall_ms = measurements.get("wall", 0) * 1000
        cpu_ms = measurements.get("cpu", 0) * 1000

        if wall_ms > 0 and row < max_y:
            tps = 1000 / wall_ms
            self._record_sample("wall", wall_ms)
            stats = self._rolling_stats("wall") if details else None
            trend = stats["trend"] if stats else ""
            text = f"{trend}  {'Wall:':<7}  {wall_ms:.2f}ms  ({tps:.0f} t/s)"
            with contextlib.suppress(curses.error):
                self.stdscr.addstr(row, col + 2, text[:width - 2], curses.A_DIM)
            row += 1

        if cpu_ms > 0 and row < max_y:
            self._record_sample("cpu", cpu_ms)
            stats = self._rolling_stats("cpu") if details else None
            trend = stats["trend"] if stats else ""
            text = f"{trend}  {'CPU:':<7}  {cpu_ms:.2f}ms"
            with contextlib.suppress(curses.error):
                self.stdscr.addstr(row, col + 2, text[:width - 2], curses.A_DIM)
            row += 1

        row += 1  # blank line before refresh

        if row < max_y and self._refresh_interval_ms > 0:
            actual_fps = 1000 / self._refresh_interval_ms
            if self._refresh_interval_ms >= 1000:
                time_str = f"{self._refresh_interval_ms / 1000:.1f}s"
            else:
                time_str = f"{self._refresh_interval_ms:.0f}ms"

            with contextlib.suppress(curses.error):
                if self.target_fps:
                    ratio = actual_fps / self.target_fps
                    if ratio >= 0.95:
                        fps_color = curses.color_pair(1)  # green
                    elif ratio >= 0.5:
                        fps_color = curses.color_pair(3)  # yellow
                    else:
                        fps_color = curses.color_pair(2)  # red
                    text = f"  {'Refresh:':<7} {time_str} {actual_fps:.1f}/{self.target_fps:.0f} fps"
                    self.stdscr.addstr(row, col + 2, text[:width - 2], curses.A_DIM)
                    fps_val = f"{actual_fps:.1f}"
                    fps_offset = 11 + len(time_str)
                    self.stdscr.addstr(row, col + 2 + fps_offset, fps_val, fps_color)
                else:
                    text = f"  {'Refresh:':<7} {time_str} ({actual_fps:.1f} fps)"
                    self.stdscr.addstr(row, col + 2, text[:width - 2], curses.A_DIM)
            row += 1

        # Per-system breakdown
        system_times = {k: v * 1000 for k, v in measurements.items() if k not in meta_keys and v > 0}
        if system_times:
            row += 1  # blank line before systems
            if row < max_y:
                self._draw_header(row, col, "Systems", width)
                row += 1

            total_sys_ms = sum(system_times.values())
            sorted_systems = sorted(system_times.items(), key=lambda x: x[1], reverse=True)
            for name, ms in sorted_systems:
                if row >= max_y - 1:
                    break
                short_name = name.replace("System", "")[:9]
                pct = (ms / total_sys_ms) * 100 if total_sys_ms > 0 else 0
                sys_key = "sys:" + name
                self._record_sample(sys_key, ms)
                stats = self._rolling_stats(sys_key) if details else None
                trend = stats["trend"] if stats else ""
                text = f"{trend}  {short_name:<9}  {ms:>6.2f}ms  {pct:>3.0f}%"
                with contextlib.suppress(curses.error):
                    self.stdscr.addstr(row, col + 2, text[:width - 2], curses.A_DIM)
                row += 1

        return row

    # -- Rolling stats -----------------------------------------------------

    def _record_sample(self, key: str, value: float) -> None:
        """Record a sample into a fixed-size ring buffer."""
        history = self._histories.setdefault(key, [])
        history.append(value)
        if len(history) > self._history_max:
            self._histories[key] = history[-self._history_max:]

    def _rolling_stats(self, key: str) -> dict[str, Any] | None:
        """Compute rolling avg, p95, peak, and trend arrow over recorded history.

        Trend compares the average of the last 10 samples vs the 10 before that.
        Arrows: ⬆ (>20% up), ↗ (5-20% up), → (flat), ↘ (5-20% down), ⬇ (>20% down).
        """
        history = self._histories.get(key)
        if not history:
            return None
        n = len(history)
        avg = sum(history) / n
        peak = max(history)
        sorted_h = sorted(history)
        p95_idx = min(int(n * 0.95), n - 1)
        p95 = sorted_h[p95_idx]

        # Trend: compare recent vs previous window
        window = min(10, n // 2) if n >= 4 else 0
        if window >= 2:
            recent = sum(history[-window:]) / window
            previous = sum(history[-window * 2 : -window]) / window
            change = (recent - previous) / previous if previous > 0 else 0.0
            if change > 0.20:
                trend = "⬆"
            elif change > 0.05:
                trend = "↗"
            elif change < -0.20:
                trend = "⬇"
            elif change < -0.05:
                trend = "↘"
            else:
                trend = "→"
        else:
            trend = "→"

        return {"avg": avg, "p95": p95, "peak": peak, "trend": trend}

    # -- Drawing helpers ---------------------------------------------------

    def _draw_header(self, row: int, col: int, title: str, width: int) -> None:
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

    def _safe_addstr(self, row: int, col: int, text: str, attr: int = 0, max_col: int = 0) -> None:
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
