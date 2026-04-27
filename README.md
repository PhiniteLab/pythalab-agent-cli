# pythalab-agent-cli

A terminal-based, local coding agent that drives a small Ollama model through a tight chat-history loop. The model produces a complete `algorithm.py` inside a single fenced `\`\`\`python\`\`\`` block; the runtime writes it, runs syntax + import + runtime smoke checks, and feeds any failure back into the conversation so the model can self-correct.

The default and only required model is [`qwen3:4b`](https://ollama.com/library/qwen3). Everything runs on `localhost` — no cloud calls, no API keys, no telemetry.

> Project home: <https://github.com/PhiniteLab/pythalab-agent-cli>
>
> License: MIT • Python 3.11+ • Linux, macOS, Windows (WSL recommended)

---

## Table of contents

1. [Highlights](#highlights)
2. [How it works](#how-it-works)
3. [Requirements](#requirements)
4. [Installation](#installation)
5. [Ollama setup](#ollama-setup)
6. [First run](#first-run)
7. [Command reference](#command-reference)
8. [Configuration](#configuration)
9. [Validation pipeline](#validation-pipeline)
10. [Security boundaries](#security-boundaries)
11. [Project structure](#project-structure)
12. [Development](#development)
13. [Troubleshooting](#troubleshooting)
14. [Roadmap](#roadmap)
15. [License](#license)

---

## Highlights

- **Local-first.** Inference goes through Ollama on `localhost:11434`. No third-party API key, no telemetry.
- **Direct chat-history loop.** The model is asked, in plain chat, for the complete contents of `algorithm.py`. Each new attempt sees the prior assistant draft and the validator's complaint.
- **Fast smoke validation.** Three subprocess checks per attempt: `py_compile`, an `importlib` import, and `runpy.run_path(..., run_name="__main__")`. No ruff / pyright / pytest gates inside the loop.
- **Optional pip-install.** When the import check reports `ModuleNotFoundError`, the runtime can install the missing distribution and re-validate (interactive prompt, or `--auto-install` / `--no-install`).
- **Allow-listed validation commands.** The subprocess sandbox only runs an explicit allow-list (`python -m py_compile`, `python -I -c`, `pytest -q`, `ruff check`, `ruff format --check`, `pyright`, a couple of `git` reads). No `shell=True`, no `rm`, no `curl`, no `pip` from inside the run.
- **Conservative single-GPU tuning.** Defaults are aimed at an RTX 3060-class 6 GB card.
- **Reproducible.** Every attempt's source is snapshotted under `.pythalab-agent/attempts/`.

## How it works

```text
┌──────────┐  fenced ```python``` block  ┌──────────────────┐
│  qwen3   │ ──────────────────────────► │ extract & write  │
│  via     │                             │ algorithm.py     │
│  Ollama  │ ◄──────── feedback ──────── │ syntax → import  │
└──────────┘                             │     → runtime     │
                                         └────────┬─────────┘
                                                  │ pass
                                                  ▼
                                            ✓ complete
```

1. The user runs `pythalab-agent run "TASK"`.
2. The runtime resolves the workspace, loads config, and starts (or reuses) a local Ollama service.
3. A system prompt + the user's task + the current contents of `algorithm.py` are sent to `qwen3:4b` over `/api/chat`.
4. The model returns one fenced `\`\`\`python\`\`\`` block. The runtime extracts the code and writes it directly to `algorithm.py`.
5. Three subprocess validators run in order: syntax (`py_compile`), import (`importlib`), runtime (`runpy.run_path("algorithm.py", run_name="__main__")`).
6. If any validator fails, the runtime appends the assistant draft and a compact validator report to the chat history, then asks the model to retry.
7. On `ModuleNotFoundError` the runtime can pip-install the missing module(s) and re-run validation.
8. The loop stops on success, when the attempt budget is reached, or when the user hits `Ctrl+C` (`--until-success` mode).

The model never gets file-write or shell tools. The runtime is the only thing that touches disk or runs subprocesses.

## Requirements

| Component | Minimum                            | Notes                                          |
| --------- | ---------------------------------- | ---------------------------------------------- |
| Python    | 3.11                               | Tested on 3.11 and 3.12.                        |
| Ollama    | 0.3+                               | <https://ollama.com/download>                  |
| Disk      | ~3 GB                              | `qwen3:4b` weights.                             |
| RAM       | 8 GB                               | CPU-only inference works but is slow.          |
| GPU       | 6 GB VRAM                          | Defaults are tuned for an RTX 3060-class card. |
| Tools     | `git` (always), `ruff`/`pyright`/`pytest` (dev only) | The dev tools are not invoked by `run` itself; they are used by the project's own test suite. |

## Installation

### 1. Clone

```bash
git clone https://github.com/PhiniteLab/pythalab-agent-cli.git
cd pythalab-agent-cli
```

### 2. Create a virtual environment and install

`uv` (recommended):

```bash
uv sync --extra dev
. .venv/bin/activate
```

Plain `pip`:

```bash
python3 -m venv .venv
. .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -e '.[dev]'
```

Minimal (no dev tools):

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
```

### 3. Verify the install

```bash
pythalab-agent --help
pythalab-agent doctor
```

`doctor` prints a readiness table covering Python, git, ruff, pyright, pytest, Ollama, and model availability. Every `True` row means that tool is on `PATH`. The `run` loop only requires `python` and `ollama` (plus `qwen3:4b` pulled). The other rows describe what the project's own test suite needs.

## Ollama setup

### Install Ollama

Follow <https://ollama.com/download>. On Linux:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### Pull the default model

```bash
ollama pull qwen3:4b
```

### Run the daemon (recommended environment for 6 GB VRAM)

```bash
OLLAMA_NUM_PARALLEL=1 \
OLLAMA_MAX_LOADED_MODELS=1 \
OLLAMA_MAX_QUEUE=16 \
OLLAMA_FLASH_ATTENTION=1 \
OLLAMA_KV_CACHE_TYPE=q8_0 \
ollama serve
```

You can skip this step: when `pythalab-agent run` cannot reach a local Ollama daemon, it starts `ollama serve` itself with the same conservative environment and stops it after the run.

Confirm the model is reachable:

```bash
pythalab-agent models doctor
```

You should see `qwen3:4b: True`.

## First run

```bash
mkdir my-workspace && cd my-workspace
pythalab-agent init .
pythalab-agent run "Implement function solve(n: int) -> int that returns the n-th Fibonacci number iteratively"
```

`init` creates:

```text
my-workspace/
├── algorithm.py             # generation target (placeholder until first run)
├── tests/test_algorithm.py  # smoke import test
├── configs/                 # per-workspace config overrides (optional)
├── AGENTS.md                # untrusted-data instruction file
└── .pythalab-agent/
    ├── attempts/            # per-attempt code snapshots
    ├── logs/
    └── memory.sqlite        # task/strategy schema (currently unused at runtime)
```

While the agent runs, every milestone is printed (`preflight`, `generate`, `validate`, `regenerate`, `complete`). The final summary table reports `task_id`, `status`, `total_attempts`, and `primary_failure` (`SYNTAX`, `IMPORT`, `RUNTIME`, `SEMANTIC`, or `NONE`).

### Without a live model

A deterministic fake backend is built in for development, demos, and CI:

```bash
pythalab-agent run "Implement stable merge sort" --backend fake
```

It exercises the full direct-generation pipeline without touching Ollama.

## Command reference

| Command                                      | Purpose                                                                  |
| -------------------------------------------- | ------------------------------------------------------------------------ |
| `pythalab-agent init [PATH]`                 | Scaffold a workspace (`algorithm.py`, `tests/`, `.pythalab-agent/`).     |
| `pythalab-agent run "TASK"`                  | Run the direct chat-history loop until success or attempt budget.        |
| `pythalab-agent run "TASK" --max-attempts N` | Override the per-call attempt budget (default: `direct.max_attempts = 10`). |
| `pythalab-agent run "TASK" --until-success`  | Foreground continuous mode, interruptible with `Ctrl+C`.                 |
| `pythalab-agent run --backend fake`          | Use the deterministic fake model.                                        |
| `pythalab-agent run --auto-install`          | Auto-install missing PyPI packages reported by the import check.         |
| `pythalab-agent run --no-install`            | Never install; always feed the import error back to the model.           |
| `pythalab-agent chat`                        | Interactive REPL: type a task, get one full generation cycle, repeat.    |
| `pythalab-agent validate`                    | Run the validation pipeline (syntax + import + runtime).                 |
| `pythalab-agent review`                      | Same as `validate`, never changes files; for CI.                         |
| `pythalab-agent repair [--task TEXT]`        | Shortcut for `run` with a default repair task.                           |
| `pythalab-agent doctor`                      | Print Python / tool / Ollama readiness table.                            |
| `pythalab-agent models list`                 | Show configured default and fallback models.                             |
| `pythalab-agent models doctor`               | Probe Ollama and verify the configured models exist.                     |
| `pythalab-agent config show`                 | Dump the merged effective configuration (YAML).                          |
| `pythalab-agent config doctor`               | Show the resolved target file and default model.                         |
| `pythalab-agent memory list`                 | List task records stored in `.pythalab-agent/memory.sqlite`.             |
| `pythalab-agent memory clear --yes`          | Wipe the memory database for the current workspace.                      |

> Note: `memory list` is currently empty after every run. The SQLite schema exists for future task / strategy / reflection persistence; the direct-generation loop in 0.1.0 does not write to it.

Common flags for `run`:

```text
--backend         ollama | fake          (default: ollama)
--fake-scenario   default | <name>       (only with --backend fake)
--path            PATH                   workspace root (default: cwd)
--max-attempts    INTEGER                0 means "use config default"
--until-success                          run until validators pass
--auto-install                           install missing third-party packages
--no-install                             never install; feed errors back instead
```

## Configuration

Configuration is layered: built-in defaults < `configs/*.yaml` in the workspace. Inspect the merged result with:

```bash
pythalab-agent config show
```

The keys actually consumed by 0.1.0:

```yaml
repo:
  target_file: algorithm.py            # used by validators and init

agent:
  continue_until_success: false        # honored by `run`

validation:
  target_file: algorithm.py            # used by syntax + import + runtime checks
  import_timeout_sec: 30.0
  runtime_timeout_sec: 60.0
  run_runtime_check: true              # set false to skip the __main__ exec

models:
  default_model: qwen3:4b
  fallback_model: qwen3:4b
  base_url: http://localhost:11434
  profiles:                            # per-role Ollama options
    direct:
      think: true                      # streams <think>…</think> chunks live
      temperature: 0.4
      top_p: 0.9
      num_ctx: 16384
      num_predict: -1
      keep_alive: 30m

direct:
  profile_name: direct
  max_attempts: 10
  max_history_chars: 24000
  request_timeout_sec: 600.0
  save_attempt_snapshots: true
  error_summary_max_lines: 80
```

Other keys present in the schema (`agent.max_total_attempts`, `validation.run_ruff/run_pyright/run_pytest`, `security.*`, `memory.top_k_*`, etc.) are accepted by the loader but **not consumed** by the 0.1.0 runtime. They reflect the future feature surface; treat them as reservations, not guarantees.

Drop a `configs/default.yaml`, `configs/models.yaml`, `configs/validation.yaml`, or `configs/security.yaml` into your workspace to override per-project values.

## Validation pipeline

`pythalab-agent validate` and the inner loop both run the same three subprocess checks against `algorithm.py`, in order, stopping on the first failure:

| # | Check    | Command                                                    | Failure type |
| - | -------- | ---------------------------------------------------------- | ------------ |
| 1 | syntax   | `python -m py_compile algorithm.py` (in-process `compile()` is used; the command is reported in the result) | `SYNTAX`  |
| 2 | import   | `python -I -c "import importlib.util; spec=importlib.util.spec_from_file_location(...); spec.loader.exec_module(mod); print('ok')"` | `IMPORT`  |
| 3 | runtime  | `python -I -c "import runpy, sys; sys.argv=['algorithm.py']; runpy.run_path('algorithm.py', run_name='__main__')"` | `RUNTIME` |

The subprocess runner uses a stable environment: `PYTHONDONTWRITEBYTECODE=1`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` (when pytest is invoked elsewhere), `PYTHONPATH` extended with the workspace root and the venv's `purelib` / `platlib`, `stdin=DEVNULL`, output captured into temporary files, no shell.

`runtime_check` can be disabled by setting `validation.run_runtime_check: false`.

The `agent.run` summary line you see in the terminal (`semantic_score=1.00 total_score=1.00 primary_failure=UNKNOWN`) is the report's compact format; `semantic_score` and `total_score` are derived from the pass/fail of the three subprocess checks — the runtime does not run a separate semantic oracle in 0.1.0.

See [docs/validation_pipeline.md](docs/validation_pipeline.md) for full details.

## Security boundaries

What is enforced at runtime:

- **Subprocess command allow-list** ([command_policy.py](src/pythalab_agent_cli/sandbox/command_policy.py)). The validation runner only accepts the allow-listed prefixes (`python -m py_compile`, `python -I -c`, `ruff check`, `ruff format --check`, `pyright`, `pytest -q`, `git diff --`, `git status --short`). Forbidden tokens (`rm`, `curl`, `wget`, `ssh`, `scp`, `sudo`, `chmod`, `chown`, `pip`, `uv`) are rejected. No `shell=True`. No string interpolation into commands.
- **No model-driven shell or filesystem.** The model returns text. The runtime is the only component that writes files or starts processes.
- **Workspace-scoped state.** Snapshots, logs, and memory live under `.pythalab-agent/` in the workspace.

What is **not** enforced at runtime in 0.1.0:

- The `security` block in `configs/security.yaml` (`write_allowlist`, `deny_write_patterns`, `forbidden_code_patterns`) is **not** applied to model output. It is part of the future feature surface.
- Generated code is run as the current user via `runpy.run_path(..., run_name="__main__")`. **Always run the agent in a workspace you trust to execute model output.** Use a throwaway directory, a container, or an unprivileged user.
- Optional pip-install (`--auto-install`) installs into the active Python environment. Use a virtual environment.

The system prompt asks the model to avoid `eval`, `exec`, network calls, and similar risky patterns; that is a soft contract, not a sandbox. See [docs/security_model.md](docs/security_model.md) for the threat model and what is planned.

## Project structure

```text
pythalab-agent-cli/
├── src/pythalab_agent_cli/
│   ├── agent/        # DirectAgentLoop, observer protocol, run-result dataclass
│   ├── app/          # Typer CLI, command implementations, REPL
│   ├── config/       # Pydantic schema, defaults, layered YAML loader
│   ├── core/         # constants, exceptions, shared enums
│   ├── llm/          # Ollama HTTP client, fake client, fenced-block extractor, ollama service manager
│   ├── memory/       # SQLite schema and store (read by `memory list`)
│   ├── repo/         # workspace discovery and `init` scaffolding
│   ├── sandbox/      # subprocess runner + command allow-list
│   ├── ui/           # Rich progress observer + key/value table helper
│   └── validation/   # syntax / import / runtime checks + report dataclass + pipeline
├── configs/          # built-in YAML presets shipped with the package
├── docs/             # architecture, agent loop, validation, security, …
├── examples/         # sample tasks and a sample workspace
├── tests/            # unit, integration, and golden tests (34 in total)
└── pyproject.toml
```

## Development

```bash
uv sync --extra dev      # or: pip install -e '.[dev]'

ruff check .
ruff format --check .
pyright
pytest -q
```

The default test suite uses `FakeModelClient` and does not need a live Ollama. Tests marked `ollama` require a running daemon and `qwen3:4b` pulled.

## Troubleshooting

| Symptom                                              | Likely cause / fix                                                                 |
| ---------------------------------------------------- | ---------------------------------------------------------------------------------- |
| `pythalab-agent: command not found`                  | Activate the venv: `. .venv/bin/activate`.                                         |
| `models doctor` shows `ollama_ok: False`             | Start the daemon: `ollama serve` (or let the CLI start it on `run`).               |
| `qwen3:4b: False`                                    | Run `ollama pull qwen3:4b`.                                                        |
| `run` exits with `primary_failure=IMPORT`            | The model imported a missing package. Re-run with `--auto-install`, or let the model retry without the import. |
| `run` exits with `primary_failure=RUNTIME`           | The model's `__main__` block raised. The traceback is fed back; usually the next attempt fixes it. |
| `run` keeps hitting `direct.max_attempts`            | Use `--until-success` or raise `direct.max_attempts` in `configs/default.yaml`.    |
| Out-of-memory on GPU                                  | Lower `models.profiles.direct.num_ctx` (default 16384) toward 8192 or 4096.       |
| `validate` exits non-zero                            | Read the printed `[FAIL]` block; fix `algorithm.py` (or re-run `run`).             |

## Roadmap

- Wire the existing `security`, `validation.run_ruff/run_pyright/run_pytest`, and `agent.max_total_attempts` config keys into the runtime so they are not declarative-only.
- Persist task / strategy / reflection records into `.pythalab-agent/memory.sqlite` after each run.
- Optional Docker sandbox runner with `--network none` and tmpfs for the runtime check.
- Multi-file edit mode behind an explicit flag.

See [docs/development_roadmap.md](docs/development_roadmap.md).

## License

MIT — see [LICENSE](LICENSE).
