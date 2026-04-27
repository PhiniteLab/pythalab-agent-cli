# Documentation index

This directory contains long-form documentation for `pythalab-agent-cli`. Each page describes the **actual 0.1.0 implementation**, not aspirational design.

| File                                                | Topic                                                                       |
| --------------------------------------------------- | --------------------------------------------------------------------------- |
| [overview.md](overview.md)                          | Public-facing summary: what the project is and is not.                       |
| [installation.md](installation.md)                  | Install steps for `uv` and `pip`, Ollama setup, GPU notes.                   |
| [usage.md](usage.md)                                | Every CLI command with worked examples.                                      |
| [architecture.md](architecture.md)                  | Module map and call graph.                                                   |
| [agent_loop.md](agent_loop.md)                      | Step-by-step description of `DirectAgentLoop`.                              |
| [validation_pipeline.md](validation_pipeline.md)    | The three subprocess validators and their exact commands.                    |
| [security_model.md](security_model.md)              | What the runtime enforces (and what it does not).                            |
| [memory_and_reward.md](memory_and_reward.md)        | SQLite schema and current persistence behaviour.                             |
| [qwen3_ollama_notes.md](qwen3_ollama_notes.md)      | Ollama tuning for `qwen3:4b` on 6 GB VRAM.                                  |
| [quality_report.md](quality_report.md)              | Test, lint, and live-run results for 0.1.0.                                  |
| [development_roadmap.md](development_roadmap.md)    | Honest list of unimplemented / partially implemented features.               |
| [references.md](references.md)                      | External references and prior art.                                           |
