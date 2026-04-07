from typing import Callable, List, Tuple

from tigen.ecs.core import ECS
from tigen.ecs.system import System
from zero.simulation.entities import EntitiesFactory


def run_simulation_until(
    systems: List[System],
    stop_condition: Callable[[System], bool],
    max_turns: int = 200,
) -> Tuple[int, bool]:
    """
    Run a simulation until a stop condition is met or the maximum number of turns is reached.
    :param systems: List of systems to run.
    :param stop_condition: Function that takes a system and returns True if the simulation should stop.
    :param max_turns: Maximum number of turns to run the simulation.
    :return: Tuple of the number of turns run and whether the stop condition was met.
    """
    turn = 0
    done = False
    while not done and turn < max_turns:
        for system in systems:
            system.update(turn)
            done = stop_condition(system)
            if done:
                break
        turn += 1
    return turn, done


def add_singleton_components(ecs: ECS):
    ecs.create_singleton_entity(*EntitiesFactory.metadata_entity())
    ecs.create_singleton_entity(*EntitiesFactory.create_config_entity())
