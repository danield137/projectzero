from typing import cast, get_args

from tigen.ai import ActionStep
from tigen.ecs.system import System
from zero.ai.actions import (
    ActionSteps,
    DropAction,
    EatAction,
    ExploreAction,
    MatingAction,
    PickUpAction,
    SleepAction,
    WalkToAction,
)
from zero.simulation.components import (
    ActivityComponent,
    BrainComponent,
    EatingActivity,
    MatingActivity,
    PositionComponent,
    SleepingActivity,
)


class ActuationSystem(System):
    def validate(self) -> bool:
        # collect all handler functions defined on this class
        handlers: set[str] = set()
        for name in dir(self):
            if name.startswith("_handle_"):
                handlers.add(name[8:])

        missing = set(get_args(ActionSteps)) - handlers
        assert not missing, f"No executor for {missing!r}"
        return True

    def update(self, simulation_time: int):
        for eid in self.ecs.get_entities_with_typed_component(BrainComponent):
            brain = self.ecs.get_typed_component(eid, BrainComponent)
            if not brain.current_plan:
                continue

            # explicit calls for performance reasons
            current_step = brain.current_plan[0]
            if isinstance(current_step, WalkToAction):
                self._handle_walk_to(eid, current_step, simulation_time)
            elif isinstance(current_step, EatAction):
                self._handle_eat(eid, current_step, simulation_time)
            elif isinstance(current_step, SleepAction):
                self._handle_sleep(eid, current_step, simulation_time)
            elif isinstance(current_step, MatingAction):
                self._handle_mating(eid, current_step, simulation_time)
            elif isinstance(current_step, ExploreAction):
                self._handle_explore(eid, current_step, simulation_time)
            elif isinstance(current_step, PickUpAction):
                self._handle_pick_up(eid, current_step, simulation_time)
            elif isinstance(current_step, DropAction):
                self._handle_drop(eid, current_step, simulation_time)

    def _handle_walk_to(self, eid: int, action: WalkToAction, simulation_time: int):
        pos = self.ecs.get_typed_component(eid, PositionComponent)
        if not pos:
            # No position — just skip the action
            brain = self.ecs.get_typed_component(eid, BrainComponent)
            cast(list[ActionStep], brain.current_plan).pop(0)
            self.ecs.update_typed_component(eid, brain)
            return

        tx, ty = action.pos
        dx = (tx > pos.x) - (tx < pos.x)
        dy = (ty > pos.y) - (ty < pos.y)

        if dx == 0 and dy == 0:
            # Arrived — pop the action
            brain = self.ecs.get_typed_component(eid, BrainComponent)
            cast(list[ActionStep], brain.current_plan).pop(0)
            self.ecs.update_typed_component(eid, brain)
            return

        pos.x += dx
        pos.y += dy
        self.ecs.update_typed_component(eid, pos)

    def _handle_explore(self, eid: int, action: ExploreAction, simulation_time: int):
        import random

        from tigen.config import get_global_config

        pos = self.ecs.get_typed_component(eid, PositionComponent)
        if not pos:
            brain = self.ecs.get_typed_component(eid, BrainComponent)
            cast(list[ActionStep], brain.current_plan).pop(0)
            self.ecs.update_typed_component(eid, brain)
            return

        config = get_global_config()
        dx = random.randint(-1, 1)
        dy = random.randint(-1, 1)
        pos.x = max(0, min(config.world_width - 1, pos.x + dx))
        pos.y = max(0, min(config.world_height - 1, pos.y + dy))
        self.ecs.update_typed_component(eid, pos)

        # Pop after one step of exploration
        brain = self.ecs.get_typed_component(eid, BrainComponent)
        cast(list[ActionStep], brain.current_plan).pop(0)
        self.ecs.update_typed_component(eid, brain)

    def _handle_eat(self, eid: int, action: EatAction, simulation_time: int):
        # Update the ActivityComponent
        act = self.ecs.get_typed_component(eid, ActivityComponent)
        if act.activity.is_eating():
            eating_activity = cast(EatingActivity, act.activity)
            if eating_activity.food == action.food_id:
                # already eating this food
                return

            eating_activity.food = action.food_id
        else:
            act.activity = EatingActivity(food=action.food_id, since=simulation_time)
            # Pop action from plan since we're starting a new eating activity
            brain = self.ecs.get_typed_component(eid, BrainComponent)
            cast(list[ActionStep], brain.current_plan).pop(0)
            self.ecs.update_typed_component(eid, brain)
        self.ecs.update_typed_component(eid, act)

    def _handle_mating(self, eid: int, action: MatingAction, simulation_time: int):
        # Update the ActivityComponent
        act = self.ecs.get_typed_component(eid, ActivityComponent)
        # todo: we need to properly handle finding a mate. For now, we leave it blank.
        #  The reproduction system will handle it. but it is clearly bad separation of concerns.
        act.activity = MatingActivity(mate=action.partner_id, since=simulation_time)
        # Pop action from plan since we're starting a new eating activity
        brain = self.ecs.get_typed_component(eid, BrainComponent)
        cast(list[ActionStep], brain.current_plan).pop(0)
        self.ecs.update_typed_component(eid, brain)
        self.ecs.update_typed_component(eid, act)

    def _handle_sleep(self, eid: int, action: SleepAction, simulation_time: int):
        # Just update ActivityComponent for now
        # TODO: Set ConsciousnessComponent.is_awake=False when implemented
        act = self.ecs.get_typed_component(eid, ActivityComponent)
        if not act.activity.is_sleeping():
            act.activity = SleepingActivity(since=simulation_time)
            # Pop action from plan since we're starting a new sleeping activity
            brain = self.ecs.get_typed_component(eid, BrainComponent)
            cast(list[ActionStep], brain.current_plan).pop(0)
            self.ecs.update_typed_component(eid, brain)
        self.ecs.update_typed_component(eid, act)

    def _handle_pick_up(self, eid: int, action: PickUpAction, simulation_time: int):
        brain = self.ecs.get_typed_component(eid, BrainComponent)
        cast(list[ActionStep], brain.current_plan).pop(0)
        self.ecs.update_typed_component(eid, brain)

    def _handle_drop(self, eid: int, action: DropAction, simulation_time: int):
        brain = self.ecs.get_typed_component(eid, BrainComponent)
        cast(list[ActionStep], brain.current_plan).pop(0)
        self.ecs.update_typed_component(eid, brain)
