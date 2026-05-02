"""Tests for dual-schedule App (fixed + render systems) and pacing."""

from __future__ import annotations

import pytest
from tigen.app import App, AppBuilder
from tigen.config import RunConfiguration
from tigen.ecs.core import ECS
from tigen.ecs.system import System

# ---------------------------------------------------------------------------
# Test helpers: minimal systems that record calls
# ---------------------------------------------------------------------------

class FixedCounterSystem(System):
    """Records each simulation_time it was called with."""
    calls: list[int]

    def init_system(self, ecs: ECS):
        super().init_system(ecs)
        self.calls = []

    def update(self, simulation_time: int):
        self.calls.append(simulation_time)


class RenderCounterSystem(System):
    """Records each simulation_time it was called with."""
    calls: list[int]

    def init_system(self, ecs: ECS):
        super().init_system(ecs)
        self.calls = []

    def update(self, simulation_time: int):
        self.calls.append(simulation_time)


class MutatingSystem(System):
    """Writes a value into the ECS so render can observe it."""
    def update(self, simulation_time: int):
        # Store the current simulation_time as a tag on the ECS for inspection
        self.ecs._test_mutated_at = simulation_time  # type: ignore[attr-defined]


class ObservingSystem(System):
    """Reads the value written by MutatingSystem and records it."""
    observed: list[int]

    def init_system(self, ecs: ECS):
        super().init_system(ecs)
        self.observed = []

    def update(self, simulation_time: int):
        val = getattr(self.ecs, "_test_mutated_at", None)
        self.observed.append(val)


class CleanupTracker(System):
    cleaned_up: bool = False

    def update(self, simulation_time: int):
        pass

    def shutdown(self):
        CleanupTracker.cleaned_up = True


class StartupTracker(System):
    started: bool = False
    app_ref: object = None

    def startup(self, app):
        StartupTracker.started = True
        StartupTracker.app_ref = app

    def update(self, simulation_time: int):
        pass


class StopRequester(System):
    """Calls app.request_stop() after 3 ticks."""
    _app_ref: object = None

    def startup(self, app):
        StopRequester._app_ref = app

    def update(self, simulation_time: int):
        if simulation_time >= 3 and StopRequester._app_ref is not None:
            StopRequester._app_ref.request_stop()


def _noop_setup(ecs: ECS) -> None:
    pass


def _build_simple(
    fixed: list[type[System]] | None = None,
    render: list[type[System]] | None = None,
    *,
    use_with_systems: bool = False,
    ticks_per_second: float | None = None,
    refresh_rate: float | None = None,
) -> App:
    builder = AppBuilder()
    if use_with_systems:
        builder.with_systems(fixed or [FixedCounterSystem])
    else:
        builder.with_fixed_systems(fixed or [FixedCounterSystem])
    if render:
        builder.with_render_systems(render)
    builder.with_setup(_noop_setup)
    builder.with_config(RunConfiguration.default())
    if ticks_per_second is not None:
        builder.with_ticks_per_second(ticks_per_second)
    if refresh_rate is not None:
        builder.with_refresh_rate(refresh_rate)
    return builder.build()


# ---------------------------------------------------------------------------
# Builder API tests
# ---------------------------------------------------------------------------

class TestBuilderAPI:
    def test_with_systems_alias(self):
        """with_systems() works as alias for with_fixed_systems()."""
        app = _build_simple(use_with_systems=True)
        app.setup()
        assert FixedCounterSystem in app.system_instances

    def test_with_fixed_systems_explicit(self):
        """with_fixed_systems() registers fixed systems."""
        app = _build_simple(use_with_systems=False)
        app.setup()
        assert FixedCounterSystem in app.system_instances

    def test_conflict_systems_then_fixed(self):
        """Calling with_systems() then with_fixed_systems() raises ValueError."""
        builder = AppBuilder()
        builder.with_systems([FixedCounterSystem])
        with pytest.raises(ValueError, match="Cannot call both"):
            builder.with_fixed_systems([FixedCounterSystem])

    def test_conflict_fixed_then_systems(self):
        """Calling with_fixed_systems() then with_systems() raises ValueError."""
        builder = AppBuilder()
        builder.with_fixed_systems([FixedCounterSystem])
        with pytest.raises(ValueError, match="Cannot call both"):
            builder.with_systems([FixedCounterSystem])

    def test_no_fixed_systems_raises(self):
        """build() raises when no fixed systems are provided."""
        builder = AppBuilder().with_setup(_noop_setup)
        with pytest.raises(ValueError, match="Fixed systems are required"):
            builder.build()

    def test_render_systems_optional(self):
        """App builds and runs without render systems."""
        app = _build_simple(render=None)
        app.run(max_ticks=5, debug_mode=False)
        assert app.simulation_time == 5

    def test_invalid_ticks_per_second(self):
        """Negative or zero ticks_per_second raises ValueError."""
        builder = AppBuilder()
        with pytest.raises(ValueError, match="ticks_per_second must be positive"):
            builder.with_ticks_per_second(0)
        with pytest.raises(ValueError, match="ticks_per_second must be positive"):
            builder.with_ticks_per_second(-5)

    def test_invalid_refresh_rate(self):
        """Negative or zero refresh_rate raises ValueError."""
        builder = AppBuilder()
        with pytest.raises(ValueError, match="refresh_rate must be positive"):
            builder.with_refresh_rate(0)

    def test_refresh_without_ticks_builds(self):
        """refresh_rate without ticks_per_second is valid (unbounded sim, gated render)."""
        app = (
            AppBuilder()
            .with_fixed_systems([FixedCounterSystem])
            .with_setup(_noop_setup)
            .with_refresh_rate(30)
            .build()
        )
        assert app._refresh_rate == 30
        assert app._ticks_per_second is None


