from __future__ import annotations

import abc
import enum
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import (
    Any,
    Literal,
    Protocol,
    runtime_checkable,
)

from tigen.ai.memory import MemoryData
from tigen.ecs.component import (
    BoolComponent,
    ClassComponent,
    IntComponent,
    StringComponent,
    ZeroToTenFloatComponent,
)
from zero.ai.actions import ActionStep
from zero.ai.primitive import PrimitiveGoal

Gender = Literal["M", "F"]
ASSIGNABLE_GENDERS: list[Gender] = ["M", "F"]


class FoodType(str, enum.Enum):
    PLANT = "Plant"
    MEAT = "Meat"


class DietType(str, enum.Enum):
    HERBIVORE = "Herbivore"  # Can only eat plants
    CARNIVORE = "Carnivore"  # Can only eat meat
    OMNIVORE = "Omnivore"  # Can eat both plants and meat


@dataclass(slots=True)
class NameComponent(StringComponent): ...


@dataclass(slots=True)
class BirthdayComponent(IntComponent): ...


@dataclass(slots=True)
class HungerComponent(ZeroToTenFloatComponent): ...


@dataclass(slots=True)
class EnergyComponent(ZeroToTenFloatComponent): ...


@dataclass(slots=True)
class HydrationComponent(ZeroToTenFloatComponent): ...


@dataclass(slots=True)
class HealthComponent(ZeroToTenFloatComponent): ...


@dataclass(slots=True)
class PhotosynthesisComponent(BoolComponent): ...


@dataclass(slots=True)
class PositionComponent(ClassComponent):
    x: int
    y: int


@dataclass(slots=True)
class EdibleComponent(ClassComponent):
    nutrition: float
    food_type: FoodType
    perishable: bool = True  # Whether entity dies when consumed


@dataclass(slots=True)
class DietComponent(ClassComponent):
    diet_type: DietType
    allow_cannibalism: bool = False  # Whether entity can eat its own species


@dataclass(slots=True)
class ReproductiveComponent(ClassComponent):
    gender: Gender
    fertility: float
    fertility_age: int


@dataclass(slots=True)
class LocalTimeComponent(ClassComponent):
    hour: int
    day: int
    year: int
    hours_in_a_day: int
    days_in_a_year: int


@dataclass(slots=True)
class DayNightCycleComponent(ClassComponent):
    is_day: bool
    sunrise: int
    sunset: int


@dataclass(slots=True)
class WeatherConditionsComponent(ClassComponent):
    precipitation: int
    temperature: int
    sunlight: int


@dataclass(slots=True)
class FamilyComponent(ClassComponent):
    mate: int | None
    children: list[int]
    parents: tuple[int, int]
    """
    Left is the mother, right is the father.
    """

    @staticmethod
    def default(parents: tuple[int, int]) -> FamilyComponent:
        return FamilyComponent(mate=None, children=[], parents=parents)


@dataclass(slots=True)
class GrowthComponent(ClassComponent):
    growth_rate: float
    # There should be some basic fact that inhibits growth.
    # IRL, there are physics and biology laws that limit growth.
    # For instance, pulling water from the ground limits the height of a tree.
    # Or, the amount of nutrients in the soil limits the growth of a plant.
    # Right now none of it is modeled, so we grow indefinitely.
    size: float


@runtime_checkable
class Resettable(Protocol):
    def reset(self) -> None:
        """Reset the component to its initial state."""


@dataclass(slots=True)
class StatsComponent(ClassComponent, Resettable):
    """
    Unified stats tracking for all simulation metrics.
    Uses plain dicts for easy serialization.
    """

    # Per-species counts and sums
    population: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    hunger_sum: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    energy_sum: dict[str, float] = field(default_factory=lambda: defaultdict(float))

    # Per-species goal tracking
    goal_counts: dict[str, dict[str, int]] = field(default_factory=lambda: defaultdict(lambda: defaultdict(int)))
    goal_total: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    # Plant statistics
    plants_generated: float = 0.0
    plants_consumed: float = 0.0
    plant_biomass: float = 0.0

    # Life statistics
    births: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    deaths: dict[str, dict[str, int]] = field(default_factory=lambda: defaultdict(lambda: defaultdict(int)))
    living: int = 0

    # Weather statistics
    precipitation: float = 0.0
    sunny: int = 0

    def reset(self) -> None:
        """Reset all stats to zero."""
        self.population.clear()
        self.hunger_sum.clear()
        self.energy_sum.clear()
        self.goal_counts.clear()
        self.goal_total.clear()
        self.plants_generated = 0.0
        self.plants_consumed = 0.0
        self.plant_biomass = 0.0
        self.births.clear()
        self.deaths.clear()
        self.living = 0
        self.precipitation = 0.0
        self.sunny = 0


# Keep EntityStatsComponent as an alias for backward compatibility during migration
EntityStatsComponent = StatsComponent


