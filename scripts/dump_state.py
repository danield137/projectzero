"""
Dump simulation state to JSONL for analysis.
Runs the simulation for N ticks, writing a snapshot each tick.
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

from tigen.config import RunConfiguration, set_global_config
from tigen.ecs.core import ECS
from zero import Simulation
from zero.simulation.components import (
    ActivityComponent,
    BrainComponent,
    EnergyComponent,
    GrowthComponent,
    HealthComponent,
    HungerComponent,
    LifeExpectancyComponent,
    NameComponent,
    ReproductiveComponent,
    WellbeingComponent,
)
from zero.simulation.entities import EntityTypes


def dump_entity(ecs: ECS, eid: int, etype: str) -> dict:
    """Serialize one entity's key components."""
    data: dict = {"id": eid, "type": etype}

    name = ecs.get_typed_component(eid, NameComponent)
    if name:
        data["name"] = name.value

    hunger = ecs.get_typed_component(eid, HungerComponent)
    if hunger:
        data["hunger"] = round(hunger.value, 3)

    energy = ecs.get_typed_component(eid, EnergyComponent)
    if energy:
        data["energy"] = round(energy.value, 3)

    health = ecs.get_typed_component(eid, HealthComponent)
    if health:
        data["health"] = round(health.value, 3)

    growth = ecs.get_typed_component(eid, GrowthComponent)
    if growth:
        data["size"] = round(growth.size, 3)
        data["growth_rate"] = round(growth.growth_rate, 3)

    repro = ecs.get_typed_component(eid, ReproductiveComponent)
    if repro:
        data["gender"] = repro.gender
        data["fertility"] = round(repro.fertility, 3)

    life = ecs.get_typed_component(eid, LifeExpectancyComponent)
    if life:
        data["life_expectancy"] = life.value

    brain = ecs.get_typed_component(eid, BrainComponent)
    if brain:
        data["goal"] = brain.current_goal.value

    activity = ecs.get_typed_component(eid, ActivityComponent)
    if activity:
        data["activity"] = activity.activity.name

    wellbeing = ecs.get_typed_component(eid, WellbeingComponent)
    if wellbeing:
        conditions = []
        if wellbeing.starving:
            conditions.append("starving")
        if wellbeing.hungry:
            conditions.append("hungry")
        if wellbeing.pregnancy:
            conditions.append(f"pregnant(since={wellbeing.pregnancy.since},offspring={wellbeing.pregnancy.offsprings})")
        if wellbeing.tired:
            conditions.append("tired")
        if wellbeing.well_fed:
            conditions.append("well_fed")
        if wellbeing.well_rested:
            conditions.append("well_rested")
        if conditions:
            data["conditions"] = conditions

    return data


def dump_tick(sim: Simulation, tick: int) -> dict:
    """Capture full simulation state at one tick."""
    ecs = sim.ecs
    counts: dict[str, int] = defaultdict(int)
    entities: list[dict] = []

    for eid in ecs.entities_by_id:
        etype = ecs.entities_by_id[eid]
        # Skip metadata/config/world/weather singletons
        if etype in (EntityTypes.Metadata, EntityTypes.CONFIG, EntityTypes.WORLD, EntityTypes.WEATHER):
            continue
        counts[etype] += 1
        entities.append(dump_entity(ecs, eid, etype))

    # Aggregate stats
    plant_biomass = sum(e.get("size", 0) for e in entities if e["type"] == EntityTypes.PLANT)

    summary = {
        "tick": tick,
        "counts": dict(counts),
        "plant_biomass": round(plant_biomass, 1),
    }

    # Per-species averages for living entities
    for species in [EntityTypes.ANIMAL, EntityTypes.HUMAN]:
        sp_entities = [e for e in entities if e["type"] == species]
        if sp_entities:
            summary[f"{species.lower()}_avg_hunger"] = round(sum(e.get("hunger", 0) for e in sp_entities) / len(sp_entities), 3)
            summary[f"{species.lower()}_avg_energy"] = round(sum(e.get("energy", 0) for e in sp_entities) / len(sp_entities), 3)
            summary[f"{species.lower()}_avg_health"] = round(sum(e.get("health", 0) for e in sp_entities) / len(sp_entities), 3)

            # Goal distribution
            goal_counts: dict[str, int] = defaultdict(int)
            for e in sp_entities:
                goal_counts[e.get("goal", "unknown")] += 1
            summary[f"{species.lower()}_goals"] = dict(goal_counts)

            # Condition distribution
            condition_counts: dict[str, int] = defaultdict(int)
            for e in sp_entities:
                for c in e.get("conditions", []):
                    key = c.split("(")[0]  # strip params
                    condition_counts[key] += 1
            if condition_counts:
                summary[f"{species.lower()}_conditions"] = dict(condition_counts)

    return {"summary": summary, "entities": entities}


def main():
    parser = argparse.ArgumentParser(description="Dump simulation state to JSONL")
    parser.add_argument("-t", "--ticks", type=int, default=200, help="Number of ticks to run")
    parser.add_argument("-o", "--output", type=str, default="sim_dump.jsonl", help="Output file path")
    parser.add_argument("--summary-only", action="store_true", help="Only write summary, skip per-entity data")
    args = parser.parse_args()

    output = Path(args.output)
    config = RunConfiguration()
    sim = Simulation(config)
    sim.setup_simulation()
    sim.set_starting_conditions()

    with output.open("w") as f:
        for tick in range(args.ticks):
            sim.simulation_time = tick

            # Run all systems
            for system in sim.system_instances.values():
                system.update(tick)

            state = dump_tick(sim, tick)
            if args.summary_only:
                f.write(json.dumps(state["summary"]) + "\n")
            else:
                f.write(json.dumps(state) + "\n")

            sim.simulation_time += 1

    counts = state["summary"]["counts"]
    print(f"Wrote {args.ticks} ticks to {output}")
    print(f"Final state: {counts}, biomass={state['summary']['plant_biomass']}")


if __name__ == "__main__":
    main()
