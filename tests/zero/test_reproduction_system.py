import pytest

from simz.ecs.core import ECS
from zero.simulation.components import (
    ActivityComponent,
    EnergyComponent,
    FamilyComponent,
    IdleActivity,
    MatingActivity,
    PregnancyComponent,
    ReproductiveComponent,
    WellbeingComponent,
)
from zero.simulation.entities import EntitiesFactory
from zero.simulation.systems.reproduction import ReproductionSystem


def test_pregnancy_initiation(ecs: ECS):
    """Test that female becomes pregnant after mating."""
    # Arrange
    ecs = ECS()
    rs = ReproductionSystem()
    rs.init_system(ecs)

    # Create male and female animals
    male_id = ecs.create_entity(*EntitiesFactory.create_animal("Male_Animal"))
    female_id = ecs.create_entity(*EntitiesFactory.create_animal("Female_Animal"))

    # Configure reproductive components
    male_repro = ecs.get_typed_component(male_id, ReproductiveComponent)
    female_repro = ecs.get_typed_component(female_id, ReproductiveComponent)

    male_repro.gender = "M"
    female_repro.gender = "F"
    male_repro.fertility = 1.0
    female_repro.fertility = 1.0

    ecs.update_typed_component(male_id, male_repro)
    ecs.update_typed_component(female_id, female_repro)

    # Set up as mating pair
    male_family = ecs.get_typed_component(male_id, FamilyComponent)
    female_family = ecs.get_typed_component(female_id, FamilyComponent)
    male_family.mate = female_id
    female_family.mate = male_id
    ecs.update_typed_component(male_id, male_family)
    ecs.update_typed_component(female_id, female_family)

    # Set up energy and activity for mating
    male_energy = ecs.get_typed_component(male_id, EnergyComponent)
    female_energy = ecs.get_typed_component(female_id, EnergyComponent)
    male_energy.value = 10.0
    female_energy.value = 10.0
    ecs.update_typed_component(male_id, male_energy)
    ecs.update_typed_component(female_id, female_energy)

    # Set both partners in mating activity
    male_activity = ecs.get_typed_component(male_id, ActivityComponent)
    female_activity = ecs.get_typed_component(female_id, ActivityComponent)
    male_activity.activity = MatingActivity(mate=female_id, since=0)
    female_activity.activity = MatingActivity(mate=male_id, since=0)
    ecs.update_typed_component(male_id, male_activity)
    ecs.update_typed_component(female_id, female_activity)

    # Initial check - female shouldn't be pregnant yet
    female_wellbeing = ecs.get_typed_component(female_id, WellbeingComponent)
    assert female_wellbeing.pregnancy is None, "Female should not be pregnant before mating"

    # Act
    rs.update(1)  # First simulation step, mating occurs

    # Assert
    female_wellbeing = ecs.get_typed_component(female_id, WellbeingComponent)
    assert female_wellbeing.pregnancy is not None, "Female should be pregnant after mating"
    assert isinstance(female_wellbeing.pregnancy, PregnancyComponent), "Pregnancy component should be added"
    assert female_wellbeing.pregnancy.mate == male_id, "Mate ID should be stored in pregnancy"


