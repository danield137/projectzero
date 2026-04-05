from simz.ai.brain import Brain
from simz.ai.memory import Memory, PerfectMemory
from zero.ai.primitive import (
    PrimitiveGoal,
    PrimitiveGoalSelector,
    PrimitivePlanner,
)


class BrainType:
    ANIMAL = "Animal"
    HUMAN = "Human"


# TODO: again, should not be defined outside of the ECS, should be a singleton component (e.g. AIConfigurationComponent)
brains: dict[str, Brain[PrimitiveGoal]] = {
    BrainType.ANIMAL: Brain(PrimitiveGoalSelector(), PrimitivePlanner(), PerfectMemory()),
    BrainType.HUMAN: Brain(PrimitiveGoalSelector(), PrimitivePlanner(), PerfectMemory()),
}


def get_predefined_brain(brain_type: str) -> Brain[PrimitiveGoal]:
    """
    Get the brain instance for the given brain type.
    """
    if brain_type not in brains:
        raise ValueError(f"Unknown brain type: {brain_type}")
    brain_impl = brains.get(brain_type)

    if brain_impl is None:
        raise ValueError(f"Brain type {brain_type} not implemented.")

    return brain_impl


def get_memory_engine(brain_type: str) -> Memory:
    """
    Get the memory engine for the given brain type.
    """
    brain_impl = get_predefined_brain(brain_type)
    return brain_impl.memory
