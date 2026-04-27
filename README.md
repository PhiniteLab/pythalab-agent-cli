# pythalab-agent-cli

`pythalab-agent-cli` is a terminal-based, validation-driven local coding agent built around small Ollama models. It is designed for engineers and researchers who want a deterministic, security-bounded code generation loop running entirely on their own machine — no cloud calls, no remote inference, no hidden network traffic.

The default and only required model is [`qwen3:4b`](https://ollama.com/library/qwen3). Generated code is staged as JSON, validated in a temporary workspace, and only materialized to a real Python file after every gate passes.

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
10. [Security model](#security-model)
11. [Project structure](#project-structure)
12. [Development](#development)
13. [Troubleshooting](#troubleshooting)
14. [Roadmap](#roadmap)
15. [License](#license)

---

## Highlights

- **Local-first.** All inference happens through Ollama on `localhost`. No third-party API key, no telemetry.
- **Validation before write.** A staged JSON draft must pass syntax, import, lint, type, runtime, and semantic gates before the runtime overwrites `algorithm.py`.
- **Small-model discipline.** The runtime supplies the public API (function/class signature, IO envelope) so the model only fills in the body.
- **Deterministic continuous loop.** The agent regenerates, repairs, and retries with a transparent attempt ledger that detects duplicates and stagnation.
- **Sandboxed execution.** No `shell=True`, no arbitrary imports, no writes outside the workspace, deny-list for `.env`/`.git`/`.ssh` and similar paths.
- **Reproducible.** Every prompt, validation result, and reward is stored in an on-disk SQLite memory under `.pythalab-agent/`.

## How it works

```text
        ┌────────┐    JSON only    ┌───────────────┐   pass    ┌──────────────┐
 user → │ planner│ ───────────────►│ code-unit gen │──────────►│ stage as JSON│
        └────────┘                 └───────────────┘           └──────┬───────┘
                                                                      │
                                                            validate in temp ws
                                                                      │
                                          fail ◄──── attempt ledger ──┴── pass ──┐
                                            │                                    ▼
                                       repair JSON                       materialize → algorithm.py
                                       (≤ max_repairs)                          │
                                            │                              final validation
                                            └──── max_repairs reached ─────► fresh candidate
```

The model is asked for **one function or one class at a time**. Its output is parsed into a `CodeUnitDraftResponse` and stored under `.pythalab-agent/staged/`. Only after every validator passes is the code written to `algorithm.py` and validated again.

## Requirements

| Requirement | Minimum                                 | Notes                                                                     |
| ----------- | --------------------------------------- | ------------------------------------------------------------------------- |
| Python      | 3.11+                                   | Tested on 3.11 and 3.12.                                                  |
| Ollama      | 0.3+                                    | <https://ollama.com/download>                                             |
| Disk        | ~3 GB                                   | `qwen3:4b` weights.                                                       |
| RAM         | 8 GB                                    | CPU-only inference works but is slow.                                     |
| GPU         | 6 GB VRAM                               | Defaults are tuned for an RTX 3060-class card (`num_ctx: 4096`, `q8_0`). |
| Tools       | `git`, `ruff`, `pyright`, `pytest`      | `ruff`, `pyright`, `pytest` are installed via the `dev` extra.            |

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

### 3. Verify the install

```bash
pythalab-agent --help
pythalab-agent doctor
```

`doctor` prints a readiness table covering Python, git, ruff, pyright, pytest, Ollama, and model availability. Every `True` row means the corresponding gate is operational.

## Ollama setup

### Install Ollama

Follow the official instructions at <https://ollama.com/download>. On Linux:

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

Confirm the model is reachable:

```bash
pythalab-agent models doctor
```

You should see `qwen3:4b: True`. If not, repeat `ollama pull qwen3:4b` and check that `ollama serve` is running on `http://localhost:11434`.

## First run

Initialise a workspace and generate a small algorithm:

```bash
mkdir my-workspace && cd my-workspace
pythalab-agent init .
pythalab-agent run "Implement function solve(n: int) -> int that returns the n-th Fibonacci number iteratively"
```

`init` creates:

```text
my-workspace/
├── algorithm.py           # generation target
├── tests/
│   └── test_algorithm.py  # only writable in explicit test mode
├── configs/               # per-workspace overrides (optional)
├── AGENTS.md              # untrusted-data instruction file
└── .pythalab-agent/       # staged drafts, attempt snapshots, memory.sqlite
```

While the agent runs, every milestone is printed (`generate`, `validate`, `repair`, `materialize`, `complete`). The final summary table reports `task_id`, `status`, `total_attempts`, and `primary_failure`.

### Without a live model

A deterministic fake backend is built in for development, demos, and CI:

```bash
pythalab-agent run "Implement stable merge sort" --backend fake
```

It exercises the full staged pipeline without touching Ollama.

## Command reference

| Command                                      | Purpose                                                                  |
| -------------------------------------------- | ------------------------------------------------------------------------ |
| `pythalab-agent init [PATH]`                 | Scaffold a workspace (`algorithm.py`, `tests/`, `.pythalab-agent/`).     |
| `pythalab-agent run "TASK"`                  | Run the staged generation loop until success or attempt budget.          |
| `pythalab-agent run "TASK" --max-attempts N` | Override `agent.max_total_attempts`.                                     |
| `pythalab-agent run "TASK" --until-success`  | Foreground continuous mode, interruptible with `Ctrl+C`.                 |
| `pythalab-agent run --backend fake`          | Use the deterministic fake model.                                        |
| `pythalab-agent chat`                        | Interactive REPL: type a task, get a staged generation cycle.            |
| `pythalab-agent validate`                    | Run syntax + import + runtime + semantic validation on the workspace.    |
| `pythalab-agent review`                      | Read-only validation report (no file changes).                           |
| `pythalab-agent repair [--task TEXT]`        | Run a single repair pass on the current `algorithm.py`.                  |
| `pythalab-agent doctor`                      | Print Python / tool / Ollama readiness table.                            |
| `pythalab-agent models list`                 | Show configured default and fallback models.                             |
| `pythalab-agent models doctor`               | Probe Ollama and verify the configured models exist.                     |
| `pythalab-agent config show`                 | Dump the merged effective configuration (YAML).                          |
| `pythalab-agent config doctor`               | Show the resolved target file and default model.                         |
| `pythalab-agent memory list`                 | List task records stored in `.pythalab-agent/memory.sqlite`.             |
| `pythalab-agent memory clear --yes`          | Wipe the memory database for the current workspace.                      |

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

Configuration is layered: built-in defaults < `configs/*.yaml` in the workspace < CLI flags. Inspect the merged result with:

```bash
pythalab-agent config show
```

The most important keys:

```yaml
agent:
  max_total_attempts: 25      # hard cap unless --until-success
  max_repairs: 3              # repair tries per staged candidate
  max_duplicate_drafts: 2     # abandon candidate after N duplicate digests
  max_same_failure_streak: 4  # abandon candidate after N identical failures
  min_score_improvement: 0.01 # required progress between repairs
  default_backend: ollama

models:
  default_model: qwen3:4b
  fallback_model: qwen3:4b
  base_url: http://localhost:11434
  default_options:
    num_ctx: 4096
    repeat_penalty: 1.05
    top_p: 0.7

validation:
  target_file: algorithm.py
  run_ruff: true
  run_pyright: true
  run_pytest: true
  run_runtime_check: true
  run_semantic: true
  semantic_threshold: 0.5

security:
  workspace_only: true
  write_allowlist: [algorithm.py]
  explicit_test_write_allowlist: [tests/test_algorithm.py]
  deny_write_patterns: ['.env', '.git/**', '.ssh/**', '**/*token*', '**/*secret*']
  forbidden_code_patterns: ['eval(', 'exec(', 'subprocess', 'socket', 'urllib', 'requests', 'httpx']
```

Drop a `configs/default.yaml` (or `models.yaml`, `validation.yaml`, `security.yaml`) into your workspace to override per-project values.

## Validation pipeline

Every staged draft and the final materialized file go through:

```bash
python -m py_compile algorithm.py
python -I -c "import importlib.util; spec=importlib.util.spec_from_file_location('algorithm','algorithm.py'); mod=importlib.util.module_from_spec(spec); assert spec.loader is not None; spec.loader.exec_module(mod)"
ruff check .
ruff format --check .
pyright
pytest -q
```

plus a deterministic semantic checklist tied to the task domain. The runner uses a stable subprocess environment to avoid `__pycache__`, plugin autoload, and parent-process pipe leaks. Optional gates (`ruff`, `pyright`, `pytest`) are skipped when the binaries are missing — install the `dev` extra to enable them.

See [docs/validation_pipeline.md](docs/validation_pipeline.md) for the gate-by-gate description and exit-code conventions.

## Security model

- **Model is data, not control.** The LLM never gets file-write or shell tools. It returns JSON; the runtime validates and applies it.
- **Path policy.** The initial write allow-list is `algorithm.py` only. `tests/test_algorithm.py` is allowed only in explicit test-generation mode. `.env`, `.git/**`, `.ssh/**`, `pyproject.toml`, `configs/security.yaml`, and any path outside the workspace are denied.
- **Command policy.** Validation commands are exact/prefix allow-listed. The runtime never uses `shell=True`. Forbidden during runs: `rm`, `curl`, `wget`, `ssh`, `scp`, `sudo`, `chmod`, `chown`, `pip`, `uv`.
- **Code policy.** Staged code is parsed with the standard library `ast`. Drafts containing `eval`, `exec`, `subprocess`, `socket`, `urllib`, `requests`, `httpx`, top-level executable statements, or hidden global state are rejected before they ever touch the filesystem.
- **Prompt-injection guard.** Repository-local instruction files (`AGENTS.md`, `CLAUDE.md`, `.cursorrules`, comments, tests, logs) are treated as untrusted data and cannot override runtime policy.
- **No secret persistence.** Memory storage is local SQLite; secrets are never read or written by design.

Full details: [docs/security_model.md](docs/security_model.md).

## Project structure

```text
pythalab-agent-cli/
├── src/pythalab_agent_cli/
│   ├── agent/        # direct generation loop, observers, results
│   ├── app/          # Typer CLI, command implementations, REPL
│   ├── config/       # schema, defaults, layered loader
│   ├── core/         # constants, errors, shared types
│   ├── llm/          # Ollama client, fake client, code extractor
│   ├── memory/       # SQLite store and migrations
│   ├── repo/         # workspace discovery and scaffolding
│   ├── sandbox/      # local subprocess runner + command policy
│   ├── ui/           # progress reporting and tables
│   └── validation/   # syntax, import, runtime, pipeline, report
├── configs/          # default YAML configuration
├── docs/             # architecture, agent loop, validation, security, ...
├── examples/         # sample tasks and a sample workspace
├── tests/            # unit, integration, and golden tests
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

The default test suite uses `FakeModelClient` and does not need a live Ollama. Tests marked `ollama` require a running daemon and the model pulled.

To work on the CLI in editable mode:

```bash
pip install -e '.[dev]'
pythalab-agent --help
```

## Troubleshooting

| Symptom                                              | Likely cause / fix                                                                 |
| ---------------------------------------------------- | ---------------------------------------------------------------------------------- |
| `pythalab-agent: command not found`                  | Activate the venv: `. .venv/bin/activate`.                                         |
| `models doctor` shows `ollama_ok: False`             | Start the daemon: `ollama serve`.                                                  |
| `qwen3:4b: False`                                    | Run `ollama pull qwen3:4b`.                                                        |
| `run` exits with `primary_failure=SECURITY`          | Generated code hit a forbidden import/call. Check `.pythalab-agent/staged/`.       |
| `run` keeps hitting `max_total_attempts`             | Use `--until-success` or raise `agent.max_total_attempts` in `configs/default.yaml`. |
| Out-of-memory on GPU                                  | Lower `models.default_options.num_ctx` or use the recommended Ollama env vars.    |
| `validate` reports `pyright skipped`                 | Install the `dev` extra: `pip install -e '.[dev]'`.                                |

## Roadmap

- Multi-file edit mode (off by default).
- Docker-based sandbox runner with `--network none` and tmpfs.
- Optional Qwen-Agent adapter for richer tool routing.
- Configurable semantic-validation oracles per domain.

See [docs/development_roadmap.md](docs/development_roadmap.md).

## License

MIT — see [LICENSE](LICENSE).
