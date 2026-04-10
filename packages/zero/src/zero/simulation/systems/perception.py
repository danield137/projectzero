from tigen.ecs.system import System
from zero.simulation.components import PerceivedEntity, PerceptionComponent, PositionComponent
from zero.simulation.entities import EntityTypes


class PerceptionSystem(System):
    """
    Populate each entity's PerceptionComponent with nearby entities
    based on spatial distance (manhattan distance within radius).
    """

    # Entity types that are not perceivable
    _SKIP_TYPES = frozenset({EntityTypes.Metadata, EntityTypes.CONFIG, EntityTypes.WORLD, EntityTypes.WEATHER})

    def update(self, simulation_time: float):
        # Build a spatial index of all positioned entities
        positioned: list[tuple[int, str, int, int]] = []  # (eid, etype, x, y)
        for eid in self.ecs.entities_by_id:
            etype = self.ecs.entities_by_id[eid]
            if etype in self._SKIP_TYPES:
                continue
            pos = self.ecs.get_typed_component(eid, PositionComponent)
            if pos:
                positioned.append((eid, etype, pos.x, pos.y))

        # For each entity with perception, find nearby entities
        perceivers = list(self.ecs.get_entities_with_typed_component(PerceptionComponent))
        for eid in perceivers:
            perception = self.ecs.get_typed_component(eid, PerceptionComponent)
            my_pos = self.ecs.get_typed_component(eid, PositionComponent)
            if not my_pos:
                continue

            radius = perception.radius
            nearby: list[PerceivedEntity] = []
            for other_eid, other_etype, ox, oy in positioned:
                if other_eid == eid:
                    continue
                dist = abs(my_pos.x - ox) + abs(my_pos.y - oy)
                if dist <= radius:
                    nearby.append(PerceivedEntity(other_eid, other_etype, dist))

            perception.nearby = nearby
            self.ecs.update_typed_component(eid, perception)
