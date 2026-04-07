import math
import random
from typing import Protocol, TypeVar

import numpy as np

T = TypeVar("T")


def clamp(value: int | float, min_value: int, max_value: int) -> int:
    """
    Clamp a value to be within the specified range [min_value, max_value].

    Examples:
        >>> clamp(5, 0, 10)
        5
        >>> clamp(-1, 0, 10)
        0
        >>> clamp(15, 0, 10)
        10
    """
    if value < min_value:
        return int(min_value)
    if value > max_value:
        return int(max_value)
    return int(value)


def random_values_w_normal_distribution(
    min_v: float, max_v: float, center: float, count: int = 1, std_dev: float = 1.0
) -> np.ndarray:
    values = np.random.normal(loc=center, scale=std_dev, size=count)
    # Clip values to stay within range [0, n]
    return np.clip(values, min_v, max_v)


class RandomChoiceMode:
    TRUE = "true"
    SIMULATED = "simulated"


def random_choice(
    values: list[T],
    probabilities: list[float],
    mode: str = RandomChoiceMode.TRUE,
    current_counts: list[int] | None = None,
    epsilon: float | None = None,
) -> T:
    """
    This method is used to choose a value from a list of values with a given expected distribution.
    It has two modes:
    - true      : For the real distribution, we will choose from the values according to the probabilities provided.
    - simulated : For the simulated distribution, we will choose the value that is furthest from its expected distribution.
                  This is to help balance the distribution of values, and prevent skewing even for small periods of time.
                  This can be helpful in scenarios where want to simulate the perception of fair distribution (a la Ipod's shuffle).
    :param value: List of values to choose from.
    :param probabilities: List of probabilities for each value.
    :param mode: Mode of choice. Can be "real" or "simulated".
    :param current_counts: List of current counts of each value.
    :param epsilon: Epsilon value for simulated mode.
    """
    if mode == RandomChoiceMode.SIMULATED:
        if current_counts is None:
            current_counts = [0] * len(values)
        if epsilon is None:
            epsilon = 0.1
        # Calculate the expected distribution
        total_items = sum(current_counts)
        if total_items == 0:
            choice = np.random.choice(len(values), p=probabilities)
            return values[choice]

        expected_counts = [math.ceil(p * total_items) for p in probabilities]
        # Calculate the difference between expected and current counts
        diffs = [abs(e - c) for e, c in zip(expected_counts, current_counts)]
        # Find the index of the value with the largest difference
        max_diff_idx = np.argmax(diffs)
        max_diff = diffs[max_diff_idx]
        if max_diff > epsilon * total_items:
            # Choose the value with the largest difference
            return values[max_diff_idx]

    choice = np.random.choice(len(values), p=probabilities)
    return values[choice]


def probabilistic_event(probabilities: list[float]) -> int:
    """
    Given a list of probabilities, return the index of the event that happened.
    Probabilities should sum to 1.0
    """
    ranges = np.cumsum(probabilities)
    r = random.random()
    i = 0
    for curr_range in ranges:
        if r > curr_range:
            i += 1
        else:
            break
    return i


def sigmoid_probability(
    x: float,
    midpoint: float = 0.5,
    growth_rate: float = 10.0,
    min_chance: float = 0.001,
    max_chance: float = 0.95,
) -> float:
    """
    Calculate a sigmoid-based probability.

    Args:
        x (float): The current value (e.g., age).
        midpoint (float): The midpoint of the sigmoid curve where probability is ~50%.
        growth_rate (float): Controls how rapidly probability increases around midpoint.
        min_chance (float): Minimum probability.
        max_chance (float): Maximum probability.

    Returns:
        float: Probability between min_chance and max_chance.
    """
    prob = min_chance + (max_chance - min_chance) / (1 + math.exp(-growth_rate * (x - midpoint)))
    return min(max(prob, min_chance), max_chance)


Vector = tuple[int, ...]  # simple discrete context vector


def cosine(a: Vector, b: Vector) -> float:  # tiny helper
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


# TODO: this probably needs to be different to align with the host system
EPSILON = 1e-9


class MovingAverageFunction(Protocol):
    def __call__(self, v: float) -> float: ...
    def current(self) -> float: ...
    def reset(self) -> None: ...
    def count(self) -> int: ...


def moving_average() -> MovingAverageFunction:
    """Creates a moving average function with O(1) memory usage.

    Returns a function that maintains a running average of all values
    passed to it, using only constant memory regardless of how many
    values are processed.

    Example:
        >>> avg = moving_average()
        >>> avg(1)        # returns 1.0
        1.0
        >>> avg(3)        # returns 2.0
        2.0
        >>> avg(5)        # returns 3.0
        3.0
        >>> avg.current() # returns 3.0 (current average without adding)
        3.0
        >>> avg.count()   # returns 3
        3
        >>> avg.reset()
        >>> avg(10)       # returns 10.0 (fresh start)
        10.0
    """
    count: int = 0
    running_sum: float = 0.0

    def add(v: float) -> float:
        nonlocal count, running_sum
        count += 1
        running_sum += v
        return running_sum / count

    def current() -> float:
        return running_sum / count if count > 0 else 0.0

    def reset() -> None:
        nonlocal count, running_sum
        count = 0
        running_sum = 0.0

    def get_count() -> int:
        return count

    # Return the add function but attach helper methods
    add.current = current  # type: ignore[attr-defined]
    add.reset = reset  # type: ignore[attr-defined]
    add.count = get_count  # type: ignore[attr-defined]

    return add  # type: ignore
