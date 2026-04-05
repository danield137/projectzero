# TODO: this is a very basic ECS implementation, it can be improved in many ways.
# A few ares to consider:
# - Performance: currently, we are using dictionaries for everything, this is not optimal for large number of entities.
#   Especially since deletion is sub-optimal, and we are not using any spatial partitioning.
# - Memory: we are storing a lot of redundant data, e.g. we store the same component data in multiple places.
#   Better memory management can be achieved either by using a more complex data structure, a database or a lower level language (with pointers).
import json
from collections import defaultdict
from collections.abc import Iterator, Sequence
from typing import Any, TypeVar, cast

from termcolor import colored

from sim.common.ds.generational import (
    GenerationalDefaultDict,
    GenerationalDict,
    IsolationLevel,
)
from sim.common.extensions import debug_enabled, equals
from sim.common.logging import Verbosity, get_logger
from sim.ecs.component import Component

logger = get_logger()

is_debugger_attached = debug_enabled()


T = TypeVar("T")


class ECS:
    """
    A data structure to store entities (E) and their components (C).
    The systems (S) use this data structure to efficiently access and update the components.
    """

    # TODO: we need to handle entity deletion better, currently, we are not reusing entity ids.
    # for large enough number of entities, this will cause memory issues.
    next_entity_id: int
    entities_by_id: GenerationalDict[int, str]
    entities_by_type: dict[str, GenerationalDict[int, Any]]
    components_by_entity: GenerationalDict[int, dict[str, Component]]
    components_by_type: dict[str, GenerationalDict[int, Component]]
    verbosity: int = Verbosity.WARNING
    tracked_entity: int | None = None
    focus_on_entity_type: str | None = None
    immutable_entities: set[int] = set()

    def __init__(
        self,
        verbosity: int = Verbosity.WARNING,
        focus_on_entity_type: str | None = None,
    ):
        self.next_entity_id = 0
        self.entities_by_id = GenerationalDict()
        self.entities_by_type = defaultdict(GenerationalDict)
        self.components_by_entity = GenerationalDefaultDict(dict)
        self.components_by_type = defaultdict(GenerationalDict)
        self.focus_on_entity_type = focus_on_entity_type
        self.verbosity = verbosity

    def entity_exists(self, eid: int) -> bool:
        """
        Check if an entity with the given id exists.
        :param eid: the entity id
        :return: True if the entity exists, False otherwise
        """
        return eid in self.entities_by_id

    def track_entity(self, eid: int) -> bool:
        if self.focus_on_entity_type is None:
            return False
        if self.tracked_entity == eid:
            return True
        if self.tracked_entity is None:
            etype = self.entities_by_id.get(eid)
            if etype == self.focus_on_entity_type:
                self.tracked_entity = eid
                return True
        return False

    def create_entity(
        self,
        etype: str,
        components: Sequence[Component] | None = None,
        mutable: bool = True,
    ) -> int:
        """
        Create an entity of the given type with the given components.
        :param etype: the entity type
        :param components: the components to add to the entity
        :return: the entity id
        """
        eid = self.next_entity_id
        # for know, we debug the first animal we create
        if self.track_entity(eid):
            logger.warning("%s entity %s", colored("Debugging", "light_yellow"), colored(eid, "light_cyan"))
        self.entities_by_id[eid] = etype
        self.entities_by_type[etype][eid] = None
        if components:
            for component in components:
                self.add_typed_component(eid, component)
        self.next_entity_id += 1
        if self.verbosity == Verbosity.DEBUG:
            # components_str = ", ".join([str(comp) for comp in components] if components else [])
            logger.debug(
                "%s entity %s of type %s, %s",
                colored("Created", "light_yellow"),
                colored(eid, "light_cyan"),
                colored(etype, "light_magenta"),
                ", ".join([str(comp) for comp in components] if components else []),
            )

        if not mutable:
            self.immutable_entities.add(eid)
        return eid

    def create_singleton_entity(
        self,
        etype: str,
        components: list[Component] | None = None,
        mutable: bool = True,
    ) -> int:
        """
        Create a singleton entity of the given type with the given component.
        :param etype: the entity type
        :param component: the component to add to the entity
        :return: the entity id
        """
        assert etype not in self.entities_by_type, (
            f"Entity type {etype} already exists, can't create a singleton entity"
        )
        # potentially, hoist singletons (and their components) in to a more "hot cache" like structure
        return self.create_entity(etype, components, mutable)

    def remove_entity(self, eid: int):
        """
        Properly remove an entity from the ECS.
        This takes care of removing all components associated with the entity.

        *Note*: this DOES NOT remove the entity from every other element that might reference it.
        It is hard to implement this in python, and is not in the scope of this project.

        :param eid: the entity id
        """
        if self.track_entity(eid):
            breakpoint()
        etype = self.entities_by_id[eid]
        if self.verbosity == Verbosity.DEBUG:
            logger.debug(
                "%s entity %s of type %s",
                colored("Removing", "light_yellow"),
                colored(eid, "light_cyan"),
                colored(etype, "light_magenta"),
            )
        self.entities_by_id.delete(eid)
        self.entities_by_type[etype].delete(eid)
        for comp_name in self.components_by_entity[eid]:
            self.components_by_type[comp_name].delete(eid)
        self.components_by_entity.delete(eid)

    def add_component(self, eid: int, comp_name: str, comp_data: Component):
        self.components_by_entity[eid][comp_name] = comp_data
        self.components_by_type[comp_name][eid] = comp_data

    def get_component(self, eid: int, comp_name: str) -> Component | None:
        return self.components_by_entity[eid].get(comp_name)

    def has_component(self, eid: int, comp_name: str) -> bool:
        """
        Check if an entity has a component.
        :param eid: the entity id
        :param comp_name: the component name
        :return: True if the entity has the component, False otherwise
        """
        return comp_name in self.components_by_entity[eid]

    def get_entities_with_component_type(self, component_type: str, etype: str | None = None) -> Iterator[int]:
        """
        Get all entities that have the given component type.
        :param component_type: the component type
        :param etype: the entity type
        :return: a list of entity ids
        """
        if component_type not in self.components_by_type:
            # finish the iteration if we don't have any entities with this component type
            return

        for eid in self.components_by_type[component_type].keys(
            allowed_mutation=IsolationLevel.ALLOW_DELETIONS, skip_empty=True
        ):
            if etype is None:
                yield eid
                continue
            if self.entities_by_id[eid] == etype:
                yield eid
                continue

    def update_component(self, eid: int, comp_name: str, comp_data: Any, debug: bool = False):
        """
        Update a component for an entity.

        *Note*: Tries to avoid updating the component if the new data is the same as the old data.

        :param eid: the entity id
        :param comp_name: the component name
        :param comp_data: the new component data
        :param debug: whether to log debug information
        """
        if eid in self.immutable_entities:
            raise ValueError(f"Entity {eid} is immutable, can't update component {comp_name}")

        if self.track_entity(eid):
            if is_debugger_attached:
                breakpoint()
            else:
                logger.warning(
                    "%s entity %s %s: %s",
                    colored("Update", "light_yellow"),
                    colored(eid, "light_cyan"),
                    colored(comp_name, "green"),
                    comp_data,
                )
        prev = self.components_by_entity[eid].get(comp_name)
        if equals(prev, comp_data):
            return
        if debug and self.verbosity == Verbosity.DEBUG:
            logger.debug(
                "%s component %s for entity %s: %s",
                colored("Updating", "light_yellow"),
                colored(comp_name, "light_magenta"),
                colored(eid, "light_cyan"),
                json.dumps(comp_data),
            )
        self.components_by_entity[eid][comp_name] = comp_data
        self.components_by_type[comp_name][eid] = comp_data

    def get_entity_components(self, eid: int) -> dict[str, Any]:
        """
        Get all components for an entity.
        :param eid: the entity id
        :return: a dictionary of component names and component data
        """
        return self.components_by_entity[eid]

    def get_typed_component(self, eid: int, comp_type: type[T]) -> T:
        """
        Get a component of a specific type for an entity.
        :param eid: the entity id
        :param comp_type: the component type
        :return: the component data
        """

        comp_name = comp_type.__name__
        comp = self.get_component(eid, comp_name)
        # this can be None, but changing everything to handle None is a bit too much right now
        return cast(T, comp)

    def get_singleton_component(self, comp_type: type[T]) -> T:
        """
        Singleton components are components that are expected to be unique in the ECS.
        This method will return the entity id and the component data.
        """
        comp_name = comp_type.__name__
        if comp_name not in self.components_by_type:
            raise ValueError(f"Component {comp_name} not found, but expected to be a singleton")
        components = self.components_by_type[comp_name]
        _, comp_data = next(components.items())
        # guaranteed to be a singleton, so we can just return the first one
        return cast(T, comp_data)

    def update_typed_component(self, eid: int, comp_data: object, debug: bool = False):
        """
        Update a component of a specific type for an entity.
        :param eid: the entity id
        :param comp_data: the new component data
        :param debug: whether to log debug information
        """

        comp_type = type(comp_data)
        comp_name = comp_type.__name__
        self.update_component(eid, comp_name, comp_data, debug)

    def update_typed_singleton_component(self, comp_data: object, debug: bool = False):
        """
        Update a component of a specific type for an entity.
        :param eid: the entity id
        :param comp_data: the new component data
        :param debug: whether to log debug information
        """

        comp_type = type(comp_data)
        comp_name = comp_type.__name__
        eid, _ = next(iter(self.components_by_type[comp_name].items()))
        self.update_component(eid, comp_name, comp_data, debug)

    def has_typed_component(self, eid: int, comp_type: type[T]) -> bool:
        """
        Check if an entity has a component of a specific type.
        :param eid: the entity id
        :param comp_type: the component type
        :return: True if the entity has the component of the given type, False otherwise
        """

        comp_name = comp_type.__name__
        return self.has_component(eid, comp_name)

    def get_entities_with_typed_component(self, comp_type: type[T], etype: str | None = None) -> Iterator[int]:
        comp_name = comp_type.__name__
        return self.get_entities_with_component_type(comp_name, etype)

    def add_typed_component(self, eid: int, component: Component):
        comp_type = component.__class__.__name__
        self.add_component(eid, comp_type, component)
