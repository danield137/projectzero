import numpy as np

from tigen.common.math import (
    RandomChoiceMode,
    clamp,
    cosine,
    probabilistic_event,
    random_choice,
    random_values_w_normal_distribution,
    sigmoid_probability,
)


def test_clamp():
    """Test the clamp function with various inputs."""
    # Test within range
    assert clamp(5, 0, 10) == 5

    # Test below minimum
    assert clamp(-1, 0, 10) == 0

    # Test above maximum
    assert clamp(15, 0, 10) == 10

    # Test with float input
    assert clamp(5.5, 0, 10) == 5

    # Test with equal min and max
    assert clamp(7, 5, 5) == 5


def test_random_values_w_normal_distribution():
    """Test the random values with normal distribution function."""
    # Test basic functionality
    values = random_values_w_normal_distribution(0, 10, 5, count=100)
    assert values.size == 100
    assert np.all((0 <= values) & (values <= 10))

    # Test with different std_dev
    values_narrow = random_values_w_normal_distribution(0, 10, 5, count=100, std_dev=0.1)
    values_wide = random_values_w_normal_distribution(0, 10, 5, count=100, std_dev=5.0)

    # The narrow distribution should have more values close to the center
    assert abs(np.mean(values_narrow) - 5) < abs(np.mean(values_wide) - 5)


def test_random_choice_true_mode():
    """Test random_choice function in TRUE mode."""
    # Setup
    values = ["A", "B", "C"]
    probabilities = [0.2, 0.3, 0.5]

    # Run many trials to verify distribution
    results = {"A": 0, "B": 0, "C": 0}
    trials = 1000

    for _ in range(trials):
        choice = random_choice(values, probabilities, mode=RandomChoiceMode.TRUE)
        results[choice] += 1

    # Check that distribution roughly matches probabilities
    # Allow for some statistical variation
    assert 150 < results["A"] < 250  # ~20%
    assert 250 < results["B"] < 350  # ~30%
    assert 450 < results["C"] < 550  # ~50%


def test_random_choice_simulated_mode():
    """Test random_choice function in SIMULATED mode."""
    # Setup
    values = ["A", "B", "C"]
    probabilities = [0.2, 0.3, 0.5]

    # Test with a single choice to verify basic functionality
    choice = random_choice(values, probabilities, mode=RandomChoiceMode.SIMULATED)

    # Just verify that the choice is one of the valid options
    assert choice in values, "Should return one of the valid options"


def test_probabilistic_event():
    """Test probabilistic_event function."""
    # Setup
    probabilities = [0.2, 0.3, 0.5]

    # Run many trials to verify distribution
    results = {0: 0, 1: 0, 2: 0}
    trials = 1000

    for _ in range(trials):
        event = probabilistic_event(probabilities)
        results[event] += 1

    # Check that distribution roughly matches probabilities
    # Allow for some statistical variation
    assert 100 < results[0] < 300  # ~20%
    assert 200 < results[1] < 400  # ~30%
    assert 400 < results[2] < 600  # ~50%


def test_sigmoid_probability():
    """Test sigmoid_probability function."""
    # Test at midpoint
    mid_prob = sigmoid_probability(0.5, midpoint=0.5)
    assert 0.45 < mid_prob < 0.55, "Probability at midpoint should be around 0.5"

    # Test below midpoint
    low_prob = sigmoid_probability(0.1, midpoint=0.5)
    assert low_prob < 0.1, "Probability well below midpoint should be low"

    # Test above midpoint
    high_prob = sigmoid_probability(0.9, midpoint=0.5)
    assert high_prob > 0.9, "Probability well above midpoint should be high"

    # Test with custom min/max
    custom_prob = sigmoid_probability(0.5, midpoint=0.5, min_chance=0.2, max_chance=0.8)
    assert 0.45 < custom_prob < 0.55, "Custom probability at midpoint should be around 0.5"
    assert custom_prob >= 0.2, "Custom probability should respect min_chance"
    assert custom_prob <= 0.8, "Custom probability should respect max_chance"


def test_cosine():
    """Test cosine similarity function."""
    # Test identical vectors
    assert cosine((1, 0, 0), (1, 0, 0)) == 1.0

    # Test orthogonal vectors
    assert cosine((1, 0, 0), (0, 1, 0)) == 0.0

    # Test opposite vectors
    assert cosine((1, 0, 0), (-1, 0, 0)) == -1.0

    # Test with zero vector (should not divide by zero)
    assert cosine((0, 0, 0), (1, 1, 1)) == 0.0

    # Test with similar vectors
    similarity = cosine((1, 1, 0), (2, 1, 0))
    assert 0.9 < similarity < 1.0
