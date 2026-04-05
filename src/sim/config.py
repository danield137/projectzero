from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class RunConfiguration:
    """Configuration object for simulation runtime settings."""

    debug_entity_id: int | None = None

    @staticmethod
    def default() -> RunConfiguration:
        """Returns a default configuration with no debug entity."""
        return RunConfiguration(debug_entity_id=None)


_global_config = RunConfiguration.default()


def set_global_config(config: RunConfiguration) -> None:
    """Set the global configuration for the simulation."""
    global _global_config
    _global_config = config


def get_global_config() -> RunConfiguration:
    """Get the current global configuration."""
    return _global_config