@pytest.mark.skip("Mating isn't implemented in the planing phase yet, so this test is not applicable.")
def test_both_partners_need_mating_activity(ecs: ECS):
    """Test that both partners must be in MatingActivity for pregnancy to occur."""
    # Arrange
    ecs = ECS()
    rs = ReproductionSystem()
    rs.init_system(ecs)

    # Create male and female animals
    male_id = ecs.create_entity(*EntitiesFactory.create_animal("Male_Animal"))
    female_id = ecs.create_entity(*EntitiesFactory.create_animal("Female_Animal"))

    # Configure reproductive components with high fertility
    male_repro = ecs.get_typed_component(male_id, ReproductiveComponent)
    female_repro = ecs.get_typed_component(female_id, ReproductiveComponent)
    male_repro.gender = "M"
    female_repro.gender = "F"
    male_repro.fertility = 1.0
    female_repro.fertility = 1.0
    ecs.update_typed_component(male_id, male_repro)
    ecs.update_typed_component(female_id, female_repro)

    # Set up as mating pair
    male_family = ecs.get_typed_component(male_id, FamilyComponent)
    female_family = ecs.get_typed_component(female_id, FamilyComponent)
    male_family.mate = female_id
    female_family.mate = male_id
    ecs.update_typed_component(male_id, male_family)
    ecs.update_typed_component(female_id, female_family)

    # Set up sufficient energy
    male_energy = ecs.get_typed_component(male_id, EnergyComponent)
    female_energy = ecs.get_typed_component(female_id, EnergyComponent)
    male_energy.value = 10.0
    female_energy.value = 10.0
    ecs.update_typed_component(male_id, male_energy)
    ecs.update_typed_component(female_id, female_energy)

    # Test Case 1: Only female in mating activity
    female_activity = ecs.get_typed_component(female_id, ActivityComponent)
    female_activity.activity = MatingActivity(mate=male_id, since=0)
    ecs.update_typed_component(female_id, female_activity)
    rs.update(1)

    female_wellbeing = ecs.get_typed_component(female_id, WellbeingComponent)
    assert female_wellbeing.pregnancy is None, "Pregnancy should not occur when only female is in mating activity"

    # Test Case 2: Only male in mating activity
    female_activity.activity = IdleActivity(since=0)
    male_activity = ecs.get_typed_component(male_id, ActivityComponent)
    male_activity.activity = MatingActivity(mate=female_id, since=0)
    ecs.update_typed_component(female_id, female_activity)
    ecs.update_typed_component(male_id, male_activity)
    rs.update(2)

    female_wellbeing = ecs.get_typed_component(female_id, WellbeingComponent)
    assert female_wellbeing.pregnancy is None, "Pregnancy should not occur when only male is in mating activity"

    # Test Case 3: Both in mating activity
    female_activity.activity = MatingActivity(mate=male_id, since=0)
    ecs.update_typed_component(female_id, female_activity)
    rs.update(3)

    female_wellbeing = ecs.get_typed_component(female_id, WellbeingComponent)
    assert female_wellbeing.pregnancy is not None, "Pregnancy should occur when both partners are in mating activity"


def test_no_self_mating(ecs: ECS):
    """Test that animals cannot mate with themselves."""
    # Arrange
    ecs = ECS()
    rs = ReproductionSystem()
    rs.init_system(ecs)

    # Create a single animal
    animal_id = ecs.create_entity(*EntitiesFactory.create_animal("Lone_Animal"))

    # Configure reproductive component with high fertility
    repro = ecs.get_typed_component(animal_id, ReproductiveComponent)
    repro.fertility = 1.0
    ecs.update_typed_component(animal_id, repro)

    # Try to set mate to self (should not be allowed in real system)
    family = ecs.get_typed_component(animal_id, FamilyComponent)
    family.mate = animal_id
    ecs.update_typed_component(animal_id, family)

    # Act
    rs.update(1)

    # Assert
    wellbeing = ecs.get_typed_component(animal_id, WellbeingComponent)
    assert wellbeing.pregnancy is None, "Animal should not become pregnant through self-mating"


