# Usage

Every CLI command lives under `pythalab-agent`. Run `pythalab-agent --help` for a generated overview, and `pythalab-agent <command> --help` for per-command flags.

This page documents what each command actually does in 0.1.0.

## `init`

```bash
pythalab-agent init [PATH]
```

Scaffolds a workspace at `PATH` (default: current directory):

```text
PATH/
├── algorithm.py             # placeholder with `def solve(...)`
├── tests/test_algorithm.py  # smoke import test
├── configs/
│   ├── default.yaml
│   ├── models.yaml
│   ├── validation.yaml
│   └── security.yaml
├── AGENTS.md                # untrusted-data instruction file
└── .pythalab-agent/
    ├── attempts/            # populated by `run`
    ├── logs/
    └── memory.sqlite        # schema present; no writes in 0.1.0
```

It will not overwrite an existing `algorithm.py`, `tests/test_algorithm.py`, or `AGENTS.md`. Re-running `init` on an existing workspace is safe.

## `run`

```bash
pythalab-agent run "TASK" [OPTIONS]
```

Runs the direct chat-history generation loop until a validator passes or the attempt budget is exhausted.

Common options:

| Flag                              | Meaning                                                                 |
| --------------------------------- | ----------------------------------------------------------------------- |
| `--backend ollama|fake`           | Choose the LLM client. `fake` is deterministic and offline.             |
| `--fake-scenario NAME`            | Use a named fake scenario (`default`, `syntax_then_repair`, `no_block_first`). |
| `--path PATH`                     | Workspace root (default: cwd).                                          |
| `--max-attempts N`                | Override `direct.max_attempts` for this call. `0` means "use config".   |
| `--until-success`                 | Foreground continuous mode; runs forever until a pass or `Ctrl+C`.      |
| `--auto-install`                  | On `ModuleNotFoundError`, auto-install the missing distribution.        |
| `--no-install`                    | Never install; always feed import errors back to the model.             |

Examples:

```bash
pythalab-agent run "Implement solve(n) returning the n-th Fibonacci number iteratively"

pythalab-agent run "Implement merge sort as solve(items)" --until-success

pythalab-agent run "Plot a sine wave" --auto-install

pythalab-agent run "Stable sort" --backend fake
```

The terminal shows live milestones (`preflight`, `generate`, `validate`, `regenerate`, `complete`) and, when the model is configured with `think: true`, streams the model's `<think>…</think>` content. Each attempt's source is snapshotted to `.pythalab-agent/attempts/task-XXXXXX-attempt-YYY.py`.

The exit code is `0` on success and `1` if the budget is exhausted without a passing validation.

## `chat`

```bash
pythalab-agent chat
```

Tiny REPL: type a task, press Enter, watch one full `run` cycle, repeat. `Ctrl+D` or `Ctrl+C` exits.

## `validate`

```bash
pythalab-agent validate [--path PATH]
```

Runs the validation pipeline (syntax → import → runtime) against the current `algorithm.py` without invoking the model. Useful for CI or for verifying a file you wrote by hand.

Exit codes: `0` on pass, `1` on any failure. The full report is printed to stdout.

## `review`

```bash
pythalab-agent review [--path PATH]
```

Equivalent to `validate`. Provided as a separate verb for CI pipelines that want a non-mutating check name.

## `repair`

```bash
pythalab-agent repair [--task TEXT]
```

Shortcut for `run` with a default task ("Fix the failing validators in algorithm.py and produce a passing implementation."). Pass `--task` to override.

## `doctor`

```bash
pythalab-agent doctor
```

Prints a readiness table for Python, `git`, `ruff`, `pyright`, `pytest`, Ollama, and the configured default / fallback models. See [installation.md](installation.md#5-verify) for what each row means.

## `config show` / `config doctor`

```bash
pythalab-agent config show           # full merged config as YAML
pythalab-agent config doctor         # workspace + target_file + default_model summary
```

`config show` writes the merged effective configuration (built-in defaults overlaid with `configs/*.yaml`). Use it to confirm a setting actually took effect.

## `models list` / `models doctor`

```bash
pythalab-agent models list           # default and fallback names
pythalab-agent models doctor         # probes Ollama + verifies the names exist
```

## `memory list` / `memory clear`

```bash
pythalab-agent memory list                 # rows from .pythalab-agent/memory.sqlite
pythalab-agent memory clear --yes          # truncate the database
```

In 0.1.0 the runtime does not persist anything to memory during `run`, so `memory list` returns an empty table immediately after a run. The schema and store are functional and used by the project's own tests; CLI integration of writes is on the roadmap.
