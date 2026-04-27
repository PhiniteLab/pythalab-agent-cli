# The agent loop

The single entry point for code generation in 0.1.0 is `DirectAgentLoop` in [src/pythalab_agent_cli/agent/direct_loop.py](../src/pythalab_agent_cli/agent/direct_loop.py). It is a flat chat-history loop with no sub-stages, no JSON staging, and no planner/patcher/reviewer roles.

## Inputs

`DirectAgentLoop.__init__` takes:

- `client: LLMClient` — usually `OllamaClient`, sometimes `FakeModelClient`.
- `pipeline: ValidationPipeline` — wraps the three validators.
- `workspace: WorkspacePaths` — resolved root, `target_file`, `state_dir`, …
- `config: AppConfig` — the merged Pydantic config tree.
- `observer: AgentObserver | None` — Rich progress reporter.
- `memory_store: SQLiteStore | None` — read-only in 0.1.0.
- `missing_package_prompt: MissingPackagePrompt | None` — callback that decides whether to pip-install on `ModuleNotFoundError`.

## Run loop

`DirectAgentLoop.run(task: str, *, max_attempts: int | None, until_success: bool) -> AgentRunResult`:

1. **Preflight.**
   - Resolve the chat profile (`config.direct.profile_name`, default `"direct"`) from `config.models.profiles`.
   - Build the initial chat history:
     - `system` = `_DIRECT_SYSTEM_PROMPT` (asks for one fenced ```` ```python ```` block, no prose, no `eval`/`exec`/network).
     - `user` = the task plus the current file contents of `target_file` (truncated if huge).
   - Emit `preflight` milestone.

2. **Attempt loop.** While the attempt counter is below the budget (or forever if `until_success`):

   a. **Generate.**
      - Emit `generate` milestone.
      - Call `client.chat_text(messages, options=profile_options, stream_callback=observer.thinking)`.
      - If `think=True` is set on the profile, NDJSON streaming is used and `<think>…</think>` chunks are forwarded to the observer live.

   b. **Extract.**
      - `extract_python_code(text)` (from [llm/code_extractor.py](../src/pythalab_agent_cli/llm/code_extractor.py)) finds the first fenced ```` ```python ```` block, AST-parses it for safety, and returns the source.
      - If no block is found, the loop appends a short reminder ("respond with one fenced python block, no prose") and continues.

   c. **Write.**
      - The extracted source is written to `workspace.target_file` (default `algorithm.py`).
      - A snapshot is written to `.pythalab-agent/attempts/task-{id:06d}-attempt-{idx:03d}.py` if `direct.save_attempt_snapshots` is true.

   d. **Validate.**
      - Emit `validate` milestone.
      - `pipeline.run(workspace.target_file)` runs syntax → import → runtime, stopping on the first failure.

   e. **Decide.**
      - **Pass:** emit `complete` milestone, return `AgentRunResult(status=COMPLETE, …)`.
      - **Fail with `IMPORT` and `ModuleNotFoundError: 'X'`:** call `missing_package_prompt(X)`. If approved, run `LocalRunner.run(["python", "-m", "pip", "install", X])`, then re-validate without consuming an attempt.
      - **Other failures:** append the assistant draft and a compact validator report to the chat history, plus an "actionable directive" tailored to the failure type (e.g. "the import test imports the module by file path; do not put expensive work at module top-level"). Emit `regenerate` milestone, increment the attempt counter, loop.

3. **Budget exhausted.** Return `AgentRunResult(status=BUDGET_EXHAUSTED, …)`.

4. **Ctrl+C in `--until-success`.** A `KeyboardInterrupt` is caught at the CLI layer and reported as `INTERRUPTED`.

## History truncation

`config.direct.max_history_chars` (default `24000`) caps the total number of characters in the chat history. When exceeded, the oldest non-system messages are dropped first. The system message and the most recent user/assistant pair are always preserved.

`config.direct.error_summary_max_lines` (default `80`) caps how many lines of validator output are appended in the feedback turn.

## Why this shape

- **No stages.** A small model like `qwen3:4b` works best when it produces one self-contained file at a time; staging tends to compound errors.
- **No tools.** The model never gets file-write or shell tools. Every side effect is the runtime's responsibility.
- **Chat history as memory.** The loop's "memory" is the chat itself. The persistent SQLite store is read-only in 0.1.0; integrating writes is on the roadmap.

## Related files

- [src/pythalab_agent_cli/agent/direct_loop.py](../src/pythalab_agent_cli/agent/direct_loop.py) — the loop.
- [src/pythalab_agent_cli/agent/observer.py](../src/pythalab_agent_cli/agent/observer.py) — milestone protocol.
- [src/pythalab_agent_cli/agent/result.py](../src/pythalab_agent_cli/agent/result.py) — return type.
- [src/pythalab_agent_cli/llm/code_extractor.py](../src/pythalab_agent_cli/llm/code_extractor.py) — fenced-block parser.
- [src/pythalab_agent_cli/ui/progress.py](../src/pythalab_agent_cli/ui/progress.py) — Rich observer.
