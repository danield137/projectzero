from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Protocol

from tigen.ai.context import BrainContext
from tigen.common.enum import TriStateEnum


class RuleResult(enum.Enum):
    ALLOW = "allow"
    DENY = "deny"
    UNKNOWN = "unknown"


class CanEatFn(Protocol):
    # TODO: getting the entire ECS is probably wrong, but for now it allows easy extending.
    def __call__(self, eater_entity: int, food_id: int) -> TriStateEnum: ...


@dataclass(slots=True)
class PrimitiveWorldRules:
    """Bag of world-specific predicates the generic AI may call."""

    can_eat: CanEatFn
    # Tomorrow: is_threat, can_mate, etc. Keep versions additive.


@dataclass(slots=True, frozen=True)
class PrimitiveBrainContext(BrainContext):
    """
    Context for the AI brain, providing necessary data for decision-making.
    All "sensory" data is normalized to a range of 0.0 to 1.0.
    This context is used by the AI engine to make decisions and plans.
    """

    hunger: float
    energy: float
    is_pregnant: bool
    rules: PrimitiveWorldRules | None = None
