# Roadmap

> A learning project to explore game design, simulation architecture, and AI in games — by building a small world from scratch.

## Vision

Project Zero is an educational sandbox for learning how to build simulations, design ECS architectures, and implement autonomous AI agents. The end goal is a primitive RimWorld-like experience: autonomous agents, resource economies, social dynamics, and emergent behavior.

**Focus areas:**
- Fast prototyping, runnable code at every step
- Learning by implementing from scratch
- Autonomous AI agents
- Social interactions and emergent behavior

## Definition of Done

A working complex-ish simulation with:
- **Entities** — plants, trees, animals, humans
- **Resources** — water (lakes), food (animals, plants), wood (trees), stone
- **Systems** — trade, social interactions, basic AI, reproduction, grid-based world
- **Interactive** — basic display (pygame), ability to add/kill individuals, spy on agents, trigger events (plague, drought, etc.)

---

## Milestones

### ✅ 0.1 — Fundamentals
- [x] Basic ECS (CRUD, typing, iterators)
- [x] Basic debugging (system execution time traces)
- [x] Realistic randomness (ratio-preserving entity generation)
- [x] Basic life flow (eat, sleep, procreate)
- [x] Predictable population growth
- [x] Fertility age range
- [x] Domain stats tracing (life, resources, food)
- [x] Energy management
- [x] Plant growth

### ✅ 0.2 — Stability & Performance
- [x] Clearer system design (aspects, split Action from Reasoning)
- [x] Health system redesign (condition-based penalties)
- [x] AI building blocks (goal setting, plan building)
- [x] Primitive behaviors with test coverage
- [x] Actuation system
- [x] Basic tests for primitive systems
- [x] Sigmoid hunger curves
- [x] ECS performance (generational list, no collection cloning)

### ✅ 0.3 — Introduce Humans
- [x] Human agents with basic properties (health, hunger, needs)
- [x] Integration into existing simulation framework

### 🚧 0.35 — Simulation Stability
- [x] System can run for a while without food running out
- [x] Live visualization (TUI dashboard)
- [ ] Performance bottlenecks — focus on Generational and ECS
  - Rewrite tigen ECS core in Rust (via PyO3) with contiguous SoA storage
  - Python dict-of-objects → Rust Vec<T> indexed by entity ID
  - Cache-friendly iteration for systems, zero pointer chasing
  - Keep Python API surface identical (drop-in replacement)

### 🔲 0.4 — Basic Socializing
- [ ] Stable simulation (solve overpopulation → plant extinction cycle)
  - Simulate food scarcity via search probability or plant "invisibility" (seedlings can't be eaten until mature)
- [ ] Simple social system (social need as a goal/plan)
- [ ] Foundational rules for groups and relationships
- [ ] Predefined scenarios ("Tiny Earth")

### 🔲 0.45 — Advanced Socializing
- [ ] Probabilistic conception and offspring
- [ ] Relationship management (likes/dislikes/friends/enemies)
- [ ] Proper mate selection based on social factors
- [ ] Separate social logic from reproduction system
- [ ] Enhanced social behaviors and group dynamics

### 🔲 0.475 — Perf & Debt
- [ ] Goal/plan/action/activity validation
- [ ] States of being (asleep, awake)
- [ ] Food discovery system (fix explore action, resource tagging)
- [ ] Profile and optimize slow systems
- [ ] Code quality pass (TODOs, maintainability)

### 🔲 0.5 — Multi-Tile & Movement
- [ ] Grid-based world implementation
- [ ] Agent movement and navigation
- [ ] Location-based resource availability

### 🔲 0.6 — Basic 2D Visualization
- [ ] Pygame window with grid rendering
- [ ] Camera/viewport navigation
- [ ] Entity sprites (humans, animals, plants, water, stone)
- [ ] Click-to-select with stat sidebar
- [ ] Pause/play, speed controls (1x/2x/4x)
- [ ] Separate rendering from simulation logic
- [ ] 30+ FPS with current entity counts

### 🔲 0.7 — Resource Harvesting
- [ ] Wood and water source mechanics
- [ ] Collection, storage, and consumption
- [ ] Fix food discovery (explore action)
- [ ] Proper resource tagging

### 🔲 0.8 — Shelter Building
- [ ] Construction mechanics using gathered resources
- [ ] Shelter benefits (weather protection, well-being)

### 🔲 0.9 — Trading System
- [ ] Simple trading/barter mechanism
- [ ] Basic market influencing resource distribution

### 🔲 1.0 — Migrations
- [ ] Population relocation based on resource scarcity or social factors
- [ ] Migration triggers with simulation feedback

### 🔲 1.1 — Advanced AI
- [ ] Complex decision-making routines
- [ ] Strategic, goal-oriented AI adapting to changing states

### 🔲 1.2 — Interactivity
- [ ] External input (trigger events, adjust parameters)
- [ ] Meaningful player influence on simulation

### 🔲 1.3 — UI & Visualization
- [ ] Polished UI with grid, resources, agent statuses
- [ ] Interactive dashboards for data inspection

### 🔲 1.4 — Better Systems
- [ ] System refinements and improvements
