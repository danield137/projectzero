from simz.ecs.system import System

from .actuation import ActuationSystem
from .energy import EnergySystem
from .growth import GrowthSystem
from .health import HealthSystem
from .hunger import HungerSystem
from .instinct import InstinctSystem
from .perception import PerceptionSystem
from .photosynthesis import PhotosynthesisSystem
from .reasoning import ReasoningSystem
from .reproduction import ReproductionSystem
from .stats import StatsSystem
from .water import WaterSystem
from .weather import WeatherSystem
from .world import WorldsSystem

__all__ = [
    "System",
    "HungerSystem",
    "HealthSystem",
    "EnergySystem",
    "PhotosynthesisSystem",
    "ReproductionSystem",
    "WeatherSystem",
    "WaterSystem",
    "GrowthSystem",
    "WorldsSystem",
    "PerceptionSystem",
    "InstinctSystem",
    "ReasoningSystem",
    "ActuationSystem",
    "StatsSystem",
]
