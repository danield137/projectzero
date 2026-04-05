from dataclasses import dataclass

from sim.ai.memory import Memory, MemoryData


@dataclass(slots=True, frozen=True)
class BrainContext:
    """
    Context for the AI brain, providing necessary data for decision-making.
    All "sensory" data is normalized to a range of 0.0 to 1.0.
    This context is used by the AI engine to make decisions and plans.
    """

    simulation_time: int
    eid: int
    etype: str
    memory_data: MemoryData
    memory_engine: Memory