def test_pregnancy_activity_cleared_once(ecs: ECS):
    """Test that pregnancy sets activity to idle and it stays idle."""
    # Arrange
    rs = ReproductionSystem()
    rs.init_system(ecs)

    # Create male and female animals of breeding age
    male_id = ecs.create_entity(*EntitiesFactory.create_animal("Male_Animal"))
    female_id = ecs.create_entity(*EntitiesFactory.create_animal("Female_Animal"))

    # Configure reproductive components
    male_repro = ecs.get_typed_component(male_id, ReproductiveComponent)
    female_repro = ecs.get_typed_component(female_id, ReproductiveComponent)
    male_repro.gender = "M"
    female_repro.gender = "F"
    ecs.update_typed_component(male_id, male_repro)
    ecs.update_typed_component(female_id, female_repro)

    # Set up energy and hunger for mating
    male_energy = ecs.get_typed_component(male_id, EnergyComponent)
    female_energy = ecs.get_typed_component(female_id, EnergyComponent)
    male_energy.value = 10.0
    female_energy.value = 10.0
    ecs.update_typed_component(male_id, male_energy)
    ecs.update_typed_component(female_id, female_energy)

    # Set up mating activity for both partners
    female_activity = ecs.get_typed_component(female_id, ActivityComponent)
    male_activity = ecs.get_typed_component(male_id, ActivityComponent)
    female_activity.activity = MatingActivity(mate=male_id, since=0)
    male_activity.activity = MatingActivity(mate=female_id, since=0)
    ecs.update_typed_component(female_id, female_activity)
    ecs.update_typed_component(male_id, male_activity)

    # Link as mates
    male_family = ecs.get_typed_component(male_id, FamilyComponent)
    female_family = ecs.get_typed_component(female_id, FamilyComponent)
    male_family.mate = female_id
    female_family.mate = male_id
    ecs.update_typed_component(male_id, male_family)
    ecs.update_typed_component(female_id, female_family)

    # Initial check
    female_wellbeing = ecs.get_typed_component(female_id, WellbeingComponent)
    assert female_wellbeing.pregnancy is None, "Female should not be pregnant initially"

    # Act - First update
    rs.update(1)

    # Assert pregnancy and idle activity after first update
    female_wellbeing = ecs.get_typed_component(female_id, WellbeingComponent)
    female_activity = ecs.get_typed_component(female_id, ActivityComponent)
    assert female_wellbeing.pregnancy is not None, "Female should be pregnant after mating"
    assert isinstance(female_activity.activity, IdleActivity), "Activity should be idle after pregnancy"

    # Act - Second update to verify activity stays idle
    rs.update(2)

    # Assert activity remains idle
    female_activity = ecs.get_typed_component(female_id, ActivityComponent)
    assert isinstance(female_activity.activity, IdleActivity), "Activity should remain idle after second update"


