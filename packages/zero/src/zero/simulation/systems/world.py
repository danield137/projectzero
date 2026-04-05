from sim.ecs.system import System
from zero.simulation.components import (
    DayNightCycleComponent,
    LocalTimeComponent,
    NameComponent,
)


class WorldsSystem(System):
    """Responsible for world specific data, like day/night cycle, time, etc."""

    def advance_time(self, simulation_time: int):
        world_entities = self.ecs.get_entities_with_typed_component(LocalTimeComponent)
        if not world_entities:
            raise ValueError("No world entity found")
        world = next(world_entities)
        local_time = self.ecs.get_typed_component(world, LocalTimeComponent)
        day_night_cycle = self.ecs.get_typed_component(world, DayNightCycleComponent)
        hours_in_a_day = local_time.hours_in_a_day
        days_in_a_year = local_time.days_in_a_year
        hour = (local_time.hour + 1) % hours_in_a_day
        if hour == 0:
            local_time.day += 1

        if local_time.day == days_in_a_year:
            local_time.year += 1
            local_time.day = 0

        local_time.hour = hour
        day_night_cycle.is_day = day_night_cycle.sunset > hour > day_night_cycle.sunrise
        self.ecs.update_typed_component(world, local_time)
        self.ecs.update_typed_component(world, day_night_cycle)

    def update(self, simulation_time: int):
        self.advance_time(simulation_time)

    def local_time_on_planets(self) -> str:
        string = ""
        for entity in self.ecs.get_entities_with_typed_component(LocalTimeComponent):
            local_time = self.ecs.get_typed_component(entity, LocalTimeComponent)
            name = self.ecs.get_typed_component(entity, NameComponent)
            string += f"{name.value}: {local_time.hour}:00\n"

        return string