# ---------------------------------------------------------------------------
# Tick ordering tests
# ---------------------------------------------------------------------------

class TestTickOrdering:
    def test_fixed_runs_on_step(self):
        """step() runs fixed systems and increments simulation_time."""
        app = _build_simple(fixed=[FixedCounterSystem])
        app.setup()
        app.step()

        fixed = app._fixed_instances[FixedCounterSystem]
        assert fixed.calls == [0]
        assert app.simulation_time == 1

    def test_step_does_not_run_render(self):
        """step() does NOT run render systems — those only run inside run()."""
        app = _build_simple(
            fixed=[FixedCounterSystem],
            render=[RenderCounterSystem],
        )
        app.setup()
        app.step()
        app.step()

        render = app._render_instances[RenderCounterSystem]
        assert render.calls == []

    def test_run_fixed_before_render(self):
        """In run(), fixed systems execute before render systems."""
        app = _build_simple(
            fixed=[MutatingSystem],
            render=[ObservingSystem],
        )
        app.run(max_ticks=3, debug_mode=False)

        observer = app._render_instances[ObservingSystem]
        # MutatingSystem.update(t) writes t to ECS. step() increments simulation_time.
        # Render then reads the value MutatingSystem wrote (0, 1, 2).
        assert observer.observed == [0, 1, 2]

    def test_simulation_time_increments_per_step(self):
        """simulation_time increments by 1 per step() call."""
        app = _build_simple(fixed=[FixedCounterSystem])
        app.setup()
        assert app.simulation_time == 0
        app.step()
        assert app.simulation_time == 1
        app.step()
        assert app.simulation_time == 2


# ---------------------------------------------------------------------------
# system_instances compatibility
# ---------------------------------------------------------------------------

class TestSystemInstances:
    def test_system_instances_contains_fixed_only(self):
        """system_instances contains only fixed systems (for dump_state compat)."""
        app = _build_simple(
            fixed=[FixedCounterSystem],
            render=[RenderCounterSystem],
        )
        app.setup()
        assert FixedCounterSystem in app.system_instances
        assert RenderCounterSystem not in app.system_instances


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

class TestCleanup:
    def test_cleanup_both_schedules(self):
        """Cleanup is called on both fixed and render systems."""
        CleanupTracker.cleaned_up = False

        app = _build_simple(
            fixed=[FixedCounterSystem],
            render=[CleanupTracker],
        )
        app.run(max_ticks=2, debug_mode=False)
        assert CleanupTracker.cleaned_up


# ---------------------------------------------------------------------------
# Unpaced run (backward compat)
# ---------------------------------------------------------------------------

