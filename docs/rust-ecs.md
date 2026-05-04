# Rust ECS — Design Direction

## Context

tigen's ECS is implemented in pure Python. Profiling shows **~70% of tick time
is spent in ECS infrastructure** — component lookups, iteration, and
generational container operations. The remaining ~30% is game logic.

Key numbers (200 ticks, ~30 entities, ~14 systems):

| Operation | Calls/100 ticks | Time share |
|---|---|---|
| `get_typed_component` | 190K | 20% |
| `update_component` | 75K | 14% |
| `get_entities_with_component_type` | 117K | 10% |
| `generational.get_at/keys/items` | 690K | 27% |

The hot path is clear: **storage and iteration of the generational containers**.

## Vision

Python remains the language for game logic. Rust replaces the infrastructure
layer — storage, iteration, queries. Developers prototype systems in Python;
the engine handles performance transparently.

**Rust is the future for ECS internals.** The Python ECS implementation stays
in the repo as a readable reference (the "textbook" version), but production
code will use the Rust backend. Over time, Python ECS code becomes dangling —
no live imports, but behavioral tests still run against it to document what
correct behavior looks like.

```
┌─────────────────────────────────────────┐
│  Game Systems (Python)                  │  ← game devs write here
│  HungerSystem, ReasoningSystem, ...     │
├─────────────────────────────────────────┤
│  ECS API (Python)                       │  ← stable interface
│  ecs.get_typed_component(eid, Type)     │
│  ecs.get_entities_with_component_type() │
├─────────────────────────────────────────┤
│  Storage (Rust via PyO3)                │  ← performance layer
│  GenerationalContainer, GenerationalDict│
│  Entity/component storage, iteration   │
└─────────────────────────────────────────┘
```

## Parity and versioning

The Python implementation is the behavioral spec. Both backends must produce
identical outputs for identical inputs — verified by a shared test suite.

- **Shared behavioral tests** — every test runs against both backends (via
  pytest parametrize). If Python passes and Rust fails, that's a Rust bug.
- **Algorithmic drift is acceptable** — Python might use O(n·log·n) where Rust
  uses O(n²) and is still faster. They're different implementations of the same
  interface. The test suite is the contract, not the algorithm.
- **Version the interface, not the implementation** — `tigen 0.7.0` means "the
  ECS API is at this version." Both backends conform. Internal algorithms are
  implementation details.
- **Don't backport Rust optimizations to Python** — `core.py` is the readable
  version, not the optimal version. Keeping it simple is a feature.
- **Python ECS will gradually become a reference only** — once Rust is stable,
  new features may be Rust-first. Python code stays for learning purposes but
  may lag behind on newer features.

## Phases

### Phase 1 — Rust-backed generational containers

Replace `GenerationalContainer` and `GenerationalDict` in
`tigen.common.ds.generational` with Rust implementations exposed via PyO3.

**What changes:**
- `GenerationalContainer<PyObject>` in Rust, wrapping a `Vec<Option<PyObject>>`
  with generation tracking and free-list recycling.
- `GenerationalDict<PyObject>` in Rust, wrapping a container + key-to-handle
  hashmap.
- Python `core.py` (the ECS) keeps its current API — it just uses Rust-backed
  storage instead of Python lists/dicts.

**What doesn't change:**
- `core.py` API surface
- `system.py` interface
- Game systems
- Component classes (still Python dataclasses)

**Expected speedup:** 5–10× on storage/iteration operations. Components are
still Python objects crossing the FFI boundary, so per-object overhead remains.

**Key decisions:**
- Store `PyObject` (opaque Python references) in Rust, not serialized data.
  This avoids the serialization cost and keeps components as normal Python
  objects.
- Iteration returns Python objects — no zero-copy possible here since components
  are Python heap objects.
- The three isolation levels (NONE, ALLOW_DELETIONS, FULL) must be preserved.
  They protect against mutation during iteration in systems.

### Phase 2 — Rust-native ECS core

Move entity management and component indexing into Rust. The Python `core.py`
becomes a thin wrapper.

**What moves to Rust:**
- Entity creation/deletion with ID recycling
- Component-to-entity indexing (`components_by_type`)
- Entity-to-components indexing (`components_by_entity`)
- `get_entities_with_component_type()` — returns entity ID iterators
- `get_typed_component(eid, comp_type)` — single-dispatch lookup

**What stays in Python:**
- Component class definitions (Python dataclasses)
- System logic
- Query/aspect resolution
- The `App` loop and builder

**Expected speedup:** 10–30× overall. The entity/component index is now a Rust
HashMap, and iteration doesn't cross FFI per-entity — it collects matching
entity IDs in Rust and returns them as a batch.

### Phase 3 — Rust-native component storage (optional, much later)

For components that are pure data (no Python methods), allow Rust-native storage
with zero-copy access. This is the `example.rs` model — `Vec<Option<T>>` per
component type, direct array indexing.

**Requires:**
- A way to declare "Rust components" — either via a schema DSL, a derive macro,
  or by inspecting Python dataclass fields and generating Rust structs.
- Serialization at the boundary: Python writes to Rust storage, systems in
  Python read back. Or: systems that touch these components are also Rust.
- This is where the "migrate system to Rust" story comes in.

**Not planned yet.** Phase 1 and 2 give 10–30× without changing any game code.
Phase 3 is for when individual systems become the bottleneck and need to be
rewritten in Rust.

## Migration strategy

Each phase is backward compatible. The test suite runs against both backends
after each phase.

During migration, Python ECS stays importable but is no longer the default:

```
Phase 1:  Rust generational containers replace Python ones.
          Python originals stay in repo as reference.
          Behavioral tests run against both.

Phase 2:  Rust ECS core becomes the default import.
          Python ECS is importable via explicit path for reference:
            from tigen.ecs.core import ECS       # Python reference
            from tigen.ecs import ECS            # Rust (default)

Phase 3:  Rust-native components for hot-path systems.
          Python systems continue to work via PyO3 bridge.
```

Environment variable for testing/debugging:
```bash
TIGEN_ECS_BACKEND=python python run.py   # force Python backend
TIGEN_ECS_BACKEND=rust python run.py     # force Rust (default)
```

## Build system

PyO3 + maturin for building the Rust extension. The package ships as:
- Pure Python wheel (no Rust, current behavior)
- Platform-specific wheel with Rust extension (when available)

At import time, tigen tries to import the Rust module. If unavailable, falls
back to pure Python. This keeps `pip install tigen` working everywhere while
offering native speed where compiled.

## Non-goals

- **Rewriting game systems in Rust.** Systems stay in Python. If a specific
  system is too slow, the developer can rewrite it — but the engine doesn't
  force this.
- **ECS archetype storage.** The current sparse-set model works well for the
  entity counts we have (hundreds, not millions). Archetype storage (like Bevy's)
  is overkill and adds complexity.
- **Multi-threading.** Python's GIL limits this. Rust-internal parallelism
  (rayon) could help for Phase 3 batch operations, but it's not a priority.
- **Custom query language / DSL.** The current Python API is sufficient.

## Open questions

- **Isolation levels in Rust:** The FULL isolation mode creates deferred-deletion
  snapshots. Implementing this in Rust while holding `PyObject` references
  requires careful GIL management. May simplify to just NONE + ALLOW_DELETIONS
  initially if FULL isn't used in practice.
- **`tigen[rust]` vs default:** Should the Rust extension be opt-in (extra) or
  the default build? Depends on CI/wheel availability for target platforms.
- **Maturin vs setuptools-rust:** Both work with PyO3. Maturin is simpler for
  pure Rust extensions. Current Cargo.toml already exists.
