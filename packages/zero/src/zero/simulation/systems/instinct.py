from tigen.ecs.system import System


class InstinctSystem(System):
    """
    Fast reflexes based solely on raw SensesComponent.
    Serves as an override for the full planning system in specific cases.
    For example, if a predator is detected, the agent should immediately
    evade without waiting for the full planning cycle.
    This helps model the brain as two separate systems:
    1) instinctual (fast, reflexive) and
    2) rational (slow, deliberative).
    Instincts are not necessarily reflexes, but they are fast and
    automatic. They are not based on conscious reasoning.
    """

    def update(self, simulation_time: float): ...
