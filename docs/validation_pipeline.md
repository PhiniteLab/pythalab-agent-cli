# Validation pipeline

`ValidationPipeline` (in [src/pythalab_agent_cli/validation/pipeline.py](../src/pythalab_agent_cli/validation/pipeline.py)) runs three checks against `algorithm.py`, in order, stopping on the first failure. The result is a `ValidationReport` with one `CheckResult` per check.

This is the **only** validation surface in 0.1.0. The pipeline does **not** run `ruff`, `pyright`, `pytest`, an AST safety scan, or a semantic oracle, even though config keys for those exist on `ValidationConfig`.

## The three checks

### 1. Syntax check

Source: [validation/syntax_check.py](../src/pythalab_agent_cli/validation/syntax_check.py).

- Reads the file's text and calls Python's built-in `compile(source, str(path), "exec")` in-process.
- On `SyntaxError`, returns `status=FAIL`, `failure=SYNTAX`, `summary` containing the error class, line/column, and message.
- The reported `command` for transparency is `python -m py_compile <path>`.

### 2. Import check

Source: [validation/import_check.py](../src/pythalab_agent_cli/validation/import_check.py).

Subprocess command:

```bash
python -I -c "
import importlib.util, sys
spec = importlib.util.spec_from_file_location('algorithm', '<abs path>')
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)
print('ok')
"
```

- `-I` (isolated mode) suppresses the user site directory and `PYTHON*` env vars (but the runner re-injects `PYTHONPATH` for the workspace + venv).
- `stdin=DEVNULL`, output captured into temp files, timeout `validation.import_timeout_sec` (default 30 s).
- Maps `ModuleNotFoundError` → `status=FAIL`, `failure=IMPORT` with the missing module name extracted for the optional pip-install prompt.

### 3. Runtime check

Source: [validation/runtime_check.py](../src/pythalab_agent_cli/validation/runtime_check.py).

Subprocess command:

```bash
python -I -c "
import runpy, sys
sys.argv = ['algorithm.py']
runpy.run_path('<abs path>', run_name='__main__')
"
```

- Executes any `if __name__ == \"__main__\":` block in the generated file.
- `status=FAIL` on any unhandled exception or non-zero exit; `failure=RUNTIME`.
- Timeout `validation.runtime_timeout_sec` (default 60 s).
- Disabled by setting `validation.run_runtime_check: false` in `configs/validation.yaml`.

## Subprocess hardening (LocalRunner)

All subprocess invocations go through [sandbox/local_runner.py](../src/pythalab_agent_cli/sandbox/local_runner.py):

- `subprocess.run(..., shell=False)`. Always.
- Argument list is validated by `CommandPolicy` first (see [security_model.md](security_model.md)).
- Environment is reset to a known set: inherits `PATH` and `HOME`, sets `PYTHONDONTWRITEBYTECODE=1`, extends `PYTHONPATH` with the workspace root and the venv's `purelib`/`platlib`.
- `stdin=DEVNULL`. Output is captured into `tempfile.NamedTemporaryFile` instances and bounded.
- A wall-clock timeout is enforced; on timeout, the result is reported as `FAIL` with a "command timed out" summary.

## ValidationReport

`ValidationReport` (in [validation/report.py](../src/pythalab_agent_cli/validation/report.py)) carries:

- `checks: list[CheckResult]` — one per check that ran.
- `primary_failure: FailureType` — `NONE`, `SYNTAX`, `IMPORT`, `RUNTIME`, or `UNKNOWN`.
- `total_score: float` — `1.0` on full pass, `0.0` otherwise.
- `semantic_score: float` — same value in 0.1.0; reserved for future per-check weighting.
- `passed: bool` — convenience flag.

## What it is **not**

- It is not a static analyzer. `ruff` / `pyright` are not invoked.
- It is not a test runner. `pytest -q` is not invoked.
- It is not a semantic correctness oracle. A pass means "imports cleanly and `__main__` did not throw" — it does not prove the function is correct for arbitrary inputs.

For unit-level correctness, write tests under `tests/` and run `pytest -q` yourself, or add a custom check in a future version (see [development_roadmap.md](development_roadmap.md)).

## Related files

- [validation/pipeline.py](../src/pythalab_agent_cli/validation/pipeline.py)
- [validation/syntax_check.py](../src/pythalab_agent_cli/validation/syntax_check.py)
- [validation/import_check.py](../src/pythalab_agent_cli/validation/import_check.py)
- [validation/runtime_check.py](../src/pythalab_agent_cli/validation/runtime_check.py)
- [validation/report.py](../src/pythalab_agent_cli/validation/report.py)
- [sandbox/local_runner.py](../src/pythalab_agent_cli/sandbox/local_runner.py)
