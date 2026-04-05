from zero.simulation.components import EntityStatsComponent
from zero.simulation.functional.stat_ops import (
    EntityType,
    avg_energy,
    avg_hunger,
    goal_ratio,
    inc_population,
    record_energy,
    record_goal,
    record_hunger,
)


def test_entity_stats_component_basic():
    """Test basic functionality of EntityStatsComponent with stat_ops helpers."""
    stats = EntityStatsComponent()

    # Test population tracking
    inc_population(stats, "Animal")
    inc_population(stats, "Animal")
    inc_population(stats, "Human")

    assert stats.population["Animal"] == 2
    assert stats.population["Human"] == 1

    # Test hunger recording and averaging
    record_hunger(stats, "Animal", 5.0)
    record_hunger(stats, "Animal", 7.0)
    record_hunger(stats, "Human", 3.0)

    assert avg_hunger(stats, "Animal") == 6.0  # (5.0 + 7.0) / 2
    assert avg_hunger(stats, "Human") == 3.0  # 3.0 / 1

    # Test energy recording and averaging
    record_energy(stats, "Animal", 8.0)
    record_energy(stats, "Animal", 4.0)

    assert avg_energy(stats, "Animal") == 6.0  # (8.0 + 4.0) / 2

    # Test goal tracking
    record_goal(stats, "Animal", "EAT")
    record_goal(stats, "Animal", "SLEEP")
    record_goal(stats, "Animal", "EAT")

    assert goal_ratio(stats, "Animal", "EAT") == 2 / 3  # 2 out of 3
    assert goal_ratio(stats, "Animal", "SLEEP") == 1 / 3  # 1 out of 3

    # Test reset
    stats.reset()
    assert stats.population["Animal"] == 0
    assert stats.hunger_sum["Animal"] == 0.0
    assert avg_hunger(stats, "Animal") == 0.0  # Should handle zero population


def test_entity_type_validation():
    """Test that our EntityType Literal works correctly."""
    stats = EntityStatsComponent()

    # These should work without type errors
    animal: EntityType = "Animal"
    human: EntityType = "Human"
    plant: EntityType = "Plant"

    record_hunger(stats, animal, 5.0)
    record_hunger(stats, human, 6.0)
    record_energy(stats, plant, 7.0)

    assert stats.hunger_sum["Animal"] == 5.0
    assert stats.hunger_sum["Human"] == 6.0
    assert stats.energy_sum["Plant"] == 7.0