class TestUnpacedRun:
    def test_run_max_ticks(self):
        """Unpaced run respects max_ticks."""
        app = _build_simple()
        app.run(max_ticks=10, debug_mode=False)
        assert app.simulation_time == 10

    def test_run_stop_condition(self):
        """Unpaced run respects stop_condition."""
        app = (
            AppBuilder()
            .with_fixed_systems([FixedCounterSystem])
            .with_setup(_noop_setup)
            .with_stop_condition(lambda a: a.simulation_time >= 5)
            .build()
        )
        app.run(max_ticks=100, debug_mode=False)
        assert app.simulation_time == 5

    def test_step_measurements(self):
        """When measurements enabled, step() populates app.measurements."""
        app = _build_simple()
        app._measurements_enabled = True
        app.setup()
        app.step()
        assert "FixedCounterSystem" in app.measurements
        assert "wall" in app.measurements
        assert "cpu" in app.measurements

    def test_step_no_measurements_by_default(self):
        """Without measurements, app.measurements stays empty."""
        app = _build_simple()
        app.setup()
        app.step()
        assert app.measurements == {}

    def test_render_runs_in_unpaced_run(self):
        """Render systems run during unpaced run() (no refresh_rate = every iteration)."""
        app = _build_simple(
            fixed=[FixedCounterSystem],
            render=[RenderCounterSystem],
        )
        app.run(max_ticks=5, debug_mode=False)

        render = app._render_instances[RenderCounterSystem]
        # Render should have run every iteration
        assert len(render.calls) == 5

    def test_refresh_rate_without_ticks_per_second(self):
        """refresh_rate alone: sim unbounded, render wall-clock gated."""
        app = _build_simple(
            fixed=[FixedCounterSystem],
            render=[RenderCounterSystem],
            refresh_rate=10,  # 10 FPS = 100ms interval
        )
        app.run(max_ticks=50, debug_mode=False)

        fixed = app._fixed_instances[FixedCounterSystem]
        render = app._render_instances[RenderCounterSystem]
        # Fixed runs every iteration (50 times)
        assert len(fixed.calls) == 50
        # Render runs fewer times due to wall-clock gating
        # (sim runs so fast that 50 ticks likely complete in <100ms, so render ~1 time)
        assert len(render.calls) < len(fixed.calls)


# ---------------------------------------------------------------------------
# Paced run
# ---------------------------------------------------------------------------

class TestPacedRun:
    def test_paced_reaches_max_ticks(self):
        """Paced run reaches max_ticks via accumulator."""
        app = _build_simple(ticks_per_second=1000, refresh_rate=1000)
        app.run(max_ticks=20, debug_mode=False)
        assert app.simulation_time == 20

    def test_paced_stop_condition(self):
        """Paced run respects stop_condition."""
        app = (
            AppBuilder()
            .with_fixed_systems([FixedCounterSystem])
            .with_setup(_noop_setup)
            .with_ticks_per_second(1000)
            .with_stop_condition(lambda a: a.simulation_time >= 5)
            .build()
        )
        app.run(max_ticks=100, debug_mode=False)
        assert app.simulation_time == 5

    def test_paced_render_runs_each_frame(self):
        """In paced mode, render systems run once per outer loop pass."""
        app = _build_simple(
            fixed=[FixedCounterSystem],
            render=[RenderCounterSystem],
            ticks_per_second=1000,
            refresh_rate=1000,
        )
        app.run(max_ticks=5, debug_mode=False)

        fixed = app._fixed_instances[FixedCounterSystem]
        render = app._render_instances[RenderCounterSystem]

        # Fixed should have run exactly 5 times (ticks 0-4)
        assert len(fixed.calls) == 5
        # Render runs at least once (it runs each frame, not each tick)
        assert len(render.calls) >= 1

    def test_paced_ticks_only_no_refresh(self):
        """ticks_per_second without refresh_rate: paced ticks, no frame sleep."""
        app = _build_simple(ticks_per_second=1000)
        app.run(max_ticks=10, debug_mode=False)
        assert app.simulation_time == 10


# ---------------------------------------------------------------------------
# Lifecycle hooks
# ---------------------------------------------------------------------------

class TestLifecycle:
    def test_startup_called_with_app(self):
        """startup() is called with the App reference after setup."""
        StartupTracker.started = False
        StartupTracker.app_ref = None

        app = _build_simple(fixed=[StartupTracker])
        app.run(max_ticks=1, debug_mode=False)
        assert StartupTracker.started
        assert StartupTracker.app_ref is app

    def test_startup_called_for_render_systems(self):
        """startup() is called on render systems too."""
        StartupTracker.started = False
        StartupTracker.app_ref = None

        app = _build_simple(
            fixed=[FixedCounterSystem],
            render=[StartupTracker],
        )
        app.run(max_ticks=1, debug_mode=False)
        assert StartupTracker.started

    def test_request_stop(self):
        """request_stop() causes the loop to exit."""
        StopRequester._app_ref = None

        app = _build_simple(fixed=[StopRequester])
        app.run(max_ticks=100, debug_mode=False)
        # StopRequester calls request_stop at simulation_time >= 3
        # So it runs ticks 0, 1, 2, 3 (request_stop at 3), then exits
        assert app.simulation_time == 4

    def test_request_stop_from_render_system(self):
        """A render system can call request_stop() to exit the loop."""
        StopRequester._app_ref = None

        app = _build_simple(
            fixed=[FixedCounterSystem],
            render=[StopRequester],
        )
        app.run(max_ticks=100, debug_mode=False)
        assert app.simulation_time <= 5  # should stop around tick 3-4
