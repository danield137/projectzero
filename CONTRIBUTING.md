# Contributing

Thanks for your interest in Project Zero! This document covers the architecture, code style, and quality gates to follow when contributing.

## Getting Started

```bash
git clone https://github.com/danield137/projectzero.git
cd projectzero
uv sync --all-groups
```

## Project Structure

This is a **uv workspace** monorepo with two packages:

- **`packages/simz/`** (`simz`) — standalone ECS simulation engine
- **`packages/zero/`** (`projectzero`) — the life simulation built on simz

The dependency is one-way: `zero → simz`. The engine has no knowledge of the simulation.

## Architecture (ECS)

The codebase follows the **Entity Component System** pattern:

- **Entities** — unique integer identifiers, nothing more
- **Components** — pure data (`slots=True` dataclasses). No logic. Single responsibility.
- **Systems** — all logic lives here. Stateless. Batch processing via `update(time)`.

## Coding Style

| Rule | Convention |
|------|-----------|
| Formatter | Ruff (120 line length) |
| Imports | StdLib → Third-party → Project (absolute imports, sorted by isort) |
| Naming | `PascalCase` classes, `snake_case` functions/vars |
| Docstrings | Google-style. No top-level module docstrings. |
| Type hints | Strict, Python 3.10+ syntax |

### Performance Guidelines

- **Hot paths** (main loop): prioritize speed over readability. Use NumPy if needed. No defensive `None` checks — crash or sanitize upstream. Avoid O(N) lookups inside loops.
- **Non-hot paths**: prioritize readability.

### Design Principles

- Avoid circular references
- Avoid dynamic attribute patching
- Design data structures as if a borrow checker exists (Rust-transferable patterns)
- If a design isn't clear-cut, present at least 3 options with pros/cons

## Quality Gates

Before submitting changes, make sure everything passes:

```bash
# Format
make format

# Lint + type check
make check

# Tests
make test
```

All three must pass cleanly.

## Testing

- **Framework**: pytest
- **Structure**: Arrange → Act → Assert
- **Rule**: Prefer adding tests to existing files over creating new ones
- **Debugging**: Assume the test is broken before assuming the code is

## Roadmap

See [ROADMAP.md](ROADMAP.md) for the milestone plan. If you're looking for something to work on, the current milestone and any unchecked items there are fair game.
