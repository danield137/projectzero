from collections.abc import Callable, Sequence
from typing import Any
from uuid import uuid4

from tigen.ai.memory import MemoryData
from tigen.common import math
from tigen.common.extensions import deep_freeze
from tigen.ecs.component import Component
from zero.simulation.components import (
    ASSIGNABLE_GENDERS,
    ActivityComponent,
    BirthdayComponent,
    BrainComponent,
    BrainType,
    DayNightCycleComponent,
    DietComponent,
    DietType,
    EdibleComponent,
    EnergyComponent,
    EntitiesConfigComponent,
    FamilyComponent,
    FoodType,
    GrowthComponent,
    HealthComponent,
    HungerComponent,
    HydrationComponent,
    LifeExpectancyComponent,
    LocalTimeComponent,
    MemoryComponent,
    NameComponent,
    PhotosynthesisComponent,
    PositionComponent,
    PregnancyComponent,
    PrimitiveGoal,
    ReproductiveComponent,
    StatsComponent,
    SummarizedStatsComponent,
    WeatherConditionsComponent,
    WellbeingComponent,
)


class EntityTypes:
    WORLD = "World"
    WEATHER = "Weather"
    PLANT = "Plant"
    ANIMAL = "Animal"
    HUMAN = "Human"  # New human entity type
    Metadata = "Metadata"
    CONFIG = "Config"


INFINITE = -1

# TODO: this should probably be typed, but need to make sure it doesn't hurt performance.
_ENTITY_CONFIG: dict[str, Any] = {
    EntityTypes.HUMAN: {
        # Humans have longer lifecycles than animals
        PregnancyComponent: {"full_term": 75},  # Longer pregnancy period
        ReproductiveComponent: {"fertility_age": 75},  # Later reproductive maturity
        HungerComponent: {
            "min": 0.0,
            "max": 10.0 - math.EPSILON,
            "time_to_starve": 15.0,  # Slightly more resilient
            "loss_rate_weight": 0.1,
            "gain_rate_weight": 0.1,
        },
        EnergyComponent: {
            "min": 0.0,
            "max": 10.0 - math.EPSILON,
            "idle_drain_rate": 0.1,
            "active_drain_rate": 0.5,
            "sleep_gain_rate": 2.0,
        },
        HealthComponent: {
            "min": 0.0,
            "max": 10.0,
            "regen_rate": 0.000001,
            "starvation_penalty": 0.1,
            "tired_penalty": 0.01,
            "hungry_penalty": 0.0,
            "well_fed_effect_duration": 10,
            "well_rested_effect_duration": 10,
        },
        LifeExpectancyComponent: {"max": 12 * 24 * 4, "avg": 8 * 24 * 3, "stddev": 2 * 24},  # Longer lifespan
    },
    EntityTypes.ANIMAL: {
        # this should be an expected value (mean and std deviation)
        PregnancyComponent: {"full_term": 50},
        ReproductiveComponent: {"fertility_age": 50},
        # TODO: theses two are actually enums. I'm not sure what's the right way to deal with this.
        # One options would be to "derive" the enum ranges from the config, but that would mean it is no longer an IntEnum.
        # Another option would be to just use the enum values directly, but that would mean it is no longer configurable.
        # For the time being, I'll just match the enum values to the config.
        HungerComponent: {
            "min": 0.0,
            "max": 10.0 - math.EPSILON,
            "time_to_starve": 10.0,
            "loss_rate_weight": 0.1,
            "gain_rate_weight": 0.1,
        },
        EnergyComponent: {
            "min": 0.0,
            "max": 10.0 - math.EPSILON,
            "idle_drain_rate": 0.1,
            "active_drain_rate": 0.5,
            "sleep_gain_rate": 2.0,
        },
        HealthComponent: {
            "min": 0.0,
            "max": 10.0,
            "regen_rate": 0.000001,
            "starvation_penalty": 0.1,
            "tired_penalty": 0.01,
            "hungry_penalty": 0.0,
            "well_fed_effect_duration": 10,
            "well_rested_effect_duration": 10,
        },
        LifeExpectancyComponent: {"max": 12 * 24 * 2, "avg": 8 * 24 * 2, "stddev": 2 * 24},
    },
    EntityTypes.PLANT: {
        GrowthComponent: {"min": 1.0, "max": 10.0},
        HydrationComponent: {"min": 0.0, "max": 10.0},
        EnergyComponent: {"min": 0.0, "max": 10.0},
    },
    EntityTypes.WEATHER: {
        WeatherConditionsComponent: {
            "precipitation": {"min": 0.0, "max": 100.0},
            "temperature": {"min": -50.0, "max": 50.0},
            "sunlight": {"min": 0.0, "max": 10.0},
        }
    },
}


