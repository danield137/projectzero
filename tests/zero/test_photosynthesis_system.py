from sim.ecs.core import ECS
from zero.simulation.components import (
    DayNightCycleComponent,
    GrowthComponent,
    HealthComponent,
    PhotosynthesisComponent,
    WeatherConditionsComponent,
)
from zero.simulation.entities import EntitiesFactory
from zero.simulation.systems.photosynthesis import PhotosynthesisSystem


def test_photosynthesis_during_day(ecs: ECS) -> None:
    """Test that plants photosynthesize during daylight."""
    # Arrange
    ps = PhotosynthesisSystem()
    ps.init_system(ecs)

    # Create a plant entity
    plant_id = ecs.create_entity(*EntitiesFactory.create_plant("Test_Plant"))

    # Ensure it's daytime
    world_id = ecs.create_entity(*EntitiesFactory.create_world("Test_World"))
    day_night = ecs.get_typed_component(world_id, DayNightCycleComponent)
    day_night.is_day = True
    ecs.update_typed_component(world_id, day_night)

    # Create weather with sunlight
    weather_id = ecs.create_entity("Weather")
    ecs.add_typed_component(weather_id, WeatherConditionsComponent(precipitation=0, temperature=25, sunlight=10))

    # Verify plant has growth component
    ecs.get_typed_component(plant_id, GrowthComponent)

    # Act
    ps.update(1)

    # Assert
    ps_after = ecs.get_typed_component(plant_id, PhotosynthesisComponent)
    assert ps_after.value == True, "Plant should be photosynthesizing during daylight"


def test_no_photosynthesis_at_night(ecs: ECS) -> None:
    """Test that plants don't photosynthesize at night."""
    # Arrange
    ps = PhotosynthesisSystem()
    ps.init_system(ecs)

    # Create a plant entity
    plant_id = ecs.create_entity(*EntitiesFactory.create_plant("Test_Plant"))

    # Set to night time
    world_id = ecs.create_entity(*EntitiesFactory.create_world("Test_World"))
    day_night = ecs.get_typed_component(world_id, DayNightCycleComponent)
    day_night.is_day = False
    ecs.update_typed_component(world_id, day_night)

    # Create weather with sunlight (even though it's night)
    weather_id = ecs.create_entity("Weather")
    ecs.add_typed_component(
        weather_id, WeatherConditionsComponent(precipitation=0, temperature=25, sunlight=0)  # No sunlight at night
    )

    # Act
    ps.update(1)

    # Assert
    ps_after = ecs.get_typed_component(plant_id, PhotosynthesisComponent)
    assert ps_after.value == False, "Plant should not be photosynthesizing at night"


def test_weather_affects_photosynthesis(ecs: ECS) -> None:
    """Test that weather conditions affect photosynthesis efficiency."""
    # Arrange
    ps = PhotosynthesisSystem()
    ps.init_system(ecs)

    # Create two plant entities
    plant1_id = ecs.create_entity(*EntitiesFactory.create_plant("Plant_Good_Weather"))
    plant2_id = ecs.create_entity(*EntitiesFactory.create_plant("Plant_Bad_Weather"))

    # Ensure it's daytime
    world_id = ecs.create_entity(*EntitiesFactory.create_world("Test_World"))
    day_night = ecs.get_typed_component(world_id, DayNightCycleComponent)
    day_night.is_day = True
    ecs.update_typed_component(world_id, day_night)

    # Create good weather conditions for plant1
    weather1_id = ecs.create_entity("Weather1")
    ecs.add_typed_component(
        weather1_id,
        WeatherConditionsComponent(
            precipitation=0, temperature=25, sunlight=10  # No rain  # Warm temperature  # Maximum sunlight
        ),
    )

    # Create poor weather conditions for plant2
    weather2_id = ecs.create_entity("Weather2")
    ecs.add_typed_component(
        weather2_id,
        WeatherConditionsComponent(
            precipitation=10, temperature=5, sunlight=2  # Heavy rain  # Cold temperature  # Minimal sunlight
        ),
    )

    # Act
    ps.update(1)

    # Assert
    ps1_after = ecs.get_typed_component(plant1_id, PhotosynthesisComponent)
    ps2_after = ecs.get_typed_component(plant2_id, PhotosynthesisComponent)

    # Both should photosynthesize, but with different efficiency based on weather
    assert ps1_after.value == True, "Plant should photosynthesize with good weather"
    assert ps2_after.value == True, "Plant should photosynthesize even with poor weather if there's some sunlight"


def test_animals_dont_photosynthesize(ecs: ECS) -> None:
    """Test that animals (entities without photosynthesis component) don't photosynthesize."""
    # Arrange
    ps = PhotosynthesisSystem()
    ps.init_system(ecs)

    # Create an animal entity
    animal_id = ecs.create_entity(*EntitiesFactory.create_animal("Test_Animal"))

    # Ensure it's daytime
    world_id = ecs.create_entity(*EntitiesFactory.create_world("Test_World"))
    day_night = ecs.get_typed_component(world_id, DayNightCycleComponent)
    day_night.is_day = True
    ecs.update_typed_component(world_id, day_night)

    # Create weather with sunlight
    weather_id = ecs.create_entity("Weather")
    ecs.add_typed_component(weather_id, WeatherConditionsComponent(precipitation=0, temperature=25, sunlight=10))

    # Get the initial health
    initial_health = ecs.get_typed_component(animal_id, HealthComponent).value

    # Act
    ps.update(1)

    # Assert
    health_after = ecs.get_typed_component(animal_id, HealthComponent).value
    assert health_after == initial_health, "Animal health should not change due to photosynthesis"
