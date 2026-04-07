# ai/actions.py  –  “decisions, not execution”
from dataclasses import dataclass
from typing import Any

from tigen.ai import ActionStep


@dataclass(frozen=True, slots=True)
class WalkToAction(ActionStep):
    pos: Any


@dataclass(frozen=True, slots=True)
class EatAction(ActionStep):
    food_id: int


@dataclass(frozen=True, slots=True)
class PickUpAction(ActionStep):
    entity: int


@dataclass(frozen=True, slots=True)
class IdleAction(ActionStep): ...


@dataclass(frozen=True, slots=True)
class ExploreAction(ActionStep):
    radius: int


@dataclass(frozen=True, slots=True)
class ReplanAction(ActionStep):
    original_goal: str


@dataclass(frozen=True, slots=True)
class DropAction(ActionStep):
    entity: int


@dataclass(frozen=True, slots=True)
class SleepAction(ActionStep): ...


@dataclass(frozen=True, slots=True)
class MatingAction(ActionStep):
    partner_id: int


# ─── species–specific steps ─────────────────────────────────────────
@dataclass(frozen=True, slots=True)
class LayEggAction(ActionStep):
    nest_id: int  # animals only


@dataclass(frozen=True, slots=True)
class GetMarriedAction(ActionStep):
    partner_id: int  # humans only


# --------------------------------------------------------------------

ActionSteps = (WalkToAction, EatAction, PickUpAction, DropAction, SleepAction, MatingAction)
