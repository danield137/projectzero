from typing import List

from tigen.ecs.component import Component, IntComponent
from tigen.ecs.core import ECS


class NameComponent(Component):
    def __init__(self, value: str):
        self.value = value


class PositionComponent(Component):
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y


class HealthComponent(IntComponent):
    pass


def test_create_entity_and_get_typed_component():
    # Arrange
    ecs = ECS()
    entity_type = "TestEntity"
    name_component = NameComponent("TestName")
    components: List[Component] = [name_component]

    # Act
    entity_id = ecs.create_entity(entity_type, components)
    retrieved_component = ecs.get_typed_component(entity_id, NameComponent)

    # Assert
    assert ecs.entity_exists(entity_id), "Entity should exist after creation."
    assert retrieved_component.value == "TestName", "Component value should match the expected value."


def test_remove_entity():
    # Arrange
    ecs = ECS()
    entity_type = "TestEntity"
    entity_id = ecs.create_entity(entity_type)

    # Act
    ecs.remove_entity(entity_id)

    # Assert
    assert not ecs.entity_exists(entity_id), "Entity should not exist after removal."


def test_update_component():
    # Arrange
    ecs = ECS()
    entity_id = ecs.create_entity("TestEntity", [NameComponent("Initial")])

    # Act
    name_comp = ecs.get_typed_component(entity_id, NameComponent)
    name_comp.value = "Updated"
    ecs.update_typed_component(entity_id, name_comp)

    # Assert
    retrieved = ecs.get_typed_component(entity_id, NameComponent)
    assert retrieved.value == "Updated", "Component should be updated with new value"


def test_has_component():
    # Arrange
    ecs = ECS()
    entity_id = ecs.create_entity("TestEntity", [NameComponent("Test")])

    # Act & Assert
    assert ecs.has_typed_component(entity_id, NameComponent), "Entity should have NameComponent"
    assert not ecs.has_typed_component(entity_id, PositionComponent), "Entity should not have PositionComponent"


def test_get_entities_with_component():
    # Arrange
    ecs = ECS()
    entity1 = ecs.create_entity("Type1", [NameComponent("Entity1"), PositionComponent(1.0, 2.0)])
    entity2 = ecs.create_entity("Type1", [NameComponent("Entity2")])
    entity3 = ecs.create_entity("Type2", [PositionComponent(3.0, 4.0)])

    # Act
    entities_with_name = list(ecs.get_entities_with_typed_component(NameComponent))
    entities_with_position = list(ecs.get_entities_with_typed_component(PositionComponent))
    entities_with_position_type1 = list(ecs.get_entities_with_typed_component(PositionComponent, "Type1"))

    # Assert
    assert sorted(entities_with_name) == sorted([entity1, entity2]), "Should return entities with NameComponent"
    assert sorted(entities_with_position) == sorted([entity1, entity3]), "Should return entities with PositionComponent"
    assert entities_with_position_type1 == [entity1], "Should return only Type1 entities with PositionComponent"


def test_add_component_after_creation():
    # Arrange
    ecs = ECS()
    entity_id = ecs.create_entity("TestEntity")

    # Act
    ecs.add_typed_component(entity_id, NameComponent("Added"))

    # Assert
    assert ecs.has_typed_component(entity_id, NameComponent), "Entity should have the added component"
    name = ecs.get_typed_component(entity_id, NameComponent)
    assert name.value == "Added", "Component should have the correct value"


def test_create_and_get_singleton():
    # Arrange
    ecs = ECS()

    # Act
    config_id = ecs.create_singleton_entity("Config", [HealthComponent(100)])

    # Assert
    singleton = ecs.get_singleton_component(HealthComponent)
    assert singleton.value == 100, "Should retrieve the singleton component correctly"

    # Should be able to update the singleton
    singleton.value = 200
    ecs.update_typed_singleton_component(singleton)
    updated = ecs.get_singleton_component(HealthComponent)
    assert updated.value == 200, "Should update the singleton component"
