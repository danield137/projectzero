"""
ECS Stress Test / Benchmark
============================
Simulates a game world with dummy components & systems, then measures
create / update / delete / iterate throughput at configurable entity scales.

Usage:
    python -m perf.bench_ecs                      # defaults (10K entities, 100 ticks)
    python -m perf.bench_ecs -n 100000 -t 200     # 100K entities, 200 ticks
    python -m perf.bench_ecs --full                # run all preset scales

Each tick applies a mixed workload based on a configurable probability
distribution (create / update / delete), then iterates all entities
through two dummy systems.  Results are printed as a statistics table
comparable to Rust's criterion output.
"""

from __future__ import annotations

import argparse
import math
import random
import time
from dataclasses import dataclass, field

from simz.ecs.component import ClassComponent, ClampedFloatComponent
from simz.ecs.core import ECS


# ── Dummy components ────────────────────────────────────────────────
@dataclass(slots=True)
class PositionComponent(ClassComponent):
    x: float = 0.0
    y: float = 0.0


@dataclass(slots=True)
class VelocityComponent(ClassComponent):
    dx: float = 0.0
    dy: float = 0.0


@dataclass(slots=True)
class HealthBenchComponent(ClampedFloatComponent):
    """Reuses ClampedFloat so we exercise set_clamped_value."""

    pass


ENTITY_TYPE = "BenchEntity"


# ── Dummy systems (plain functions, no System subclass overhead) ────
def movement_system(ecs: ECS) -> int:
    """Move every entity that has Position+Velocity.  Returns count processed."""
    n = 0
    for eid in ecs.get_entities_with_typed_component(VelocityComponent):
        pos = ecs.get_typed_component(eid, PositionComponent)
        vel = ecs.get_typed_component(eid, VelocityComponent)
        if pos is None or vel is None:
            continue
        pos.x += vel.dx
        pos.y += vel.dy
        ecs.update_typed_component(eid, pos)
        n += 1
    return n


def health_decay_system(ecs: ECS) -> int:
    """Tick down health for every entity. Returns count processed."""
    n = 0
    for eid in ecs.get_entities_with_typed_component(HealthBenchComponent):
        hp = ecs.get_typed_component(eid, HealthBenchComponent)
        if hp is None:
            continue
        hp.set_clamped_value(hp.value - 0.001)
        ecs.update_typed_component(eid, hp)
        n += 1
    return n


# ── World loader ────────────────────────────────────────────────────
def load_world(ecs: ECS, n: int, seed: int = 42) -> list[int]:
    """Create *n* entities with all three components.  Returns entity IDs."""
    rng = random.Random(seed)
    eids: list[int] = []
    for _ in range(n):
        eid = ecs.create_entity(
            ENTITY_TYPE,
            [
                PositionComponent(x=rng.uniform(-1000, 1000), y=rng.uniform(-1000, 1000)),
                VelocityComponent(dx=rng.uniform(-1, 1), dy=rng.uniform(-1, 1)),
                HealthBenchComponent(value=rng.uniform(3.0, 10.0), min=0.0, max=10.0),
            ],
        )
        eids.append(eid)
    return eids


# ── Statistics ──────────────────────────────────────────────────────
@dataclass(slots=True)
class Stats:
    label: str
    samples: list[float] = field(default_factory=list)

    def add(self, ns: float) -> None:
        self.samples.append(ns)

    @property
    def n(self) -> int:
        return len(self.samples)

    @property
    def mean(self) -> float:
        return sum(self.samples) / self.n if self.n else 0

    @property
    def median(self) -> float:
        s = sorted(self.samples)
        mid = self.n // 2
        if self.n % 2 == 0:
            return (s[mid - 1] + s[mid]) / 2
        return s[mid]

    @property
    def stddev(self) -> float:
        if self.n < 2:
            return 0
        m = self.mean
        return math.sqrt(sum((x - m) ** 2 for x in self.samples) / (self.n - 1))

    @property
    def p95(self) -> float:
        s = sorted(self.samples)
        return s[int(self.n * 0.95)] if self.n else 0

    @property
    def p99(self) -> float:
        s = sorted(self.samples)
        return s[min(int(self.n * 0.99), self.n - 1)] if self.n else 0

    @property
    def min_val(self) -> float:
        return min(self.samples) if self.samples else 0

    @property
    def max_val(self) -> float:
        return max(self.samples) if self.samples else 0

    def summary(self) -> str:
        return (
            f"  {self.label:<24} "
            f"mean={_fmt(self.mean):>10}  "
            f"med={_fmt(self.median):>10}  "
            f"σ={_fmt(self.stddev):>10}  "
            f"p95={_fmt(self.p95):>10}  "
            f"p99={_fmt(self.p99):>10}  "
            f"min={_fmt(self.min_val):>10}  "
            f"max={_fmt(self.max_val):>10}  "
            f"n={self.n}"
        )


def _fmt(ns: float) -> str:
    """Format nanoseconds into a human-readable duration."""
    if ns < 1_000:
        return f"{ns:.0f}ns"
    if ns < 1_000_000:
        return f"{ns / 1_000:.2f}μs"
    if ns < 1_000_000_000:
        return f"{ns / 1_000_000:.2f}ms"
    return f"{ns / 1_000_000_000:.2f}s"


# ── Benchmark runner ────────────────────────────────────────────────
@dataclass(slots=True)
class BenchConfig:
    entity_count: int = 10_000
    ticks: int = 100
    # per-tick probability of each operation (applied per-entity)
    p_create: float = 0.002  # ~0.2% of pop spawned per tick
    p_delete: float = 0.002  # ~0.2% of pop killed per tick
    seed: int = 42
    warmup_ticks: int = 5


