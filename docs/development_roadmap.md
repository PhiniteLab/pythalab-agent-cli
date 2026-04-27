# Development roadmap

The 0.1.0 codebase is intentionally small. Several components ship with full schemas and tested helpers but are not yet wired into the `run` loop. This page lists, in priority order, the planned work to close the gap between the schema surface and runtime behaviour.

## Near-term

1. **Persist runs to SQLite memory.**
   - On `DirectAgentLoop.run` start, insert a `tasks` row.
   - Per attempt, insert a `validation_runs` row with the report summary and an `artifacts` row holding the snapshot path.
   - On success, also write a `reflections` row capturing the failure trail.
   - This makes `pythalab-agent memory list` and a future `memory show <id>` useful.

2. **Wire optional `ruff` / `pyright` / `pytest` checks.**
   - Add three new `ValidationCheck` implementations driven by `validation.run_ruff` / `run_pyright` / `run_pytest`.
   - Each is opt-in (default off) so the loop stays fast.
   - Keep them downstream of syntax/import/runtime so cheap checks fail first.

3. **Wire `security.forbidden_code_patterns`.**
   - Add a pre-runtime AST scan that rejects extracted code containing `eval`, `exec`, `os.system`, `subprocess.*`, `socket`, etc., according to the config list.
   - On rejection, treat as a `SYNTAX`-style failure and feed the violation back to the model.

4. **Wire `security.write_allowlist` / `deny_write_patterns`.**
   - Today the runtime only writes to `repo.target_file`. When multi-file edit lands (item 6), enforce these.

## Medium-term

5. **Reward / strategy feedback.**
   - Update `strategy_stats` based on attempt count and final success.
   - Pick prompt variants based on the running stats (small bandit, no learning across machines).

6. **Multi-file edit mode.**
   - Optional flag (e.g. `--multi-file`) that lets the model emit multiple fenced blocks tagged with relative paths.
   - Validate by running the existing pipeline plus a project-wide `pytest -q` if enabled.

7. **Docker sandbox runner.**
   - `LocalRunner` already isolates the environment; a `DockerRunner` variant would run the runtime check inside a `python:3.11-slim` container with `--network none` and a tmpfs working directory.
   - Selectable via `validation.runner = local | docker`.

## Longer-term

8. **Wake-up planner role.**
   - For tasks above a length threshold, route through the (currently inert) `planner` model profile to produce an outline, then drive `direct` per outline node.
   - Keep the JSON-free principle: outline is plain Markdown.

9. **Repair-only mode without regenerating from scratch.**
   - Instead of rewriting `algorithm.py`, accept a unified diff from the model and apply it. Falls back to full rewrite on parse failure.
   - This needs the `patcher` profile and a small diff applier.

10. **Telemetry export.**
    - `pythalab-agent memory export --jsonl` for offline analysis.
    - No remote upload — the project stays local-only.

## Non-goals

- Cloud model backends.
- Generic file-system / shell tool use by the model.
- Fine-tuning or training loops.

## Status legend (for tracking)

When work begins on an item, it should move into a GitHub Project board column matching one of:

- `planned` — listed here, no PR yet.
- `in-progress` — open PR.
- `done` — merged and reflected in [quality_report.md](quality_report.md) under the relevant release.
