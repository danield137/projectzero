from typing import cast

import numpy as np

from sim.common import logging
from sim.ecs.system import System
from zero.simulation.components import (
    GrowthComponent,
    Resettable,
    StatsComponent,
    SummarizedStatsComponent,
)
from zero.simulation.entities import EntityTypes
from zero.simulation.functional import stat_ops

logger = logging.get_logger()


def diff_string(diff: float | int) -> str:
    sign = "+" if diff > 0 else "-"
    if isinstance(diff, int):
        return f"{sign}{abs(diff)}"
    return f"{sign}{abs(diff):.2f}"


def number_with_diff(number: float, diff: float) -> str:
    if diff == 0:
        return f"{number}(==)"

    return f"{number}({diff_string(diff)})"


def last_with_diff(numbers: list[int] | list[float]) -> str:
    last = 0.0
    diff = 0.0
    if len(numbers) > 0:
        last = numbers[-1]
        if len(numbers) > 1:
            diff = last - numbers[0]

    return number_with_diff(last, diff)


def avg_str(numbers: list[int] | list[float]) -> str:
    return f"{np.mean(numbers):.2f}"


def sum_str(numbers: list[int] | list[float]) -> str:
    return f"{np.sum(numbers):.2f}"


def percentage_str(numbers: list[int] | list[float], of: int) -> str:
    return f"{np.sum(numbers) / of:.2f}"


def first(numbers: list[int] | list[float]) -> str:
    if len(numbers) > 0:
        return f"{numbers[0]:.1f}"
    return "0"


class StatsSystem(System):
    def to_string(self, stats: SummarizedStatsComponent) -> str:
        # collect distributions - now nested by species
        goals_parts: list[str] = []
        for sp, sp_goals in stats.goal_distribution.items():
            sp_goals_str = ",".join([f"{g[0]}={np.mean(v):.1f}" for g, v in sp_goals.items() if v])
            if sp_goals_str:
                goals_parts.append(f"{sp[0]}:[{sp_goals_str}]")
        goals = ";".join(goals_parts)

        deaths_parts: list[str] = []
        for sp, sp_deaths in stats.deaths_distribution.items():
            sp_deaths_str = ",".join([f"{c[0]}={np.mean(v) if v else 0:.1f}" for c, v in sp_deaths.items() if v])
            if sp_deaths_str:
                deaths_parts.append(f"{sp[0]}:{sp_deaths_str}")
        deaths = ";".join(deaths_parts)

        # Get current stats from unified stats component
        unified_stats = self.ecs.get_singleton_component(StatsComponent)
        animal_count = unified_stats.population["Animal"]
        human_count = unified_stats.population["Human"]

        # Get per-species birth/death counts from the reporting period
        animal_births = sum_str(stats.births["Animal"]) if stats.births["Animal"] else "0"
        human_births = sum_str(stats.births["Human"]) if stats.births["Human"] else "0"
        animal_deaths = sum_str(stats.deaths["Animal"]) if stats.deaths["Animal"] else "0"
        human_deaths = sum_str(stats.deaths["Human"]) if stats.deaths["Human"] else "0"

        # Show closing stock instead of opening stock for better balance readability
        closing_stock = stats.plant_biomass[-1] if stats.plant_biomass else 0.0

        return (
            f"A={animal_count}(+{animal_births}-{animal_deaths}) "
            f"H={human_count}(+{human_births}-{human_deaths}) "
            f"P={closing_stock:.1f}(+{sum_str(stats.plants_generated)}-{sum_str(stats.plants_consumed)}) "
            f"D=[{deaths}] "
            f"Ws={percentage_str(stats.sunny, stats.reset_every)} "
            f"Wr={avg_str(stats.precipitation)} "
            f"G=[{goals}] "
            f"Ah={stat_ops.avg_hunger(unified_stats, 'Animal'):.2f} "
            f"Hh={stat_ops.avg_hunger(unified_stats, 'Human'):.2f} "
            f"Ae={stat_ops.avg_energy(unified_stats, 'Animal'):.2f} "
            f"He={stat_ops.avg_energy(unified_stats, 'Human'):.2f} "
        )

    def collect_stats(self, stats: SummarizedStatsComponent):
        unified_stats = self.ecs.get_singleton_component(StatsComponent)

        stats.animals.append(unified_stats.living)  # Use unified stats living count

        # Collect per-species births
        stats.births["Animal"].append(unified_stats.births["Animal"])
        stats.births["Human"].append(unified_stats.births["Human"])
        stats.births["Plant"].append(unified_stats.births["Plant"])

        # Collect per-species deaths
        stats.deaths["Animal"].append(stat_ops.deaths_total(unified_stats, "Animal"))
        stats.deaths["Human"].append(stat_ops.deaths_total(unified_stats, "Human"))
        stats.deaths["Plant"].append(stat_ops.deaths_total(unified_stats, "Plant"))

        stats.plants_generated.append(unified_stats.plants_generated)
        stats.plants_consumed.append(unified_stats.plants_consumed)
        # the biomass is equal to the generated minus consumed plants
        act = 0
        ids = self.ecs.get_entities_with_typed_component(GrowthComponent)
        for eid in ids:
            growth = self.ecs.get_typed_component(eid, GrowthComponent)
            if growth.size > 0:
                act += growth.size
        stats.plant_biomass.append(unified_stats.plant_biomass)
        stats.precipitation.append(unified_stats.precipitation)
        stats.hunger.append(stat_ops.avg_hunger(unified_stats, EntityTypes.ANIMAL))
        stats.energy.append(stat_ops.avg_energy(unified_stats, EntityTypes.ANIMAL))
        stats.sunny.append(unified_stats.sunny)

        # Collect goal distribution
        for sp in stats.goal_distribution:
            for activity in stats.goal_distribution[sp]:
                etype = cast(stat_ops.EntityType, sp)
                stats.goal_distribution[sp][activity].append(stat_ops.goal_ratio(unified_stats, etype, activity))

        # Deaths distribution per species
        for sp in stats.deaths_distribution:
            etype = cast(stat_ops.EntityType, sp)
            total = stat_ops.deaths_total(unified_stats, etype)
            for cause in stats.deaths_distribution[sp]:
                count = unified_stats.deaths[sp].get(cause, 0)
                stats.deaths_distribution[sp][cause].append(count / total if total > 0 else 0)

        # Reset only the unified stats component
        resettables: list[Resettable] = [unified_stats]
        for stats_component in resettables:
            stats_component.reset()

    def update(self, simulation_time: int):
        stats = self.ecs.get_singleton_component(SummarizedStatsComponent)
        if (simulation_time % stats.reset_every == 0 and simulation_time > 0) or simulation_time == 1:
            if stats.print_to_console:
                logger.info(self.to_string(stats))
                stats.reset()

        self.collect_stats(stats)
        self.ecs.update_typed_singleton_component(stats)