def run_benchmark(cfg: BenchConfig) -> dict[str, Stats]:
    """Run the full benchmark and return per-operation stats."""
    ecs = ECS()
    rng = random.Random(cfg.seed)

    # --- Load ---
    load_stats = Stats("load_world")
    t0 = time.perf_counter_ns()
    alive = load_world(ecs, cfg.entity_count, cfg.seed)
    load_stats.add(time.perf_counter_ns() - t0)

    # --- Per-tick stats ---
    tick_stats = Stats("tick_total")
    iter_stats = Stats("systems_iterate")
    create_stats = Stats("create_entities")
    delete_stats = Stats("delete_entities")
    update_stats = Stats("update_components")

    for tick in range(cfg.ticks + cfg.warmup_ticks):
        is_warmup = tick < cfg.warmup_ticks
        tick_t0 = time.perf_counter_ns()

        # ── Creates ──
        t0 = time.perf_counter_ns()
        n_create = max(1, int(len(alive) * cfg.p_create))
        for _ in range(n_create):
            eid = ecs.create_entity(
                ENTITY_TYPE,
                [
                    PositionComponent(x=rng.uniform(-1000, 1000), y=rng.uniform(-1000, 1000)),
                    VelocityComponent(dx=rng.uniform(-1, 1), dy=rng.uniform(-1, 1)),
                    HealthBenchComponent(value=rng.uniform(3.0, 10.0), min=0.0, max=10.0),
                ],
            )
            alive.append(eid)
        if not is_warmup:
            create_stats.add(time.perf_counter_ns() - t0)

        # ── Deletes ──
        t0 = time.perf_counter_ns()
        n_delete = min(max(1, int(len(alive) * cfg.p_delete)), len(alive))
        for _ in range(n_delete):
            if not alive:
                break
            idx = rng.randint(0, len(alive) - 1)
            eid = alive[idx]
            alive[idx] = alive[-1]
            alive.pop()
            ecs.remove_entity(eid)
        if not is_warmup:
            delete_stats.add(time.perf_counter_ns() - t0)

        # ── Random updates (simulate ad-hoc component writes) ──
        t0 = time.perf_counter_ns()
        n_update = max(1, int(len(alive) * 0.05))  # 5% get a random poke
        for _ in range(n_update):
            if not alive:
                break
            eid = alive[rng.randint(0, len(alive) - 1)]
            pos = ecs.get_typed_component(eid, PositionComponent)
            if pos is not None:
                pos.x += rng.uniform(-5, 5)
                pos.y += rng.uniform(-5, 5)
                ecs.update_typed_component(eid, pos)
        if not is_warmup:
            update_stats.add(time.perf_counter_ns() - t0)

        # ── Systems (full iteration) ──
        t0 = time.perf_counter_ns()
        movement_system(ecs)
        health_decay_system(ecs)
        if not is_warmup:
            iter_stats.add(time.perf_counter_ns() - t0)

        if not is_warmup:
            tick_stats.add(time.perf_counter_ns() - tick_t0)

    return {
        "load_world": load_stats,
        "tick_total": tick_stats,
        "systems_iterate": iter_stats,
        "create_entities": create_stats,
        "delete_entities": delete_stats,
        "update_components": update_stats,
    }


def print_results(cfg: BenchConfig, results: dict[str, Stats]) -> None:
    pop = cfg.entity_count
    print()
    print(f"═══ ECS Benchmark ═══  entities={pop:,}  ticks={cfg.ticks}  "
          f"p_create={cfg.p_create}  p_delete={cfg.p_delete}")
    print(f"{'─' * 120}")
    for stats in results.values():
        print(stats.summary())
    print(f"{'─' * 120}")

    # per-entity throughput for the iteration phase
    iter_s = results["systems_iterate"]
    if iter_s.n and pop:
        ns_per_ent = iter_s.median / pop
        print(f"  iteration throughput   ≈ {_fmt(ns_per_ent)}/entity (median, 2 systems)")
    print()


# ── Preset scales ───────────────────────────────────────────────────
SCALES = [100, 1_000, 10_000, 100_000]


def run_all_scales(ticks: int = 100) -> None:
    for n in SCALES:
        cfg = BenchConfig(entity_count=n, ticks=ticks)
        results = run_benchmark(cfg)
        print_results(cfg, results)


# ── CLI ─────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="ECS stress-test benchmark")
    parser.add_argument("-n", "--entities", type=int, default=10_000, help="Number of entities to load (default: 10K)")
    parser.add_argument("-t", "--ticks", type=int, default=100, help="Number of ticks to simulate (default: 100)")
    parser.add_argument("--p-create", type=float, default=0.002, help="Per-tick create probability (default: 0.002)")
    parser.add_argument("--p-delete", type=float, default=0.002, help="Per-tick delete probability (default: 0.002)")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed (default: 42)")
    parser.add_argument("--full", action="store_true", help="Run all preset scales (100, 1K, 10K, 100K)")
    parser.add_argument("--warmup", type=int, default=5, help="Warmup ticks excluded from stats (default: 5)")
    args = parser.parse_args()

    if args.full:
        run_all_scales(args.ticks)
    else:
        cfg = BenchConfig(
            entity_count=args.entities,
            ticks=args.ticks,
            p_create=args.p_create,
            p_delete=args.p_delete,
            seed=args.seed,
            warmup_ticks=args.warmup,
        )
        results = run_benchmark(cfg)
        print_results(cfg, results)


if __name__ == "__main__":
    main()
