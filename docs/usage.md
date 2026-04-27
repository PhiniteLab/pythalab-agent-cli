# Usage Guide

This guide walks through every command exposed by `pythalab-agent`, with realistic examples and the expected output shape.

All examples assume:

```bash
. .venv/bin/activate
cd my-workspace
```

## 1. `pythalab-agent init`

Scaffold a workspace.

```bash
pythalab-agent init .
```

Creates `algorithm.py`, `tests/test_algorithm.py`, `configs/`, `AGENTS.md`, and the `.pythalab-agent/` runtime directory.

Re-running `init` is safe; it does not overwrite existing files.

## 2. `pythalab-agent run`

The core command. Generates code, validates it staged, repairs, and materializes only when every gate passes.

```bash
pythalab-agent run "Implement function solve(n: int) -> int that returns the n-th Fibonacci number iteratively"
```

Typical milestones printed to the terminal:

```text
✓ preflight        — target=algorithm.py model=qwen3:4b max_attempts=25
✓ generate (#1)    — model returned 412 chars
✓ validate (#1)    — attempt 1 passed
✓ complete (1/25)  — algorithm.py validated after 1 attempt(s)
```

Final summary:

```text
                         Run result
┏━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Key               ┃ Value                                           ┃
┡━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ task_id           │ 77001                                           │
│ status            │ success                                         │
│ changed_files     │ algorithm.py                                    │
│ attempt_snapshots │ .pythalab-agent/attempts/task-077001-attempt-…  │
│ total_attempts    │ 1                                               │
│ max_attempts      │ 25                                              │
│ primary_failure   │ NONE                                            │
└───────────────────┴─────────────────────────────────────────────────┘
```

Useful flags:

```bash
pythalab-agent run "TASK" --max-attempts 50         # raise the budget
pythalab-agent run "TASK" --until-success            # foreground continuous
pythalab-agent run "TASK" --backend fake             # deterministic, no Ollama
pythalab-agent run "TASK" --path ./other-workspace   # operate elsewhere
pythalab-agent run "TASK" --no-install               # never install missing deps
pythalab-agent run "TASK" --auto-install             # install missing deps automatically
```

### Writing good tasks

The runtime works best with explicit signatures:

```text
Implement function solve(data: list[int]) -> list[int] that returns a stable merge sort of data.
```

If no signature is given, the runtime supplies the standard envelope:

```python
def solve(request: dict[str, object]) -> dict[str, object]
```

with `request = {"inputs": ..., "parameters": ..., "config": ..., "metadata": ...}` and `result = {"outputs": ..., "metrics": ..., "artifacts": ..., "diagnostics": ...}`.

## 3. `pythalab-agent chat`

Interactive REPL — type a task per line, press Enter, get a full staged generation cycle, then loop.

```bash
pythalab-agent chat
task> Implement solve(x: float) -> float for sin via Taylor series, six terms
task> exit
```

Useful for quickly iterating on small tasks without typing the full `run` command each time.

## 4. `pythalab-agent validate`

Run the full validation pipeline against the current `algorithm.py` without writing anything.

```bash
pythalab-agent validate
```

Output:

```text
 syntax: exit=0
 import: exit=0
 runtime: exit=0
semantic_score=1.00
total_score=1.00
primary_failure=UNKNOWN
```

A non-zero exit code on any line indicates a failing gate.

## 5. `pythalab-agent review`

Read-only validation report. Same gates as `validate`, but explicitly does not change files. Useful in CI or pre-commit hooks.

```bash
pythalab-agent review
```

## 6. `pythalab-agent repair`

Run a single repair pass against the current `algorithm.py`. Useful when validation fails and you want one focused fix attempt without restarting from scratch.

```bash
pythalab-agent repair --task "Fix latest validation failure"
pythalab-agent repair --backend fake
```

Without `--task` the default repair task is "Fix latest validation failure".

## 7. `pythalab-agent doctor`

Print a readiness table:

```bash
pythalab-agent doctor
```

Use this first whenever the agent misbehaves.

## 8. `pythalab-agent models`

```bash
pythalab-agent models list      # configured default + fallback
pythalab-agent models doctor    # probe Ollama, verify models exist
```

To use a different model for one workspace, drop a `configs/models.yaml`:

```yaml
default_model: qwen3:4b
fallback_model: qwen3:4b
base_url: http://localhost:11434
```

(Only Ollama is supported in 0.1.x.)

## 9. `pythalab-agent config`

```bash
pythalab-agent config show      # YAML dump of the merged config
pythalab-agent config doctor    # quick "target_file + default_model" summary
```

The merged configuration is the union of:

1. Built-in defaults (see [config/defaults.py](../src/pythalab_agent_cli/config/defaults.py)).
2. `configs/*.yaml` in the workspace root (`default.yaml`, `models.yaml`, `validation.yaml`, `security.yaml`, `prompts.yaml`).
3. CLI flags.

## 10. `pythalab-agent memory`

The runtime keeps an SQLite memory under `.pythalab-agent/memory.sqlite`.

```bash
pythalab-agent memory list             # show task records
pythalab-agent memory clear --yes      # wipe everything
```

## 11. Programmatic use

The CLI is a thin wrapper over `pythalab_agent_cli.app.commands`. To embed:

```python
from pathlib import Path
from pythalab_agent_cli.app.commands import run_command

result = run_command(
    repo_root=Path("./my-workspace"),
    task="Implement solve(n: int) -> int Fibonacci iteratively",
    backend="ollama",
    max_attempts=10,
    until_success=False,
)
print(result.status, result.changed_files)
```

The public Python API surface is intentionally narrow; rely on the CLI for stable behaviour.

## 12. CI integration example

```yaml
# .github/workflows/check.yml
name: pythalab-agent validate
on: [push, pull_request]
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e '.[dev]'
      - run: pythalab-agent review
```

`review` requires no Ollama and no model, which makes it safe for headless CI.
