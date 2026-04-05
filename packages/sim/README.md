# simz

A lightweight ECS (Entity Component System) based simulation engine.

## Features

- **ECS Core** — Entity-Component-System architecture with generational IDs and efficient queries
- **AI Module** — Brain/context/memory abstractions for agent behavior
- **Common Utilities** — Math helpers, logging, data structures (generational containers, running stats)
- **Configurable** — Runtime configuration for simulation parameters

## Installation

```bash
pip install simz
```

## Quick Start

```python
from simz.ecs.core import ECS
from simz.ecs.component import Component
from simz.ecs.system import System

# Define components
class Position(Component):
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y

# Create ECS and entities
ecs = ECS()
ecs.create_entity("player", [Position(0, 0)])
```

## License

Non-commercial use only. See [LICENSE](LICENSE) for details.