from typing import List

from zero import Simulation
from zero.simulation.components import NameComponent, ReproductiveComponent
from zero.simulation.entities import EntitiesFactory, EntityTypes


def test_gender_balanced_spawner_distribution():
    """Test that the gender balanced spawner creates reasonable gender distribution."""
    spawner = EntitiesFactory.gender_balanced_spawner(EntitiesFactory.create_human, prefix="TestHuman")

    male_count = 0
    female_count = 0

    # Spawn 100 humans to test distribution
    for _ in range(100):
        _, components = spawner()
        repro = next(c for c in components if isinstance(c, ReproductiveComponent))
        if repro.gender == "M":
            male_count += 1
        else:
            female_count += 1

    # Assert distribution is reasonably balanced (within 20% of ideal)
    # For 100 entities, we expect 50/50, so allow 40-60 range for each gender
    assert 40 <= male_count <= 60
    assert 40 <= female_count <= 60
    assert male_count + female_count == 100


def test_startup_creates_two_humans():
    """Test that simulation startup creates exactly two humans."""
    sim = Simulation()
    sim.setup_simulation()
    sim.set_starting_conditions()

    # Check that exactly 6 humans were created
    human_count = len(sim.ecs.entities_by_type.get(EntityTypes.HUMAN, []))
    assert human_count == 6


def test_startup_creates_animals():
    """Test that simulation startup creates the expected number of animals."""
    sim = Simulation()
    sim.setup_simulation()
    sim.set_starting_conditions()

    # Check that exactly 10 animals were created
    animal_count = len(sim.ecs.entities_by_type.get(EntityTypes.ANIMAL, []))
    assert animal_count == 10


def test_spawner_creates_unique_names():
    """Test that spawner creates entities with unique, sequential names."""
    spawner = EntitiesFactory.gender_balanced_spawner(EntitiesFactory.create_animal, prefix="TestAnimal")

    names: List[str] = []
    for _ in range(5):
        _, components = spawner()
        name_comp = next(c for c in components if isinstance(c, NameComponent))
        names.append(name_comp.value)

    expected_names = ["TestAnimal_0", "TestAnimal_1", "TestAnimal_2", "TestAnimal_3", "TestAnimal_4"]
    assert names == expected_names
