import pytest

from zero.ai.brains import Brain, BrainType, get_predefined_brain


def test_get_predefined_brain_valid_types():
    """Test getting predefined brains with valid types."""
    # Act
    animal_brain = get_predefined_brain(BrainType.ANIMAL)
    human_brain = get_predefined_brain(BrainType.HUMAN)

    # Assert
    assert isinstance(animal_brain, Brain), "Should return a Brain instance for ANIMAL type"
    assert isinstance(human_brain, Brain), "Should return a Brain instance for HUMAN type"
    assert animal_brain.goal_selector is not None, "Animal brain should have a goal selector"
    assert animal_brain.planner is not None, "Animal brain should have a planner"
    assert human_brain.goal_selector is not None, "Human brain should have a goal selector"
    assert human_brain.planner is not None, "Human brain should have a planner"


def test_get_predefined_brain_invalid_type():
    """Test getting a brain with an invalid type raises an error."""
    # Act & Assert
    with pytest.raises(ValueError) as excinfo:
        get_predefined_brain("NonExistentBrainType")

    # Verify the error message
    assert "Unknown brain type" in str(excinfo.value), "Error message should mention unknown brain type"


def test_brain_types_consistency():
    """Test that all defined brain types have implementations."""
    # Arrange
    all_brain_types = [BrainType.ANIMAL, BrainType.HUMAN]

    # Act & Assert
    for brain_type in all_brain_types:
        brain = get_predefined_brain(brain_type)
        assert brain is not None, f"Brain type {brain_type} should have an implementation"
        assert hasattr(brain, "goal_selector"), "Brain should have a goal_selector"
        assert hasattr(brain, "planner"), "Brain should have a planner"