@dataclass(slots=True)
class SummarizedStatsComponent(ClassComponent):
    """
    Stores "moving" statistics that are reset every day.
    Generally, we collect the values at every "tick" in a list.
    """

    reset_every: int = 24
    print_to_console: bool = True
    animals: list[int] = field(default_factory=list[int])
    plants: list[int] = field(default_factory=list[int])
    births: dict[str, list[int]] = field(default_factory=lambda: defaultdict(list[int]))
    deaths: dict[str, list[int]] = field(default_factory=lambda: defaultdict(list[int]))
    hunger: list[float] = field(default_factory=list[float])
    energy: list[float] = field(default_factory=list[float])
    plants_generated: list[float] = field(default_factory=list[float])
    plants_consumed: list[float] = field(default_factory=list[float])
    plant_biomass: list[float] = field(default_factory=list[float])
    precipitation: list[float] = field(default_factory=list[float])
    sunny: list[int] = field(default_factory=list[int])
    goal_distribution: dict[str, dict[str, list[float]]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(list[float]))
    )
    deaths_distribution: dict[str, dict[str, list[float]]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(list[float]))
    )

    def __post_init__(self):
        self.animals = []
        self.plants = []
        self.births = {"Animal": [], "Human": [], "Plant": []}
        self.deaths = {"Animal": [], "Human": [], "Plant": []}
        self.hunger = []
        self.energy = []
        self.plants_generated = []
        self.plants_consumed = []
        self.plant_biomass = []
        self.precipitation = []
        self.sunny = []
        self.goal_distribution = {s: {k: [] for k in goals()} for s in species()}
        self.deaths_distribution = {s: {k: [] for k in death_causes()} for s in species()}

    def reset(self):
        self.animals.clear()
        self.plants.clear()
        self.births = {"Animal": [], "Human": [], "Plant": []}
        self.deaths = {"Animal": [], "Human": [], "Plant": []}
        self.hunger.clear()
        self.energy.clear()
        self.plants_generated.clear()
        self.plants_consumed.clear()
        self.plant_biomass.clear()
        self.precipitation.clear()
        self.sunny.clear()
        self.goal_distribution = {s: {k: [] for k in goals()} for s in species()}
        self.deaths_distribution = {s: {k: [] for k in death_causes()} for s in species()}


@dataclass(slots=True)
class WellbeingConditionComponent(ClassComponent):
    since: int


@dataclass(slots=True)
class PregnancyComponent(WellbeingConditionComponent):
    offsprings: float
    mate: int


@dataclass(slots=True)
class LifeExpectancyComponent(IntComponent): ...


@dataclass(slots=True)
class WellbeingComponent(ClassComponent):
    """
    A grouping of various health conditions.
    This is probably not the most efficient way to model this, but it's a start.
    A more efficient way would probably be to use a bit map or something of that sort.
    """

    starving: WellbeingConditionComponent | None = None
    hungry: WellbeingConditionComponent | None = None
    pregnancy: PregnancyComponent | None = None
    tired: WellbeingConditionComponent | None = None
    well_fed: WellbeingConditionComponent | None = None
    well_rested: WellbeingConditionComponent | None = None

    @staticmethod
    def default() -> WellbeingComponent:
        return WellbeingComponent()


@dataclass(slots=True)
class Activity(abc.ABC):
    since: int

    def is_eating(self) -> bool:
        return isinstance(self, EatingActivity)

    def is_sleeping(self) -> bool:
        return isinstance(self, SleepingActivity)

    def is_idle(self) -> bool:
        return isinstance(self, IdleActivity)

    @property
    def name(self) -> str:
        return self.__class__.__qualname__


@dataclass(slots=True)
class EatingActivity(Activity):
    food: int


@dataclass(slots=True)
class MatingActivity(Activity):
    mate: int


@dataclass(slots=True)
class SleepingActivity(Activity): ...


@dataclass(slots=True)
class IdleActivity(Activity): ...


def activities() -> list[str]:
    return [
        EatingActivity.__qualname__,
        SleepingActivity.__qualname__,
        IdleActivity.__qualname__,
        MatingActivity.__qualname__,
    ]


def goals() -> list[str]:
    return [goal.value for goal in PrimitiveGoal]


class CauseOfDeath(str, enum.Enum):
    LOW_HEALTH = "LowHealth"
    OLD_AGE = "OldAge"
    EATEN = "Eaten"


def death_causes() -> list[str]:
    # enum value to list
    return [cause.value for cause in CauseOfDeath]


def species() -> list[str]:
    return ["Animal", "Human", "Plant"]


@dataclass(slots=True)
class ActivityComponent(ClassComponent):
    activity: Activity

    @staticmethod
    def default() -> ActivityComponent:
        return ActivityComponent(IdleActivity(0))


# TODO: make this more ergonomic
@dataclass(slots=True)
class EntitiesConfigComponent(ClassComponent):
    """
    The entities config is a dictionary of dictionaries.
    The first level is the entity type (e.g. "animal", "plant").
    The second level is the component type (e.g. "energy", "pregnancy").
    The third level is the specific property (e.g. "health_reg_rate", "reproduction_rate").
    The values are the default values for each property.
    """

    _entities: dict[str, dict[str, dict[str, float]]] = field(repr=False)

    @property
    def entities(self) -> dict[str, dict[str, dict[str, float]]]:
        return self._entities

    def __getitem__(self, key: str) -> Any:
        return self._entities[key]


class BrainType(str, enum.Enum):
    ANIMAL = "Animal"
    HUMAN = "Human"

    @staticmethod
    def all() -> list[str]:
        return [BrainType.ANIMAL, BrainType.HUMAN]


# -------------------------------------------------------
# AI Components
# -------------------------------------------------------


@dataclass(slots=True)
class BrainComponent(ClassComponent):
    brain_type: BrainType
    current_goal: PrimitiveGoal = PrimitiveGoal.IDLE
    current_plan: Sequence[ActionStep] | None = None


@dataclass(slots=True)
class MemoryComponent(ClassComponent):
    # memory is a complex entity. the logic associated with it is elsewhere.
    data: MemoryData


@dataclass(slots=True)
class SensesComponent(ClassComponent): ...


@dataclass(slots=True)
class PerceptionComponent(ClassComponent): ...


@dataclass(slots=True)
class BeliefComponent(ClassComponent): ...


@dataclass(slots=True)
class InstinctOverrideComponent(ClassComponent): ...
