import abc

from sim.config import RunConfiguration, get_global_config
from sim.ecs.core import ECS


class System(abc.ABC):
    ecs: ECS
    config: RunConfiguration
    logging_enabled: bool = False

    def init_system(self, ecs: ECS):
        self.ecs = ecs
        self.config = get_global_config()

    @abc.abstractmethod
    def update(self, simulation_time: int):
        pass

    def validate(self) -> bool:
        """
        [Optional]: Validate the system.
        This is called once after the system is initialized and before the simulation starts.
        """
        return True
