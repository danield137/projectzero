"""
Helper functions for manipulating StatsComponent.
All operations are O(1) and work on the raw component data.
"""

from typing import Literal

from zero.simulation.components import StatsComponent

# Only include living entities that can have stats
EntityType = Literal["Animal", "Human", "Plant"]


def inc_population(stats: StatsComponent, etype: EntityType) -> None:
    """Increment population count for a species."""
    stats.population[etype] += 1


def record_hunger(stats: StatsComponent, etype: EntityType, value: float) -> None:
    """Add a hunger value to the running sum for a species."""
    stats.hunger_sum[etype] += value


def record_energy(stats: StatsComponent, etype: EntityType, value: float) -> None:
    """Add an energy value to the running sum for a species."""
    stats.energy_sum[etype] += value


def record_goal(stats: StatsComponent, etype: EntityType, goal: str) -> None:
    """Record an instance of a goal being chosen for a species."""
    stats.goal_counts[etype][goal] += 1
    stats.goal_total[etype] += 1


def avg_hunger(stats: StatsComponent, etype: EntityType) -> float:
    """Get mean hunger for a species."""
    pop = stats.population[etype]
    return stats.hunger_sum[etype] / pop if pop else 0.0


def avg_energy(stats: StatsComponent, etype: EntityType) -> float:
    """Get mean energy for a species."""
    pop = stats.population[etype]
    return stats.energy_sum[etype] / pop if pop else 0.0


def goal_ratio(stats: StatsComponent, etype: EntityType, goal: str) -> float:
    """Get ratio of times a goal was chosen for a species."""
    total = stats.goal_total[etype]
    return stats.goal_counts[etype][goal] / total if total else 0.0


def goal_ratios(stats: StatsComponent, etype: EntityType) -> dict[str, float]:
    """Get all goal ratios for a species."""
    result = {}
    total = stats.goal_total[etype]
    if total:
        for goal, count in stats.goal_counts[etype].items():
            result[goal] = count / total
    return result


# Food statistics functions
def record_plants_growth(stats: StatsComponent, value: float) -> None:
    """Record plants generated."""
    stats.plants_generated += value


def record_plants_consumed(stats: StatsComponent, value: float) -> None:
    """Record plants consumed."""
    stats.plants_consumed += value


def record_plants_biomass(stats: StatsComponent, value: float) -> None:
    """Record plant biomass."""
    stats.plant_biomass += value


# Life statistics functions
def inc_births(stats: StatsComponent, etype: EntityType) -> None:
    """Increment birth count for a species."""
    stats.births[etype] += 1


def record_death(stats: StatsComponent, etype: EntityType, cause: str) -> None:
    """Record a death with cause for a species."""
    stats.deaths[etype][cause] += 1


def deaths_total(stats: StatsComponent, etype: EntityType) -> int:
    """Get total deaths for a species across all causes."""
    return sum(stats.deaths[etype].values())


def set_living_count(stats: StatsComponent, count: int) -> None:
    """Set current living count."""
    stats.living = count


# Weather statistics functions
def record_precipitation(stats: StatsComponent, value: float) -> None:
    """Record precipitation."""
    stats.precipitation += value


def inc_sunny(stats: StatsComponent) -> None:
    """Increment sunny count."""
    stats.sunny += 1
