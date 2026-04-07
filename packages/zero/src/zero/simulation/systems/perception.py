from tigen.ecs.system import System


class PerceptionSystem(System):
    """
    Gather sensory (sight, sound, ..) state into SensesComponent.
    This can be later used to make decisions.
    """

    def update(self, simulation_time: float): ...