def test_fertility_affects_pregnancy_chance(ecs: ECS):
    """Test that fertility level affects chance of pregnancy."""
    # Arrange
    ecs = ECS()
    rs = ReproductionSystem()
    rs.init_system(ecs)

    # Create two pairs of animals with different fertility levels
    male1_id = ecs.create_entity(*EntitiesFactory.create_animal("High_Fertility_Male"))
    female1_id = ecs.create_entity(*EntitiesFactory.create_animal("High_Fertility_Female"))
    male2_id = ecs.create_entity(*EntitiesFactory.create_animal("Low_Fertility_Male"))
    female2_id = ecs.create_entity(*EntitiesFactory.create_animal("Low_Fertility_Female"))

    # Configure high fertility pair
    high_male_repro = ecs.get_typed_component(male1_id, ReproductiveComponent)
    high_female_repro = ecs.get_typed_component(female1_id, ReproductiveComponent)
    high_male_repro.gender = "M"
    high_female_repro.gender = "F"
    high_male_repro.fertility = 1.0
    high_female_repro.fertility = 1.0
    ecs.update_typed_component(male1_id, high_male_repro)
    ecs.update_typed_component(female1_id, high_female_repro)

    # Configure low fertility pair
    low_male_repro = ecs.get_typed_component(male2_id, ReproductiveComponent)
    low_female_repro = ecs.get_typed_component(female2_id, ReproductiveComponent)
    low_male_repro.gender = "M"
    low_female_repro.gender = "F"
    low_male_repro.fertility = 0.1
    low_female_repro.fertility = 0.1
    ecs.update_typed_component(male2_id, low_male_repro)
    ecs.update_typed_component(female2_id, low_female_repro)

    # Set up mating pairs
    high_male_family = ecs.get_typed_component(male1_id, FamilyComponent)
    high_female_family = ecs.get_typed_component(female1_id, FamilyComponent)
    high_male_family.mate = female1_id
    high_female_family.mate = male1_id
    ecs.update_typed_component(male1_id, high_male_family)
    ecs.update_typed_component(female1_id, high_female_family)

    low_male_family = ecs.get_typed_component(male2_id, FamilyComponent)
    low_female_family = ecs.get_typed_component(female2_id, FamilyComponent)
    low_male_family.mate = female2_id
    low_female_family.mate = male2_id
    ecs.update_typed_component(male2_id, low_male_family)
    ecs.update_typed_component(female2_id, low_female_family)

    # Set up energy for both pairs
    high_male_energy = ecs.get_typed_component(male1_id, EnergyComponent)
    high_female_energy = ecs.get_typed_component(female1_id, EnergyComponent)
    low_male_energy = ecs.get_typed_component(male2_id, EnergyComponent)
    low_female_energy = ecs.get_typed_component(female2_id, EnergyComponent)
    high_male_energy.value = 10.0
    high_female_energy.value = 10.0
    low_male_energy.value = 10.0
    low_female_energy.value = 10.0
    ecs.update_typed_component(male1_id, high_male_energy)
    ecs.update_typed_component(female1_id, high_female_energy)
    ecs.update_typed_component(male2_id, low_male_energy)
    ecs.update_typed_component(female2_id, low_female_energy)

    successful_attempts_high = 0
    successful_attempts_low = 0

    # Run multiple attempts to reduce randomness impact
    for i in range(100):  # Increased iterations for more reliable results
        # Reset pregnancy status and set mating activity
        high_female_wellbeing = ecs.get_typed_component(female1_id, WellbeingComponent)
        low_female_wellbeing = ecs.get_typed_component(female2_id, WellbeingComponent)
        high_female_wellbeing.pregnancy = None
        low_female_wellbeing.pregnancy = None
        ecs.update_typed_component(female1_id, high_female_wellbeing)
        ecs.update_typed_component(female2_id, low_female_wellbeing)

        # Set both pairs in mating activity
        high_male_activity = ecs.get_typed_component(male1_id, ActivityComponent)
        high_female_activity = ecs.get_typed_component(female1_id, ActivityComponent)
        low_male_activity = ecs.get_typed_component(male2_id, ActivityComponent)
        low_female_activity = ecs.get_typed_component(female2_id, ActivityComponent)

        high_male_activity.activity = MatingActivity(mate=female1_id, since=i)
        high_female_activity.activity = MatingActivity(mate=male1_id, since=i)
        low_male_activity.activity = MatingActivity(mate=female2_id, since=i)
        low_female_activity.activity = MatingActivity(mate=male2_id, since=i)

        ecs.update_typed_component(male1_id, high_male_activity)
        ecs.update_typed_component(female1_id, high_female_activity)
        ecs.update_typed_component(male2_id, low_male_activity)
        ecs.update_typed_component(female2_id, low_female_activity)

        # Try mating
        rs.update(i)

        # Check results
        high_female_wellbeing = ecs.get_typed_component(female1_id, WellbeingComponent)
        low_female_wellbeing = ecs.get_typed_component(female2_id, WellbeingComponent)

        if high_female_wellbeing.pregnancy is not None:
            successful_attempts_high += 1
        if low_female_wellbeing.pregnancy is not None:
            successful_attempts_low += 1

    # Assert
    # High fertility pair (1.0 * 1.0 = 100% chance) should have significantly more pregnancies
    # than low fertility pair (0.1 * 0.1 = 1% chance)
    assert successful_attempts_high > successful_attempts_low * 3, (
        "High fertility pair should have significantly more pregnancies. "
        f"High fertility successes: {successful_attempts_high}, "
        f"Low fertility successes: {successful_attempts_low}"
    )
