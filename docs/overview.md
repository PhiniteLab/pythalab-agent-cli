# Overview

`pythalab-agent-cli` is a local-only command-line coding agent that drives a small Ollama model (`qwen3:4b`) through a tight chat-history loop to produce a single Python file (`algorithm.py`) for a user-described task.

## What it is

- A Typer-based CLI installed as `pythalab-agent`.
- A direct chat-history generation loop. The model is asked, in plain chat, for the **complete** contents of `algorithm.py` inside one fenced ```` ```python ```` block.
- A three-step subprocess validator (syntax, import, runtime) that turns failures into the next user turn.
- A Pydantic-typed configuration layer that merges built-in defaults with `configs/*.yaml` in the workspace.
- A subprocess sandbox that only runs an allow-list of validation commands; never `shell=True`.

## What it is not (in 0.1.0)

- It is **not** a multi-file editing agent. It writes one file: `algorithm.py` (or whatever `repo.target_file` resolves to).
- It does **not** stage code as JSON, parse it through interface contracts, or use domain templates.
- It does **not** run `ruff`, `pyright`, `pytest`, or any "semantic" oracle inside the loop. The pipeline only does syntax, import, and runtime smoke checks.
- It does **not** persist task / reflection / strategy records to SQLite at runtime — the schema exists, but no writes happen during `run`.
- It does **not** sandbox model-generated code. Generated code runs as the current user via `runpy`. Always work in a throwaway directory, container, or unprivileged account.
- It does **not** call the network. The only outbound traffic is HTTP to a local Ollama daemon (and any pip-install you opt into via `--auto-install`).

## Audience

- Researchers and engineers who want a small, auditable agent loop they can read end-to-end in an afternoon.
- Anyone who wants to use `qwen3:4b` (or another small Ollama model) for short Python tasks without sending data to a vendor.

## High-level diagram

```text
        +------------------+
TASK -> | DirectAgentLoop  | --(chat)--> Ollama / qwen3:4b
        |                  | <--(text)--
        |  extract code    |
        |  write file      |
        |  validate (3x)   |
        +------------------+
                  |
                  v
            algorithm.py
                  |
                  v
        ValidationReport (syntax, import, runtime)
```

For the loop in detail see [agent_loop.md](agent_loop.md). For the validators see [validation_pipeline.md](validation_pipeline.md).
