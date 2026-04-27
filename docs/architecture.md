# Architecture

`pythalab-agent-cli` is a small Python package organised by component. Each module has a narrow responsibility; nothing reaches across layers except through the `DirectAgentLoop` orchestrator.

## Module map

```text
src/pythalab_agent_cli/
├── __main__.py            entry point: `python -m pythalab_agent_cli`
├── app/
│   ├── cli.py             Typer app, all commands and flags
│   ├── commands.py        run_command / init_command / validate_command / doctor_command
│   └── interactive.py     `chat` REPL
├── agent/
│   ├── direct_loop.py     DirectAgentLoop — the only generation loop
│   ├── observer.py        AgentObserver protocol (milestone events, thinking stream)
│   └── result.py          AgentRunResult dataclass
├── llm/
│   ├── base.py            LLMClient protocol + ChatMessage dataclass
│   ├── ollama_client.py   HTTPX client for /api/chat (blocking + NDJSON streaming)
│   ├── ollama_service.py  Optional `ollama serve` lifecycle manager
│   ├── fake_client.py     Deterministic offline client (3 scenarios)
│   └── code_extractor.py  Extracts the first fenced ```python``` block from text
├── validation/
│   ├── base.py            ValidationCheck protocol, CheckResult dataclass
│   ├── syntax_check.py    py_compile via in-process compile()
│   ├── import_check.py    `python -I -c "<importlib snippet>"`
│   ├── runtime_check.py   `python -I -c "<runpy snippet>"`
│   ├── pipeline.py        ValidationPipeline.run() — syntax → import → runtime
│   └── report.py          ValidationReport with per-check status + scores
├── sandbox/
│   ├── base.py            SubprocessRunner protocol
│   ├── command_policy.py  CommandPolicy — allow-list / forbidden-token check
│   └── local_runner.py    LocalRunner — actual subprocess.run wrapper
├── config/
│   ├── schema.py          Pydantic models for the entire config
│   ├── defaults.py        DEFAULT_CONFIG_NAMES (load order)
│   └── loader.py          Layered YAML loader
├── core/
│   ├── constants.py       DEFAULT_MODEL, DEFAULT_BASE_URL, env var names, …
│   ├── errors.py          PythalabError + 6 subclasses
│   └── types.py           TaskType, FailureType, ValidationStatus, WorkspacePaths
├── memory/
│   ├── models.py          dataclasses: TaskRecord, ArtifactRecord, …
│   ├── migrations.py      single-shot CREATE TABLE migration
│   └── sqlite_store.py    SQLiteStore — read/write API (read-only at runtime in 0.1.0)
├── repo/
│   └── workspace.py       initialize_workspace + workspace path discovery
└── ui/
    ├── progress.py        RichAgentObserver — Rich spinner + thinking stream
    └── tables.py          key_value_table helper
```

## Call graph for `pythalab-agent run`

```text
app/cli.py:run
  └─ commands.run_command(repo_root, task, ...)
       ├─ load_config(repo_root)              → config/loader.py
       ├─ build LLMClient                     → llm/ollama_client.py | llm/fake_client.py
       │     └─ OllamaServiceManager.ensure() → llm/ollama_service.py (optional)
       ├─ build ValidationPipeline            → validation/pipeline.py
       │     wraps SyntaxCheck, ImportCheck, RuntimeCheck
       │     each Check uses LocalRunner      → sandbox/local_runner.py
       │       which consults CommandPolicy   → sandbox/command_policy.py
       ├─ build SQLiteStore                   → memory/sqlite_store.py (read-only)
       ├─ build RichAgentObserver             → ui/progress.py
       └─ DirectAgentLoop(...).run()          → agent/direct_loop.py
              ├─ extract_python_code()        → llm/code_extractor.py
              ├─ write target_file            → workspace
              ├─ pipeline.run()               → ValidationReport
              └─ on import failure: optional MissingPackagePrompt → pip install
```

Every external interaction (HTTP, subprocess, filesystem) is funneled through one of: `OllamaClient`, `LocalRunner`, or direct `pathlib` writes scoped to the workspace root.

## Public dataclasses

| Type                | File                          | Used for                                                          |
| ------------------- | ----------------------------- | ----------------------------------------------------------------- |
| `ChatMessage`       | `llm/base.py`                 | One turn in the chat history (`role`, `content`).                 |
| `CheckResult`       | `validation/base.py`          | Output of one validator (`name`, `status`, `command`, `summary`). |
| `ValidationReport`  | `validation/report.py`        | Aggregate of all `CheckResult`s + scores + primary failure type.  |
| `AgentRunResult`    | `agent/result.py`             | Final summary returned by `DirectAgentLoop.run()`.                |
| `WorkspacePaths`    | `core/types.py`               | Resolved paths (`root`, `target_file`, `state_dir`, …).           |
| `DoctorReport`      | `app/commands.py`             | Output of `pythalab-agent doctor`.                                |

## What is intentionally absent

- No JSON code-staging layer. Generated text goes from the model straight into `algorithm.py`.
- No `ComponentSpec` / `InterfaceSpec` / domain template loader.
- No planner / patcher / reviewer / reflection / json-repair model profiles in the run path. The schema reserves them; only the `direct` profile is consumed.
- No `ruff`, `pyright`, `pytest`, or AST safety gate inside the validation pipeline.
- No reward / bandit / strategy update during `run`.

These are documented as roadmap items; see [development_roadmap.md](development_roadmap.md).
