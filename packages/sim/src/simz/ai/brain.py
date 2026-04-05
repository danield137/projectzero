import abc
import enum
from dataclasses import dataclass
from typing import Generic, TypeVar

from simz.ai import ActionStep
from simz.ai.context import BrainContext
from simz.ai.memory import Memory

TGoal = TypeVar("TGoal", bound=enum.Enum)


@dataclass(slots=True)
class GoalSelector(abc.ABC, Generic[TGoal]):
    @abc.abstractmethod
    def select_goal(self, ctx: BrainContext) -> TGoal: ...


@dataclass(slots=True)
class Planner(abc.ABC, Generic[TGoal]):
    @abc.abstractmethod
    def make_plan(self, ctx: BrainContext, goal: str) -> list[ActionStep]: ...


@dataclass(slots=True)
class Brain(Generic[TGoal]):
    goal_selector: GoalSelector[TGoal]
    planner: Planner[TGoal]
    memory: Memory
