# Installation

`pythalab-agent-cli` is a Python 3.11+ package. It depends only on Ollama at runtime.

## 1. Clone the repository

```bash
git clone https://github.com/PhiniteLab/pythalab-agent-cli.git
cd pythalab-agent-cli
```

## 2. Create an environment

### Option A — `uv` (recommended)

```bash
uv sync --extra dev
. .venv/bin/activate
```

### Option B — plain `pip`

```bash
python3 -m venv .venv
. .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -e '.[dev]'
```

### Option C — runtime only (no dev tools)

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
```

Dev extras add `ruff`, `pyright`, `pytest`, and `pytest-cov` for working on the project itself. They are **not** required to run the agent.

## 3. Install Ollama and pull `qwen3:4b`

Follow <https://ollama.com/download>. On Linux:

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen3:4b
```

This is the only model the runtime needs. `models.fallback_model` defaults to the same image, so a single pull covers both slots.

## 4. Recommended Ollama environment

For a 6 GB-class GPU (e.g. RTX 3060):

```bash
OLLAMA_NUM_PARALLEL=1 \
OLLAMA_MAX_LOADED_MODELS=1 \
OLLAMA_MAX_QUEUE=16 \
OLLAMA_FLASH_ATTENTION=1 \
OLLAMA_KV_CACHE_TYPE=q8_0 \
ollama serve
```

You can skip running `ollama serve` manually. When `pythalab-agent run` cannot reach `http://localhost:11434`, the `OllamaServiceManager` (see [src/pythalab_agent_cli/llm/ollama_service.py](../src/pythalab_agent_cli/llm/ollama_service.py)) starts the daemon with the same conservative environment and stops it after the run.

CPU-only inference works but is slow; expect tens of seconds per attempt.

## 5. Verify

```bash
pythalab-agent --help
pythalab-agent doctor
pythalab-agent models doctor
```

`doctor` prints a readiness table:

| Field                       | Meaning                                                       |
| --------------------------- | ------------------------------------------------------------- |
| `python_ok`                 | The interpreter is on `PATH`.                                 |
| `git_ok`                    | `git` is installed (used by `git diff/status` allow-list).    |
| `ruff_ok`, `pyright_ok`, `pytest_ok` | Tools are present (used by the project's own test suite, **not** by the run loop). |
| `ollama_ok`                 | `http://localhost:11434/api/tags` responded.                  |
| `default_model_available`   | `qwen3:4b` is in `ollama list`.                               |
| `fallback_model_available`  | The configured fallback model is in `ollama list`.            |

A `True` on `python_ok`, `ollama_ok`, and `default_model_available` is enough to use `pythalab-agent run`.
