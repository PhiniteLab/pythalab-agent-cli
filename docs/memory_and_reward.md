# Memory and reward

`pythalab-agent-cli` ships a SQLite-backed memory store. In 0.1.0 the schema is fully implemented and exercised by unit tests, but the runtime does not write to it during a `run`. This page describes the current state honestly and points at the future work.

## Where it lives

`<workspace>/.pythalab-agent/memory.sqlite`. Created during `pythalab-agent init` and on first access. The schema migration is single-shot and idempotent (see [memory/migrations.py](../src/pythalab_agent_cli/memory/migrations.py)).

## Schema

Tables created by the migration:

| Table              | Purpose                                                              |
| ------------------ | -------------------------------------------------------------------- |
| `tasks`            | One row per logical task with `prompt`, `task_type`, timestamps.     |
| `artifacts`        | Code or report blobs attached to a task (path, kind, sha256, body).  |
| `validation_runs`  | Aggregate validation outcome per attempt (status, scores, failure).  |
| `reflections`      | Free-form notes per task (intended for self-reflection prompts).     |
| `strategy_stats`   | Counter / reward stats per `(strategy_name, task_type)` pair.        |

`SQLiteStore` ([memory/sqlite_store.py](../src/pythalab_agent_cli/memory/sqlite_store.py)) provides typed read/write methods for all of the above (`record_task`, `record_artifact`, `record_validation`, `record_reflection`, `update_strategy`, plus listers and `clear`).

## What runs at runtime in 0.1.0

- `pythalab-agent init` creates the database file and applies the migration.
- `pythalab-agent memory list` reads from `tasks`.
- `pythalab-agent memory clear --yes` truncates all tables.
- The internal test suite uses the store directly to exercise both reads and writes.

What does **not** happen yet:

- `DirectAgentLoop.run` does **not** write to `tasks`, `artifacts`, `validation_runs`, `reflections`, or `strategy_stats`.
- There is no reward signal feeding back into prompt selection or strategy choice.
- `agent.run` ignores the memory store except to pass it through for future use.

That means `pythalab-agent memory list` is empty after every run today. This is expected — see the roadmap.

## Why the schema is already there

Two reasons:

1. **API stability.** Persisting attempts is the next planned feature. Shipping the schema and store with 0.1.0 means an upgrade does not require a SQLite migration on existing workspaces.
2. **Unit-testability.** The store itself is fully covered by tests in `tests/unit/`, so a future runtime integration only has to wire calls in, not redesign the storage layer.

## Roadmap

- Persist a `tasks` row when `DirectAgentLoop.run` starts.
- Persist a `validation_runs` row per attempt with the `ValidationReport` summary.
- Snapshot final `algorithm.py` source as an `artifacts` row on success.
- Optionally write `reflections` rows after each failed attempt summarising the cause (`SYNTAX` / `IMPORT` / `RUNTIME`).
- Add `pythalab-agent memory show <task-id>` to inspect a task's history.

See [development_roadmap.md](development_roadmap.md).
