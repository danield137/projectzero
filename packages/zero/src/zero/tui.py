"""Zero simulation TUI dashboard.

Uses the tigen TUI dashboard framework to provide a curses-based dashboard
for the zero simulation. All domain-specific data extraction lives here;
the rendering is handled by the framework.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
from tigen.tui import Bar, BarChart, BarGroup, Metric, Panel, Table, TUIDashboard

if TYPE_CHECKING:
    from tigen.ecs.core import ECS


def _extract_context(ecs: ECS) -> dict[str, Any]:
    """Extract zero-specific world stats from the ECS into a flat context dict."""
    from zero.simulation.components import (
        EnergyComponent,
        HungerComponent,
        SummarizedStatsComponent,
    )
    from zero.simulation.entities import EntityTypes

    ctx: dict[str, Any] = {}

    try:
        stats = ecs.get_singleton_component(SummarizedStatsComponent)

        # Population counts
        animal_eids = ecs.entities_by_type.get(EntityTypes.ANIMAL)
        human_eids = ecs.entities_by_type.get(EntityTypes.HUMAN)
        animal_count = len(animal_eids) if animal_eids else 0
        human_count = len(human_eids) if human_eids else 0

        ctx["animals"] = animal_count
        ctx["humans"] = human_count
        ctx["plant_biomass"] = stats.plant_biomass[-1] if stats.plant_biomass else 0.0

        # Births/deaths (from summarized stats, current period)
        ctx["animal_births"] = sum(stats.births.get("Animal", []))
        ctx["animal_deaths"] = sum(stats.deaths.get("Animal", []))
        ctx["human_births"] = sum(stats.births.get("Human", []))
        ctx["human_deaths"] = sum(stats.deaths.get("Human", []))
        ctx["plants_generated"] = sum(stats.plants_generated)
        ctx["plants_consumed"] = sum(stats.plants_consumed)

        # Weather
        ctx["sunny_ratio"] = sum(stats.sunny) / len(stats.sunny) if stats.sunny else 0.0
        ctx["precipitation"] = float(np.mean(stats.precipitation)) if stats.precipitation else 0.0

        # Vitals
        a_hunger, a_energy = 0.0, 0.0
        if animal_eids:
            for eid in animal_eids:
                a_hunger += ecs.get_typed_component(eid, HungerComponent).value
                a_energy += ecs.get_typed_component(eid, EnergyComponent).value
        ctx["avg_animal_hunger"] = a_hunger / animal_count if animal_count else 0.0
        ctx["avg_animal_energy"] = a_energy / animal_count if animal_count else 0.0

        h_hunger, h_energy = 0.0, 0.0
        if human_eids:
            for eid in human_eids:
                h_hunger += ecs.get_typed_component(eid, HungerComponent).value
                h_energy += ecs.get_typed_component(eid, EnergyComponent).value
        ctx["avg_human_hunger"] = h_hunger / human_count if human_count else 0.0
        ctx["avg_human_energy"] = h_energy / human_count if human_count else 0.0

        # Goals distribution
        goals: dict[str, dict[str, float]] = {}
        for sp, sp_goals in stats.goal_distribution.items():
            goals[sp] = {}
            for goal, values in sp_goals.items():
                if values:
                    goals[sp][goal] = float(np.mean(values))
        ctx["goals"] = goals

    except Exception:
        # Stats might not be available yet
        ctx.setdefault("animals", 0)
        ctx.setdefault("humans", 0)
        ctx.setdefault("plant_biomass", 0.0)
        ctx.setdefault("goals", {})

    return ctx


def _population_rows(ctx: dict[str, Any]) -> list[list[str]]:
    rows = []
    for label, count_key, birth_key, death_key in [
        ("Animal", "animals", "animal_births", "animal_deaths"),
        ("Human", "humans", "human_births", "human_deaths"),
    ]:
        count = ctx.get(count_key, 0)
        births = ctx.get(birth_key, 0)
        deaths = ctx.get(death_key, 0)
        net = births - deaths
        net_str = f"+{net}" if net >= 0 else str(net)
        rows.append([label, str(count), net_str, str(births), str(deaths)])

    # Plants
    biomass = ctx.get("plant_biomass", 0.0)
    gen = ctx.get("plants_generated", 0.0)
    con = ctx.get("plants_consumed", 0.0)
    net = gen - con
    net_str = f"+{net:.0f}" if net >= 0 else f"{net:.0f}"
    rows.append(["Plant", f"{biomass:.0f}", net_str, f"{gen:.0f}", f"{con:.0f}"])

    return rows


def _vitals_rows(ctx: dict[str, Any]) -> list[list[str]]:
    return [
        ["Animal", f"{ctx.get('avg_animal_hunger', 0):.2f}", f"{ctx.get('avg_animal_energy', 0):.2f}"],
        ["Human", f"{ctx.get('avg_human_hunger', 0):.2f}", f"{ctx.get('avg_human_energy', 0):.2f}"],
    ]


def _activity_bars(ctx: dict[str, Any]) -> list[BarGroup]:
    groups = []
    goals = ctx.get("goals", {})
    for species, species_goals in goals.items():
        if not species_goals:
            continue
        bars = [
            Bar(label=goal, ratio=ratio)
            for goal, ratio in sorted(species_goals.items(), key=lambda x: x[1], reverse=True)
            if ratio > 0.01
        ]
        if bars:
            groups.append(BarGroup(label=species, bars=bars))
    return groups


ZERO_DASHBOARD = TUIDashboard(
    title="Project Zero",
    context=_extract_context,
    perf_details=True,
    panels=[
        Panel("Population", [
            Table(
                headers=["", "Count", "Net", "Born", "Died"],
                fn=_population_rows,
            ),
        ]),
        Panel("Vitals (Avg)", [
            Table(
                headers=["", "Hunger", "Energy"],
                fn=_vitals_rows,
            ),
        ]),
        Panel("Activity", [
            BarChart(fn=_activity_bars),
        ]),
        Panel("Weather", [
            Metric("Sun", lambda ctx: f"{ctx.get('sunny_ratio', 0) * 100:.0f}%"),
            Metric("Rain", lambda ctx: f"{ctx.get('precipitation', 0):.1f}"),
        ]),
    ],
)
