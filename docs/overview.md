# Project Summary

`pythalab-agent-cli` is a local, validation-driven coding agent for small Ollama models. It runs entirely on the user's machine and is built around three principles:

1. **The model never writes files.** It returns structured JSON. The runtime owns every filesystem and shell action.
2. **Nothing is materialized without proof.** Generated code is staged as JSON, validated in a temporary workspace through syntax/import/lint/type/runtime/semantic gates, and only then written to `algorithm.py`.
3. **Small models, small surface.** The runtime supplies the public API (function/class signature, IO envelope) so a constrained model only fills in the body — one function or one class at a time.

## Audience

- Engineers and researchers who want a reproducible local coding loop with no cloud calls.
- Hardware-constrained users (6 GB VRAM class) running `qwen3:4b` through Ollama.
- Teams who need the agent's output to land inside a tight security and validation envelope.

## Default stack

| Layer       | Choice                                             |
| ----------- | -------------------------------------------------- |
| Model       | `qwen3:4b` via Ollama                              |
| Runtime     | Python 3.11+, Typer CLI, Rich progress             |
| Validation  | `py_compile`, `importlib`, `ruff`, `pyright`, `pytest`, deterministic semantic checks |
| Memory      | SQLite under `.pythalab-agent/memory.sqlite`        |
| Sandbox     | Local subprocess runner with allow-listed commands |

## What ships in 0.1.0

- Continuous staged-generation loop with attempt ledger (duplicate / stagnation detection).
- Ollama and deterministic fake backends.
- Eleven CLI commands: `init`, `run`, `chat`, `validate`, `review`, `repair`, `doctor`, `models`, `config`, `memory`, plus completion installers.
- Domain templates for AI/ML, RL, nonlinear control, classical control, simulation, visualization, and general algorithms.
- Strict JSON-first generation contract enforced with Pydantic.
- Path / command / code AST policies; no `shell=True`, no third-party imports by default.
- 6 GB VRAM-friendly defaults (`num_ctx: 4096`, short `num_predict`, `q8_0` KV cache).
- 34 unit / integration / golden tests; `ruff`, `pyright`, and `pytest` all green.

## What is intentionally out of scope for 0.1.0

- Multi-file edit mode (security policy keeps writes pinned to `algorithm.py`).
- Cloud LLM backends.
- Docker sandbox runner (interface is sketched but not enabled by default).
- Optional Qwen-Agent adapter (off by default).

## Where to start

- [README](../README.md) — quickstart and command reference.
- [Installation guide](installation.md) — full prerequisites and step-by-step setup.
- [Usage guide](usage.md) — every command with realistic examples.
- [Architecture](architecture.md) — module layout and data flow.
- [Agent loop](agent_loop.md) — staged generation and repair policy.
- [Validation pipeline](validation_pipeline.md) — gate-by-gate description.
- [Security model](security_model.md) — threat model and policy.
- [Roadmap](development_roadmap.md) — what comes after 0.1.x.
