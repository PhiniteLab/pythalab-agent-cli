# Installation Guide

This document is the long-form companion to the README quickstart. It targets new users on Linux, macOS, and Windows (WSL2 recommended).

## 1. System prerequisites

| Component | Minimum                         | Recommended                     |
| --------- | ------------------------------- | ------------------------------- |
| OS        | Linux / macOS / Windows + WSL2  | Ubuntu 22.04 LTS or newer       |
| Python    | 3.11                            | 3.12                            |
| Disk      | ~3 GB (model) + ~200 MB (deps)  | 10 GB free                      |
| RAM       | 8 GB                            | 16 GB                           |
| GPU       | None (CPU works, slow)          | NVIDIA 6 GB+ VRAM (RTX 3060)    |

Required CLI tools:

```bash
git --version
python3 --version    # must be 3.11+
```

Optional but recommended for development:

```bash
ruff --version
pyright --version
pytest --version
```

`ruff`, `pyright`, and `pytest` are pulled in automatically by the `dev` extra; you do not need to install them globally.

## 2. Install Ollama

Linux:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

macOS: download the installer from <https://ollama.com/download>.

Windows: install Ollama for Windows from <https://ollama.com/download>, or use the Linux installer inside WSL2.

Verify:

```bash
ollama --version
```

Pull the default model (~2.5 GB):

```bash
ollama pull qwen3:4b
```

Start the daemon with conservative options for 6 GB VRAM cards:

```bash
OLLAMA_NUM_PARALLEL=1 \
OLLAMA_MAX_LOADED_MODELS=1 \
OLLAMA_MAX_QUEUE=16 \
OLLAMA_FLASH_ATTENTION=1 \
OLLAMA_KV_CACHE_TYPE=q8_0 \
ollama serve
```

If you already run Ollama as a system service, you can keep the defaults and adjust later through `~/.ollama` or the systemd unit.

## 3. Clone the repository

```bash
git clone https://github.com/PhiniteLab/pythalab-agent-cli.git
cd pythalab-agent-cli
```

## 4. Create a virtual environment

### Option A — `uv` (fastest)

```bash
# Install uv if missing: https://docs.astral.sh/uv/
uv sync --extra dev
. .venv/bin/activate
```

### Option B — plain `pip`

```bash
python3 -m venv .venv
. .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -e '.[dev]'
```

### Option C — minimal install (no dev tools)

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
```

In option C, `ruff`, `pyright`, and `pytest` gates are skipped automatically; only syntax/import/runtime/semantic validation runs.

## 5. Verify the installation

```bash
pythalab-agent --help
pythalab-agent doctor
pythalab-agent models doctor
```

Expected `doctor` output (every row should be `True` after a full install):

```text
python_ok                 True
git_ok                    True
ruff_ok                   True
pyright_ok                True
pytest_ok                 True
ollama_ok                 True
default_model_available   True
fallback_model_available  True
```

If any row is `False`, see the [README troubleshooting table](../README.md#troubleshooting).

## 6. Initialise a workspace

```bash
mkdir my-workspace && cd my-workspace
pythalab-agent init .
```

Generated files:

```text
my-workspace/
├── algorithm.py
├── tests/test_algorithm.py
├── configs/
├── AGENTS.md
└── .pythalab-agent/
    ├── staged/
    └── memory.sqlite
```

`algorithm.py` is the single default write target. `tests/test_algorithm.py` is only writable in explicit test-generation mode.

## 7. Run the agent

Live model:

```bash
pythalab-agent run "Implement function solve(n: int) -> int that returns the n-th Fibonacci number iteratively"
```

Deterministic dry-run (no Ollama needed):

```bash
pythalab-agent run "Implement stable merge sort" --backend fake
```

Continuous mode (until validators pass or you press `Ctrl+C`):

```bash
pythalab-agent run "TASK" --until-success
```

## 8. Uninstall

```bash
pip uninstall pythalab-agent-cli
deactivate
rm -rf .venv my-workspace/.pythalab-agent
```

To remove the model:

```bash
ollama rm qwen3:4b
```

## 9. Common environment variables

| Variable                  | Effect                                                          |
| ------------------------- | --------------------------------------------------------------- |
| `OLLAMA_HOST`             | Override the Ollama base URL (default `http://localhost:11434`).|
| `OLLAMA_NUM_PARALLEL`     | Concurrent requests; keep at `1` for 6 GB VRAM cards.           |
| `OLLAMA_MAX_LOADED_MODELS`| Limit loaded models; `1` is the safe default.                   |
| `OLLAMA_FLASH_ATTENTION`  | `1` reduces memory pressure on supported GPUs.                  |
| `OLLAMA_KV_CACHE_TYPE`    | `q8_0` enables 8-bit KV cache where supported.                  |
| `PYTHALAB_AGENT_MODEL`    | Override the default model used by the CLI.                     |
