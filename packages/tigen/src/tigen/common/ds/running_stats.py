"""
Utilities for maintaining online statistics with O(1) memory usage.
"""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field

from tigen.common.math import MovingAverageFunction, moving_average


@dataclass(slots=True)
class RunningMean:
    """Maintains a running mean using constant memory."""

    avg: MovingAverageFunction = field(default_factory=moving_average)

    def add(self, value: float) -> None:
        """Add a value to the running mean."""
        self.avg(value)

    def value(self) -> float:
        """Get the current mean without modifying it."""
        return self.avg.current()

    def reset(self) -> None:
        """Reset the mean calculation."""
        self.avg.reset()


@dataclass(slots=True)
class RunningDistribution:
    """
    Incrementally maintains a probability distribution over categorical values.
    Supports O(1) updates and probability queries.
    """

    counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    total: int = 0

    def add(self, key: str, n: int = 1) -> None:
        """
        Record n occurrences of key.

        :param key: Category to increment
        :param n: Count to add (default: 1)
        """
        self.counts[key] += n
        self.total += n

    def prob(self, key: str) -> float:
        """
        Get P(key) = count(key) / total.
        Returns 0.0 if no samples recorded.

        :param key: Category to query
        :return: Probability of this category
        """
        return self.counts[key] / self.total if self.total else 0.0

    def keys(self) -> Iterable[str]:
        """Get recorded categories."""
        return self.counts.keys()

    def reset(self) -> None:
        """Clear all counts."""
        self.counts.clear()
        self.total = 0
