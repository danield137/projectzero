from __future__ import annotations

import abc
from typing import TYPE_CHECKING

from tigen.config import RunConfiguration, get_global_config
from tigen.ecs.core import ECS

if TYPE_CHECKING:
    from tigen.app import App


class System(abc.ABC):
    ecs: ECS
    config: RunConfiguration
    logging_enabled: bool = False

    def init_system(self, ecs: ECS):
        self.ecs = ecs
        self.config = get_global_config()

    def startup(self, app: App) -> None:  # noqa: B027
        """
        [Optional]: Called once after all systems are initialized and the world
        is populated (setup_fn has run), but before the simulation loop starts.
        Use for initialization that depends on full ECS state.
        """

    @abc.abstractmethod
    def update(self, simulation_time: int):
        pass

    def shutdown(self) -> None:  # noqa: B027
        """
        [Optional]: Called once after the simulation loop ends.
        Use for releasing resources, restoring state, etc.
        """

    def validate(self) -> bool:
        """
        [Optional]: Validate the system.
        This is called once after the system is initialized and before the simulation starts.
        """
        return True

    def cleanup(self) -> None:
        """Deprecated: use shutdown() instead."""
        self.shutdown()
