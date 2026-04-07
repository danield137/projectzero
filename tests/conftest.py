import pytest

from tests import add_singleton_components
from tigen.ecs.core import ECS


@pytest.fixture
def ecs():
    """Provides a clean ECS instance with singleton components."""
    _ecs = ECS()
    add_singleton_components(_ecs)
    return _ecs
