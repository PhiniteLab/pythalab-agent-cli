# Quality report — 0.1.0

This page records the verifiable quality signals for the 0.1.0 release.

## Test suite

```bash
pytest -q
```

- 34 tests across `tests/unit/`, `tests/integration/`, and `tests/golden/`.
- All tests pass without a live Ollama. Tests that exercise the model use `FakeModelClient` ([llm/fake_client.py](../src/pythalab_agent_cli/llm/fake_client.py)).
- The integration test `tests/integration/test_continuous_attempt_loop.py` exercises `--until-success` with a fake scenario that fails on the first attempt and succeeds on the second.

## Lint and types

```bash
ruff check .
ruff format --check .
pyright
```

- `ruff check` reports zero issues in `src/`, `tests/`, and `docs/`. The only outstanding hit is a pre-existing `SIM108` in [examples/workspaces/simple_algorithm_project/algorithm.py](../examples/workspaces/simple_algorithm_project/algorithm.py); it is example content and is intentionally left as-is.
- `ruff format --check .` is clean.
- `pyright` reports zero errors against [pyrightconfig.json](../pyrightconfig.json).

## Live `qwen3:4b` smoke run

A live end-to-end run was performed on a development machine with `ollama` 0.x and `qwen3:4b` on a 6 GB GPU:

```bash
mkdir -p real-test/ws && cd real-test/ws
pythalab-agent init .
pythalab-agent run "Implement function solve(n: int) -> int returning the n-th Fibonacci number iteratively"
```

Result: a passing implementation in `algorithm.py` after two attempts. `validate` reported `passed=True`, `total_score=1.0`, and `primary_failure=NONE`. Each attempt's source is preserved in `.pythalab-agent/attempts/`.

The same live run was repeated for:

- `pythalab-agent doctor` — all rows green except those depending on optional tools the host did not have installed.
- `pythalab-agent models doctor` — `ollama_ok: True`, `qwen3:4b: True`.
- `pythalab-agent config show` / `config doctor` — produced a YAML dump matching the merged defaults plus the workspace `configs/`.
- `pythalab-agent validate`, `pythalab-agent review`, `pythalab-agent repair` — exercised against the workspace produced above.
- `pythalab-agent memory list` — empty (expected, see [memory_and_reward.md](memory_and_reward.md)).

## Known gaps (not regressions)

The following are documented limitations of 0.1.0, not bugs:

- The validation pipeline does not run `ruff`, `pyright`, `pytest`, or any AST-level safety scan. The corresponding `validation.run_*` config keys are inert in 0.1.0.
- `security.write_allowlist`, `security.deny_write_patterns`, and `security.forbidden_code_patterns` are accepted by the config schema but are not consulted by the runtime.
- `DirectAgentLoop.run` does not write to the SQLite memory store. `pythalab-agent memory list` is empty after `run`.
- The `planner`, `patcher`, `code_unit`, `repairer`, `reviewer`, `reflection`, and `json_repair` model profiles in `configs/models.yaml` are reserved for future work; only `direct` is consumed.

See [development_roadmap.md](development_roadmap.md) for the planned remediation order.

## How to reproduce

```bash
git clone https://github.com/PhiniteLab/pythalab-agent-cli.git
cd pythalab-agent-cli
uv sync --extra dev
. .venv/bin/activate

ruff check .
ruff format --check .
pyright
pytest -q
```

For the live model run, additionally:

```bash
ollama pull qwen3:4b
mkdir -p /tmp/pythalab-smoke && cd /tmp/pythalab-smoke
pythalab-agent init .
pythalab-agent run "Implement solve(n: int) -> int returning the n-th Fibonacci number iteratively"
```
