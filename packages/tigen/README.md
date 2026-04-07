# tigen — Tiny Game Engine

A lightweight ECS (Entity Component System) based simulation engine.

## Features

- **ECS Core** — Entity-Component-System architecture with generational IDs and efficient queries
- **AI Module** — Brain/context/memory abstractions for agent behavior
- **Common Utilities** — Math helpers, logging, data structures (generational containers, running stats)
- **Configurable** — Runtime configuration for simulation parameters

## Installation

```bash
pip install tigen
```

## Quick Start

```python
from tigen.ecs.core import ECS
from tigen.ecs.component import Component
from tigen.ecs.system import System

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

[MIT](../../LICENSE) — see root LICENSE file.