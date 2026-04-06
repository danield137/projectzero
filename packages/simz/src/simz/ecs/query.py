import inspect
from collections.abc import Callable
from typing import TypeVar

from simz.ecs.core import ECS

T = TypeVar("T")


class Query:
    @staticmethod
    def function(ecs: ECS, entity_id: int, fn: Callable[..., bool]) -> bool:
        """
        Executes a function, injecting components from the ECS as arguments.
        """
        # 1. Inspect the predicate's signature to see what components it needs
        required_params = inspect.signature(fn).parameters

        # 2. Build the arguments dictionary by fetching components from the ECS
        args_to_pass = {}
        for name, param in required_params.items():
            component_type = param.annotation
            # This assumes the type hint is the component class
            component = ecs.get_typed_component(entity_id, component_type)

            # If a required component doesn't exist, the predicate should fail
            if component is None:
                return False

            args_to_pass[name] = component

        # 3. Call the predicate with the resolved dependencies
        return fn(**args_to_pass)

    @staticmethod
    def aspect(ecs: ECS, aspect_class: type[T], entity_id: int) -> T | None:
        """
        Constructs a single Aspect instance for a given entity.

        Inspects the aspect's __init__ signature to determine which
        components to fetch. Returns None if any required component
        is missing.
        """
        try:
            # 1. Inspect the __init__ to find required components
            required_params = inspect.signature(aspect_class.__init__).parameters

            args_to_pass = {}
            # Start from index 1 to skip 'self'
            for param_name in list(required_params.keys())[1:]:
                param = required_params[param_name]
                component_type = param.annotation

                # This is a simple way to differentiate singletons
                # A more robust way might be a custom type hint or registry
                if "Singleton" in component_type.__name__:
                    component = ecs.get_singleton_component(component_type)
                else:
                    component = ecs.get_typed_component(entity_id, component_type)

                if component is None:
                    # A required component is missing, so we can't build the Aspect
                    return None

                args_to_pass[param_name] = component

            # 2. Instantiate the aspect with the fetched components
            return aspect_class(**args_to_pass)

        except Exception:
            # Could log an error here if aspect construction fails
            return None
