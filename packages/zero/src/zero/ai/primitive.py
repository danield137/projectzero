import enum
from typing import cast

from sim.ai import ActionStep
from sim.ai.brain import GoalSelector, Planner
from sim.ai.context import BrainContext
from sim.ai.memory import MemoryFact, MemQuery
from sim.common.logging import get_logger
from zero.ai.actions import (
    EatAction,
    ExploreAction,
    MatingAction,
    PickUpAction,
    SleepAction,
    WalkToAction,
)
from zero.ai.context import PrimitiveBrainContext

logger = get_logger()


class PrimitiveGoal(str, enum.Enum):
    IDLE = "Idle"
    EAT = "Eat"
    SLEEP = "Sleep"
    REPRODUCE = "Reproduce"

    @staticmethod
    def all() -> list[str]:
        return [PrimitiveGoal.IDLE, PrimitiveGoal.EAT, PrimitiveGoal.SLEEP, PrimitiveGoal.REPRODUCE]


class PrimitiveGoalSelector(GoalSelector[PrimitiveGoal]):
    possible_outcomes: list[str] = [PrimitiveGoal.IDLE, PrimitiveGoal.EAT, PrimitiveGoal.SLEEP, PrimitiveGoal.REPRODUCE]

    def select_goal(self, ctx: BrainContext) -> PrimitiveGoal:
        # TODO: ctx should be generic
        ctx = cast(PrimitiveBrainContext, ctx)
        goal = PrimitiveGoal.IDLE
        if ctx.hunger >= 0.8:
            goal = PrimitiveGoal.EAT
        elif ctx.energy <= 0.2:
            goal = PrimitiveGoal.SLEEP
        elif ctx.hunger < 0.6 and ctx.energy > 0.4 and not ctx.is_pregnant:
            # Relaxed conditions: hunger < 6.0 (not too hungry) and energy > 4.0 (enough energy)
            goal = PrimitiveGoal.REPRODUCE
        else:
            goal = PrimitiveGoal.IDLE
        return goal


class PrimitiveMemoryAccess:
    @staticmethod
    def recall_food(ctx: BrainContext) -> list[MemoryFact]:
        ctx = cast(PrimitiveBrainContext, ctx)
        q = MemQuery(None, None, lambda x: x.tag == "food", None, 1)
        facts = ctx.memory_engine.recall(ctx.memory_data, q, ctx.simulation_time)
        return facts

    @staticmethod
    def recall_home(ctx: BrainContext) -> list[MemoryFact]:
        ctx = cast(PrimitiveBrainContext, ctx)
        q = MemQuery(None, None, lambda x: x.tag == "home", None, 1)
        facts = ctx.memory_engine.recall(ctx.memory_data, q, ctx.simulation_time)
        return facts


# TODO: this needs to be further improved.
# should not know the internal structure of a memory fact.
# the problem is that we likely need to have an ai module that is specific to the simulation,
# as the top level ai module is meant to be generic.
class PrimitivePlanner(Planner[PrimitiveGoal]):
    def plan_eat(self, ctx: BrainContext) -> list[ActionStep]:
        ctx = cast(PrimitiveBrainContext, ctx)
        known_foods = PrimitiveMemoryAccess.recall_food(ctx)

        # Filter foods based on dietary preferences if rules are available
        if ctx.rules is not None:
            edibles: list[MemoryFact] = []
            for f in known_foods:
                can_eat = ctx.rules.can_eat(ctx.eid, f.value["id"])
                if can_eat.is_unknown():
                    # remove this food from memory
                    ctx.memory_engine.forget(ctx.memory_data, f.uid)
                elif can_eat.is_true():
                    edibles.append(f)
        else:
            edibles = known_foods

        if edibles:
            food = edibles[0]
            if food.value["owned"]:
                return [EatAction(food.value["id"])]

            return [
                WalkToAction(food.value["location"]),
                PickUpAction(food.value["id"]),
                EatAction(food.value["id"]),
            ]

        return [ExploreAction(1)]

    def plan_sleep(self, ctx: BrainContext) -> list[ActionStep]:
        ctx = cast(PrimitiveBrainContext, ctx)
        known_homes = PrimitiveMemoryAccess.recall_home(ctx)
        if known_homes:
            home = known_homes[0]
            return [WalkToAction(home.value["location"]), SleepAction()]
        # here we need to check the ctx to see if we have enough energy to explore, or just fall asleep where we are
        return [SleepAction()]

    def plan_reproduce(self, ctx: BrainContext) -> list[ActionStep]:
        ctx = cast(PrimitiveBrainContext, ctx)
        # Partner selection deferred to ReproductionSystem for now.
        # TODO: Implement partner selection logic somewhere (?)
        return [MatingAction(partner_id=-1)]

    def make_plan(self, ctx: BrainContext, goal: str) -> list[ActionStep]:
        ctx = cast(PrimitiveBrainContext, ctx)
        if goal == PrimitiveGoal.EAT:
            return self.plan_eat(ctx)
        if goal == PrimitiveGoal.IDLE:
            return []
        if goal == PrimitiveGoal.SLEEP:
            return self.plan_sleep(ctx)
        if goal == PrimitiveGoal.REPRODUCE:
            return self.plan_reproduce(ctx)
        return []
