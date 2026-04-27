# References

## Direct dependencies

- [Ollama](https://ollama.com/) — local model runtime. The CLI talks to its `/api/chat` endpoint.
- [`qwen3:4b` on Ollama](https://ollama.com/library/qwen3) — the default and only required model.
- [Typer](https://typer.tiangolo.com/) — CLI framework.
- [Rich](https://rich.readthedocs.io/) — terminal rendering for the progress observer.
- [HTTPX](https://www.python-httpx.org/) — HTTP client for the Ollama endpoint, including NDJSON streaming.
- [Pydantic v2](https://docs.pydantic.dev/) — config schema.
- [PyYAML](https://pyyaml.org/) — config loader.

## Development tooling

- [uv](https://docs.astral.sh/uv/) — recommended environment manager.
- [Ruff](https://docs.astral.sh/ruff/) — linter and formatter.
- [Pyright](https://microsoft.github.io/pyright/) — type checker.
- [pytest](https://docs.pytest.org/) — test runner.

## Background reading

- [Qwen technical reports](https://github.com/QwenLM/Qwen3) — context about the underlying model family.
- [`runpy`](https://docs.python.org/3/library/runpy.html) — used by the runtime check.
- [`importlib.util.spec_from_file_location`](https://docs.python.org/3/library/importlib.html#importlib.util.spec_from_file_location) — used by the import check.
- [Python `compile`](https://docs.python.org/3/library/functions.html#compile) — used by the syntax check.
- [`subprocess` security considerations](https://docs.python.org/3/library/subprocess.html#security-considerations) — informs `LocalRunner`'s argument handling.

## Prior art and inspiration

- The continuous validate-then-repair loop pattern is common across local coding agents; this project keeps the loop deliberately small so that the entire run path fits in one file ([direct_loop.py](../src/pythalab_agent_cli/agent/direct_loop.py)).
- The "fenced code block + import smoke + runtime smoke" validation strategy was chosen to maximise signal per second on a 4 B parameter model on consumer hardware.
