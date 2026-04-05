from zero.ai.actions import EatAction, MatingAction, SleepAction
from simz.ecs.core import ECS
from zero.simulation.components import (
    ActivityComponent,
    BrainComponent,
    EatingActivity,
    IdleActivity,
    MatingActivity,
    SleepingActivity,
)
from zero.simulation.entities import EntitiesFactory
from zero.simulation.systems.actuation import ActuationSystem


def test_validate_does_not_raise(ecs: ECS):
    """Test that the ActuationSystem has all required action handlers."""
    # Arrange
    actuation_system = ActuationSystem()
    actuation_system.init_system(ecs)

    # Act & Assert
    assert actuation_system.validate()


def test_eat_action_does_update_activity(ecs: ECS):
    """Test that EatAction updates the ActivityComponent correctly."""
    # Arrange
    actuation_system = ActuationSystem()
    actuation_system.init_system(ecs)

    # Create entity with initial idle activity
    eid = ecs.create_entity(*EntitiesFactory.create_animal("Animal_1"))
    activity = ecs.get_typed_component(eid, ActivityComponent)
    activity.activity = IdleActivity(since=0)
    ecs.update_typed_component(eid, activity)

    # Set up brain with eat action
    food_id = 123  # Some arbitrary food entity ID
    brain = ecs.get_typed_component(eid, BrainComponent)
    brain.current_plan = [EatAction(food_id=food_id)]
    ecs.update_typed_component(eid, brain)

    # Act
    simulation_time = 42  # Arbitrary timestamp
    actuation_system.update(simulation_time)

    # Assert
    activity = ecs.get_typed_component(eid, ActivityComponent)
    assert activity.activity.is_eating()
    eating_activity = activity.activity
    assert isinstance(eating_activity, EatingActivity)
    assert eating_activity.food == food_id
    assert eating_activity.since == simulation_time


def test_eat_action_preserves_existing_food(ecs: ECS):
    """Test that EatAction doesn't change the activity if already eating the same food."""
    # Arrange
    actuation_system = ActuationSystem()
    actuation_system.init_system(ecs)

    # Create entity already eating
    eid = ecs.create_entity(*EntitiesFactory.create_animal("Animal_1"))
    food_id = 123
    simulation_time = 42
    activity = ecs.get_typed_component(eid, ActivityComponent)
    activity.activity = EatingActivity(food=food_id, since=simulation_time)
    ecs.update_typed_component(eid, activity)

    # Set up brain with eat action for same food
    brain = ecs.get_typed_component(eid, BrainComponent)
    brain.current_plan = [EatAction(food_id=food_id)]
    ecs.update_typed_component(eid, brain)

    # Act
    new_time = simulation_time + 10
    actuation_system.update(new_time)

    # Assert - activity should be unchanged
    activity = ecs.get_typed_component(eid, ActivityComponent)
    assert activity.activity.is_eating()
    eating_activity = activity.activity
    assert isinstance(eating_activity, EatingActivity)
    assert eating_activity.food == food_id
    assert eating_activity.since == simulation_time  # Original timestamp preserved


def test_sleep_action_does_update_activity(ecs: ECS):
    """Test that SleepAction updates the ActivityComponent correctly."""
    # Arrange
    actuation_system = ActuationSystem()
    actuation_system.init_system(ecs)

    # Create entity with initial idle activity
    eid = ecs.create_entity(*EntitiesFactory.create_animal("Animal_1"))
    activity = ecs.get_typed_component(eid, ActivityComponent)
    activity.activity = IdleActivity(since=0)
    ecs.update_typed_component(eid, activity)

    # Set up brain with sleep action
    brain = ecs.get_typed_component(eid, BrainComponent)
    brain.current_plan = [SleepAction()]
    ecs.update_typed_component(eid, brain)

    # Act
    simulation_time = 42  # Arbitrary timestamp
    actuation_system.update(simulation_time)

    # Assert
    activity = ecs.get_typed_component(eid, ActivityComponent)
    assert activity.activity.is_sleeping()
    sleeping_activity = activity.activity
    assert isinstance(sleeping_activity, SleepingActivity)
    assert sleeping_activity.since == simulation_time
    # TODO: assert consciousness.is_awake is False when ConsciousnessComponent is implemented


def test_mating_action_sets_mating_activity(ecs: ECS):
    """Test that MatingAction updates the ActivityComponent correctly."""
    # Arrange
    actuation_system = ActuationSystem()
    actuation_system.init_system(ecs)

    # Create entity with initial idle activity
    female_eid = ecs.create_entity(*EntitiesFactory.create_animal("Female_1"))
    male_eid = ecs.create_entity(*EntitiesFactory.create_animal("Male_1"))
    activity = ecs.get_typed_component(female_eid, ActivityComponent)
    activity.activity = IdleActivity(since=0)
    ecs.update_typed_component(female_eid, activity)

    # Set up brain with mating action
    brain = ecs.get_typed_component(female_eid, BrainComponent)
    brain.current_plan = [MatingAction(partner_id=male_eid)]
    ecs.update_typed_component(female_eid, brain)

    # Act
    simulation_time = 42  # Arbitrary timestamp
    actuation_system.update(simulation_time)

    # Assert
    activity = ecs.get_typed_component(female_eid, ActivityComponent)
    assert isinstance(activity.activity, MatingActivity), "Activity should be MatingActivity"
    mating_activity = activity.activity
    assert mating_activity.mate == male_eid, "MatingActivity should target correct mate"
    assert mating_activity.since == simulation_time, "MatingActivity should have correct timestamp"


def test_sleep_preserves_existing_sleep(ecs: ECS):
    """Test that SleepAction doesn't change activity if already sleeping."""
    # Arrange
    actuation_system = ActuationSystem()
    actuation_system.init_system(ecs)

    # Create entity already sleeping
    eid = ecs.create_entity(*EntitiesFactory.create_animal("Animal_1"))
    simulation_time = 42
    activity = ecs.get_typed_component(eid, ActivityComponent)
    activity.activity = SleepingActivity(since=simulation_time)
    ecs.update_typed_component(eid, activity)

    # Set up brain with sleep action
    brain = ecs.get_typed_component(eid, BrainComponent)
    brain.current_plan = [SleepAction()]
    ecs.update_typed_component(eid, brain)

    # Act
    new_time = simulation_time + 10
    actuation_system.update(new_time)

    # Assert - activity should be unchanged
    activity = ecs.get_typed_component(eid, ActivityComponent)
    assert activity.activity.is_sleeping()
    sleeping_activity = activity.activity
    assert isinstance(sleeping_activity, SleepingActivity)
    assert sleeping_activity.since == simulation_time  # Original timestamp preserved
