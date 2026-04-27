# Security model

`pythalab-agent-cli` runs untrusted model output as Python on the host, by design — that's how the runtime check works. This page documents what the runtime actually enforces, what it does not, and how to operate it safely.

## Threat model

- **Trusted:** the user, the local Python interpreter, the local Ollama daemon, files written by the user.
- **Semi-trusted:** the workspace root and everything under it. The agent reads and writes here.
- **Untrusted:** the model's output (any text returned by Ollama or the fake backend). Treated as data until validated.

The agent is **not** designed to defend against a malicious local Ollama daemon. If a different daemon is bound to `localhost:11434`, change `models.base_url`.

## What the runtime enforces

### 1. Subprocess command allow-list

[sandbox/command_policy.py](../src/pythalab_agent_cli/sandbox/command_policy.py) defines:

- An **allow-list** of command prefixes that may be executed by `LocalRunner`:
  - `("python", "-m", "py_compile")`
  - `("python", "-I", "-c")`
  - `("ruff", "check")`
  - `("ruff", "format", "--check")`
  - `("pyright",)`
  - `("pytest", "-q")`
  - `("git", "diff", "--")`
  - `("git", "status", "--short")`
- A **forbidden-token** set: `{"rm", "curl", "wget", "ssh", "scp", "sudo", "chmod", "chown", "pip", "uv"}`. Any argument whose token form matches is rejected, even inside an allow-listed command.

Anything else raises `SandboxPolicyError` before `subprocess.run` is called. There is no `shell=True` path. There is no string interpolation.

The `--auto-install` flow goes through `LocalRunner.run(["python", "-m", "pip", "install", <name>])`, which is allowed because `pip` only appears as a sub-command argument here; the policy specifically permits `python -m pip install` for this single use case (see [agent/direct_loop.py](../src/pythalab_agent_cli/agent/direct_loop.py)).

### 2. Subprocess execution hardening

`LocalRunner` (in [sandbox/local_runner.py](../src/pythalab_agent_cli/sandbox/local_runner.py)):

- `shell=False`, argument list only.
- Reset environment: `PATH`, `HOME`, plus `PYTHONDONTWRITEBYTECODE=1` and a project-aware `PYTHONPATH`.
- `stdin=subprocess.DEVNULL`.
- Output streamed into `tempfile.NamedTemporaryFile`; truncated to a bounded size.
- Wall-clock timeout from the relevant config key (`validation.import_timeout_sec`, `validation.runtime_timeout_sec`, …).

### 3. Workspace-scoped state

All agent state lives under `<workspace>/.pythalab-agent/` (logs, attempt snapshots, SQLite memory). The runtime does not touch `~/.config`, system Python, or anything outside the workspace. Optional `pip install` is the one exception and it targets the active interpreter.

### 4. Local-only network

The only outbound connection is to `models.base_url` (default `http://localhost:11434`). The fake backend makes no network calls. The model itself cannot make network calls — it only returns text.

## What the runtime does **not** enforce in 0.1.0

- **Generated-code content scanning.** The system prompt asks the model to avoid `eval`, `exec`, `subprocess`, `socket`, file I/O outside the target file, and network access. That is a soft contract, not a sandbox. If the model emits `os.system("rm -rf …")` and writes that to `algorithm.py`, the runtime check will execute it.
- **`security.write_allowlist` / `security.deny_write_patterns` / `security.forbidden_code_patterns`.** These keys are accepted by the config schema but are not consulted at runtime in 0.1.0.
- **Resource limits.** No `RLIMIT_*`, no cgroups, no tmpfs. Use the OS for that.
- **Container or VM isolation.** Out of scope for 0.1.0.

## Operating safely

The single most important rule: **run the agent in a workspace you can afford to lose, in an environment you can afford to expose.**

Concrete recommendations:

1. **Use a throwaway workspace directory.** Don't run `pythalab-agent run` in your home directory.
2. **Use a virtual environment.** Optional pip-install targets the active interpreter. A fresh venv keeps surprises contained.
3. **Use an unprivileged user or a container.** A `docker run --rm -it -v $PWD:/work -w /work python:3.11-slim …` shell is a fine isolation layer; install the agent inside.
4. **Review `.pythalab-agent/attempts/` after a run.** Every draft the model produced is on disk; you can read all of them.
5. **Disable the runtime check** if you only want syntax + import smoke testing on untrusted output: set `validation.run_runtime_check: false` in `configs/validation.yaml`.
6. **Disable `--auto-install` in CI.** Use `--no-install` so an unexpected `import` cannot trigger network installs.

## Reporting

If you find a security-relevant issue, please open a private security advisory on the GitHub repository.
