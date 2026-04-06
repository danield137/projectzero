# Project Zero

A simulation sandbox exploring emergent AI behavior, social dynamics, and ecological systems — built on an ECS (Entity Component System) architecture in Python.

## Overview

Project Zero simulates a miniature world where plants grow, animals hunt, and humans reason — all driven by composable systems and lightweight AI. It's a playground for prototyping ideas around agent behavior, resource economies, and emergent complexity.

**Key features:**
- **ECS engine ([simz](https://pypi.org/project/simz/))** — generational entity IDs, typed components, system-based updates
- **AI module** — brain/memory/context abstractions with goal-directed planning
- **Ecological simulation** — weather, photosynthesis, hunger, energy, reproduction, health
- **TUI dashboard** — terminal-based live visualization

## Quick Start

```bash
# Clone and install
git clone https://github.com/danield137/projectzero.git
cd projectzero
uv sync --all-groups

# Run the simulation (100 ticks)
uv run python run.py -t 100

# Run with TUI dashboard
uv run python run.py -t 5000 --tui

# Run tests
uv run pytest
```

## Project Structure

```
projectzero/
├── packages/
│   ├── sim/              # simz — standalone ECS simulation engine
│   │   └── src/simz/
│   │       ├── ecs/      # Entity-Component-System core
│   │       ├── ai/       # Brain, memory, context abstractions
│   │       └── common/   # Math, logging, data structures
│   └── zero/             # Project Zero — the life simulation
│       └── src/zero/
│           ├── ai/       # Brains, planners, actions
│           └── simulation/
│               ├── components.py   # Health, hunger, energy, etc.
│               ├── entities.py     # Plants, animals, humans
│               └── systems/        # All simulation systems
├── tests/                # pytest test suites
├── perf/                 # Benchmarks
└── run.py                # Entry point
```

This is a **uv workspace** monorepo. The `simz` engine is published independently on [PyPI](https://pypi.org/project/simz/) and can be used in other projects:

```bash
pip install simz
```

## How It Works

Each tick of the simulation runs a pipeline of systems:

1. **World** — advance time, manage world state
2. **Weather** — temperature and rainfall cycles
3. **Photosynthesis** — plants convert sunlight to growth
4. **Reproduction** — entities reproduce when conditions are met
5. **Energy/Hunger** — metabolic systems drain and replenish
6. **Perception** — entities observe their surroundings
7. **Reasoning** — humans plan and make decisions
8. **Actuation** — actions are executed
9. **Health** — entities live or die based on their state

Entities are just integer IDs with attached components (pure data). Systems contain all the logic and operate on component queries — no inheritance hierarchies, no god objects.

## CLI Options

```
python run.py [options]

  -t, --ticks N         Run for N ticks (default: unlimited)
  -r, --release         Disable debug/memory tracking
  --tui                 Use TUI dashboard mode
  --tui-interval N      Dashboard refresh interval in ticks (default: 100)
  --tui-delay SECS      Delay between ticks (default: 0)
```

## License

[MIT](LICENSE)