class EntitiesFactory:
    @staticmethod
    def metadata_entity() -> tuple[str, list[Component]]:
        return EntityTypes.Metadata, [
            SummarizedStatsComponent(),
            StatsComponent(),  # Unified stats for all simulation metrics
        ]

    @staticmethod
    def create_config_entity() -> tuple[str, list[Component]]:
        return EntityTypes.CONFIG, [
            # we freeze the config to prevent accidental changes during simulation.
            EntitiesConfigComponent(deep_freeze(_ENTITY_CONFIG)),
        ]

    @staticmethod
    def create_world(name: str | None = None) -> tuple[str, Sequence[Component]]:
        return EntityTypes.WORLD, [
            NameComponent(name or "World"),
            LocalTimeComponent(hour=0, day=0, year=0, hours_in_a_day=24, days_in_a_year=65),
            DayNightCycleComponent(is_day=True, sunrise=6, sunset=18),
        ]

    @staticmethod
    def create_weather() -> tuple[str, list[Component]]:
        return EntityTypes.WEATHER, [
            WeatherConditionsComponent(0, 0, 0),
        ]

    @staticmethod
    def create_plant(name: str | None = None, position: tuple[int, int] | None = None) -> tuple[str, Sequence[Component]]:
        pos = position or (0, 0)
        return EntityTypes.PLANT, [
            NameComponent(name or "Plant"),
            PositionComponent(pos[0], pos[1]),
            GrowthComponent(1 / 3.0, 1.0),
            HydrationComponent(3.0),
            BirthdayComponent(0),
            PhotosynthesisComponent(True),
            EdibleComponent(nutrition=5.0, food_type=FoodType.PLANT),
        ]

    # TODO: sex is something that we need to probably assign from outside and not pick randomly here.
    # The reason is that we might want to "properly" simulate population distribution, and just picking randomly can create (temporary) imbalances.
    # This will be perceived as an unrealistic simulation, so need to artificially balance the population distribution.
    @staticmethod
    def create_animal(
        name: str | None = None,
        pre_existing_gender_dist: list[int] | None = None,
        family: FamilyComponent | None = None,
        birthday: int = 0,
        position: tuple[int, int] | None = None,
    ) -> tuple[str, Sequence[Component]]:
        gender = math.random_choice(
            ASSIGNABLE_GENDERS,
            [0.5, 0.5],
            math.RandomChoiceMode.SIMULATED,
            pre_existing_gender_dist,
        )
        life_expectancy = round(
            math.random_values_w_normal_distribution(
                0,
                _ENTITY_CONFIG[EntityTypes.ANIMAL][LifeExpectancyComponent]["max"],
                _ENTITY_CONFIG[EntityTypes.ANIMAL][LifeExpectancyComponent]["avg"],
                std_dev=_ENTITY_CONFIG[EntityTypes.ANIMAL][LifeExpectancyComponent]["stddev"],
            )[0]
        )
        name = name or str(uuid4())
        family_comp: FamilyComponent = family or FamilyComponent.default((0, 0))
        pos = position or (0, 0)

        return EntityTypes.ANIMAL, [
            # general components
            NameComponent(name),
            PositionComponent(pos[0], pos[1]),
            BirthdayComponent(birthday),
            LifeExpectancyComponent(life_expectancy),
            # state components
            HungerComponent(0.0),
            # TODO: currently, there is no proper check that prevents this from being set to 10 (which is technically above the max).
            # Need to figure out how to prevent this from happening.
            EnergyComponent(10.0 - math.EPSILON),
            HealthComponent(10.0 - math.EPSILON),
            WellbeingComponent.default(),
            # social components
            family_comp,
            # higher level functions
            ReproductiveComponent(
                gender, 1, _ENTITY_CONFIG[EntityTypes.ANIMAL][ReproductiveComponent]["fertility_age"]
            ),
            BrainComponent(BrainType.ANIMAL, PrimitiveGoal.IDLE, None),
            MemoryComponent(MemoryData()),
            ActivityComponent.default(),
            # Food chain components
            EdibleComponent(nutrition=10.0, food_type=FoodType.MEAT),  # Animals provide more nutrition as meat
            DietComponent(diet_type=DietType.HERBIVORE),  # Animals are herbivores (eat only plants)
        ]

    @staticmethod
    def create_human(
        name: str | None = None,
        pre_existing_gender_dist: list[int] | None = None,
        family: FamilyComponent | None = None,
        birthday: int = 0,
        position: tuple[int, int] | None = None,
    ) -> tuple[str, Sequence[Component]]:
        gender = math.random_choice(
            ASSIGNABLE_GENDERS,
            [0.5, 0.5],
            math.RandomChoiceMode.SIMULATED,
            pre_existing_gender_dist,
        )
        life_expectancy = round(
            math.random_values_w_normal_distribution(
                0,
                _ENTITY_CONFIG[EntityTypes.HUMAN][LifeExpectancyComponent]["max"],
                _ENTITY_CONFIG[EntityTypes.HUMAN][LifeExpectancyComponent]["avg"],
                std_dev=_ENTITY_CONFIG[EntityTypes.HUMAN][LifeExpectancyComponent]["stddev"],
            )[0]
        )
        name = name or str(uuid4())
        family_comp: FamilyComponent = family or FamilyComponent.default((0, 0))
        pos = position or (0, 0)

        return EntityTypes.HUMAN, [
            # general components
            NameComponent(name),
            PositionComponent(pos[0], pos[1]),
            BirthdayComponent(birthday),
            LifeExpectancyComponent(life_expectancy),
            # state components
            HungerComponent(0.0),
            EnergyComponent(10.0 - math.EPSILON),
            HealthComponent(10.0 - math.EPSILON),
            WellbeingComponent.default(),
            # social components
            family_comp,
            # higher level functions
            ReproductiveComponent(gender, 1, _ENTITY_CONFIG[EntityTypes.HUMAN][ReproductiveComponent]["fertility_age"]),
            BrainComponent(BrainType.ANIMAL, PrimitiveGoal.IDLE, None),  # Using ANIMAL brain type for now
            MemoryComponent(MemoryData()),
            ActivityComponent.default(),
            # Food chain components
            EdibleComponent(
                nutrition=4.0, food_type=FoodType.MEAT
            ),  # Humans provide meat nutrition (for cannibalism if enabled)
            DietComponent(diet_type=DietType.OMNIVORE),  # Humans are omnivores (can eat both plants and animals)
        ]

    @staticmethod
    def gender_balanced_spawner(
        create_fn: Callable[..., tuple[str, Sequence[Component]]],
        *,
        prefix: str,
    ) -> Callable[..., tuple[str, Sequence[Component]]]:
        """
        Returns a closure that spawns entities with near-uniform gender
        distribution each time it is called. Accepts **kwargs to pass through
        to the create function (e.g. position).

        Example
        -------
        animal_spawner = EntitiesFactory.gender_balanced_spawner(
            EntitiesFactory.create_animal, prefix="Animal"
        )
        etype, comps = animal_spawner(position=(5, 5))
        """
        counter = 0
        gender_counts = [0, 0]  # [M, F]

        def _spawn(**kwargs: Any) -> tuple[str, Sequence[Component]]:
            nonlocal counter, gender_counts
            name = f"{prefix}_{counter}"
            counter += 1
            etype, comps = create_fn(name, gender_counts, **kwargs)
            repro = next(c for c in comps if isinstance(c, ReproductiveComponent))
            gender_idx = 1 if repro.gender == "F" else 0
            gender_counts[gender_idx] += 1
            return etype, comps

        return _spawn
