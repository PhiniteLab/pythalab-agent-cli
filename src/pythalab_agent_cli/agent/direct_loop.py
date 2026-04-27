"""Direct, pythalab-cortex-style code-generation loop for ``algorithm.py``.

The model is asked, in plain chat, to produce the complete contents of a single
file. Whatever comes back gets written straight to ``algorithm.py``. We do not
gate the model output behind AST safety filters, semantic checklists, ruff,
pyright, or pytest — only a syntax + import smoke check (mirroring
pythalab-cortex's validation surface).

If the smoke check fails we feed the error back as the next user turn and let
the model try again, accumulating chat history so attempt N sees attempts
1..N-1 plus their validator feedback.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from pythalab_agent_cli.agent.observer import AgentObserver, AgentProgressEvent, NullObserver
from pythalab_agent_cli.agent.result import AgentRunResult
from pythalab_agent_cli.config.schema import AppConfig
from pythalab_agent_cli.core.errors import ModelError
from pythalab_agent_cli.core.types import FailureType
from pythalab_agent_cli.llm.base import ChatMessage, ModelClient
from pythalab_agent_cli.llm.code_extractor import ExtractedCode, extract_python_code
from pythalab_agent_cli.validation.pipeline import ValidationPipeline
from pythalab_agent_cli.validation.report import ValidationReport, ValidationResult

MissingPackagePrompt = Callable[[set[str]], bool]
"""Hook invoked when the import-check reports missing modules.

The callable receives the set of missing top-level *import* names (e.g.
``{"matplotlib", "numpy"}``) and must return ``True`` to install them into the
active Python environment, or ``False`` to leave the failure intact.
"""

# Map top-level import names to PyPI distribution names where they differ.
_IMPORT_TO_PYPI: dict[str, str] = {
    "cv2": "opencv-python",
    "PIL": "pillow",
    "sklearn": "scikit-learn",
    "yaml": "pyyaml",
    "bs4": "beautifulsoup4",
    "skimage": "scikit-image",
}

_DIRECT_SYSTEM_PROMPT = (
    "You are a precise senior Python engineer. You write the complete contents of a "
    "single file named ``algorithm.py``.\n\n"
    "Code-quality rules (MANDATORY):\n"
    "  - Always wrap your answer in exactly ONE fenced ```python ... ``` block. No prose "
    "outside the block.\n"
    "  - Output the COMPLETE updated contents of algorithm.py, from the first line to the "
    'last. Do not write "... unchanged ..." or use ellipses.\n'
    "  - Include all required imports at the top of the file.\n"
    "  - Python 3.11+. Use modern builtin generics (``list[int]``, ``dict[str, object]``).\n"
    "  - Include type hints on public functions and concise docstrings.\n"
    "  - The code MUST be syntactically valid and importable as-is.\n"
    "  - Do not use placeholders such as ``...``, ``# TODO``, ``pass  # implement``, or "
    "``raise NotImplementedError``.\n\n"
    "Dependency policy:\n"
    "  - Always satisfy the user's request as written. If the user asks for ``matplotlib``, "
    "``numpy``, ``pandas``, ``scipy``, ``sklearn``, ``torch``, ``tensorflow``, etc., import "
    "and use them normally. Do NOT refuse, do NOT silently downgrade to a stdlib-only "
    "version, and do NOT replace plotting with CSV writes unless the user asked for that.\n"
    "  - When a third-party package is genuinely missing from the environment, the runtime "
    "will detect ``ModuleNotFoundError`` and offer to install it. Your job is to write the "
    "correct code; the runtime handles installation.\n"
    "  - Prefer the standard library only when no third-party dependency is required by "
    "the task. Pick well-known, pip-installable packages with stable import names.\n\n"
    "Iteration rules:\n"
    "  - When earlier assistant turns are present, treat them as your own prior drafts. "
    "Build on them: keep what works, fix what the validator complained about, and "
    "extend the file to satisfy the latest user instructions.\n"
    "  - Never delete previously-correct code unless the new request explicitly contradicts it.\n\n"
    "Execution model (IMPORTANT):\n"
    "  - After each generation the runtime executes ``algorithm.py`` as ``__main__`` and "
    "captures any uncaught exception. So your file MUST run end-to-end without crashing.\n"
    "  - Provide a top-level ``if __name__ == '__main__':`` block that exercises the "
    "primary entry point with realistic inputs (small but non-trivial: e.g. a 2-step "
    "simulation, a tiny example dataset). Do not leave it empty and do not call "
    "``sys.exit`` or ``input()``.\n"
    "  - Validate matrix/array shapes, units, and indices before using them. When you "
    "slice state vectors (``x[:n]``, ``x[n:]``), make sure the resulting shapes are what "
    "the consuming function expects (e.g. an inertia matrix ``M @ v`` requires ``v`` to "
    "have the matching column count).\n"
    "  - Guard divisions, square roots, ``log``, matrix inversions and similar against "
    "degenerate inputs. Prefer a small example that you have mentally executed.\n"
    "  - If a runtime error is reported, READ THE TRACEBACK: the failing line, the "
    "operator, and the operand shapes/values are the actual fix target. Do not just "
    "reshuffle code — fix the specific operation that crashed."
)


@dataclass(frozen=True)
class _AttemptOutcome:
    raw_response: str
    extracted: ExtractedCode | None
    code_written: bool
    snapshot_path: Path | None
    report: ValidationReport
    feedback_for_next_turn: str


class DirectAgentLoop:
    """Stable, serial, cumulative direct-to-algorithm.py generation loop."""

    def __init__(
        self,
        *,
        repo_root: Path,
        config: AppConfig,
        client: ModelClient,
        session_id: str | None = None,
        observer: AgentObserver | None = None,
        max_attempts: int | None = None,
        continue_until_success: bool | None = None,
        missing_package_prompt: MissingPackagePrompt | None = None,
    ) -> None:
        self.repo_root = repo_root.resolve()
        self.config = config
        self.client = client
        self.session_id = session_id or uuid4().hex
        self.observer: AgentObserver = observer or NullObserver()
        self.max_attempts_override = max_attempts
        self.continue_until_success = (
            config.agent.continue_until_success if continue_until_success is None else continue_until_success
        )
        self.pipeline = ValidationPipeline(config.validation)
        self.missing_package_prompt = missing_package_prompt
        self._task_counter = 0

    # -- Public entry point ------------------------------------------------

    def run(self, user_request: str) -> AgentRunResult:
        """Execute the direct generation loop for ``user_request`` and return a result."""
        target_file = self.repo_root / self.config.target_file
        model_name = self.config.models.default_model
        max_attempts = self._effective_max_attempts()
        task_id = self._next_task_id()

        self._emit("preflight", "running", "direct generation loop starting; serial single-GPU mode")
        baseline_text = target_file.read_text(encoding="utf-8") if target_file.exists() else ""
        messages: list[ChatMessage] = [
            {"role": "system", "content": _DIRECT_SYSTEM_PROMPT},
            {"role": "user", "content": self._initial_user_prompt(user_request, baseline_text)},
        ]
        attempt_limit = "∞" if max_attempts <= 0 else str(max_attempts)
        self._emit(
            "preflight",
            "done",
            f"target={self.config.target_file} model={model_name} max_attempts={attempt_limit}",
        )
        snapshot_paths: list[str] = []
        best_report: ValidationReport | None = None
        best_score = 0.0
        total_attempts = 0
        last_feedback = ""

        try:
            while self._budget_available(total_attempts, max_attempts):
                stage_label = "generate" if total_attempts == 0 else "regenerate"
                self._emit(
                    stage_label,
                    "running",
                    f"requesting attempt {total_attempts + 1} from {model_name}",
                    attempt_index=total_attempts,
                    total_attempts=total_attempts,
                    max_attempts=max_attempts,
                )
                outcome = self._one_attempt(
                    task_id=task_id,
                    attempt_index=total_attempts,
                    user_request=user_request,
                    target_file=target_file,
                    messages=messages,
                )
                if outcome.snapshot_path is not None:
                    snapshot_paths.append(str(outcome.snapshot_path.relative_to(self.repo_root)))
                best_report, best_score = self._track_best(best_report, best_score, outcome.report)
                total_attempts += 1

                if outcome.report.passed:
                    return self._success(
                        task_id=task_id,
                        report=outcome.report,
                        total_attempts=total_attempts,
                        max_attempts=max_attempts,
                        snapshot_paths=snapshot_paths,
                    )

                # Persist this round into chat history so the next turn sees the
                # model's last raw output and the validator's complaint.
                messages.append({"role": "assistant", "content": outcome.raw_response})
                messages.append({"role": "user", "content": outcome.feedback_for_next_turn})
                messages = self._truncate_history(messages, self.config.direct.max_history_chars)
                last_feedback = outcome.feedback_for_next_turn

            return self._budget_exhausted(
                task_id=task_id,
                report=best_report,
                snapshot_paths=snapshot_paths,
                total_attempts=total_attempts,
                max_attempts=max_attempts,
                last_feedback=last_feedback,
            )
        except ModelError as exc:
            return self._error_result(
                task_id=task_id,
                exc=exc,
                snapshot_paths=snapshot_paths,
                total_attempts=total_attempts,
                max_attempts=max_attempts,
            )

    # -- Single attempt ---------------------------------------------------

    def _one_attempt(
        self,
        *,
        task_id: int,
        attempt_index: int,
        user_request: str,
        target_file: Path,
        messages: list[ChatMessage],
    ) -> _AttemptOutcome:
        profile = self.config.models.profile(self.config.direct.profile_name)

        def _emit_thinking(chunk: str) -> None:
            self._emit("thinking", "stream", chunk, attempt_index=attempt_index)

        raw = self.client.chat_text(messages=messages, profile=profile, on_thinking=_emit_thinking)
        self._emit(
            "generate",
            "done",
            f"model returned {len(raw)} chars",
            attempt_index=attempt_index,
        )
        extracted = extract_python_code(raw)
        if extracted is None or not extracted.code.strip():
            self._emit(
                "extract",
                "fail",
                "model output had no usable ```python``` block; will retry with stronger format hint",
                attempt_index=attempt_index,
            )
            report = self._failure_report("extract", "no python code block in model response", FailureType.SEMANTIC)
            return _AttemptOutcome(
                raw_response=raw,
                extracted=None,
                code_written=False,
                snapshot_path=None,
                report=report,
                feedback_for_next_turn=(
                    "Your previous response did not contain a valid ```python ... ``` code "
                    "block. Output the COMPLETE updated algorithm.py inside exactly one such "
                    "fenced block. No prose, no diff, no patches."
                ),
            )

        # Materialize directly to algorithm.py — no path policy, no safety gate.
        target_file.write_text(extracted.code, encoding="utf-8")
        snapshot = self._save_snapshot(task_id, attempt_index, extracted.code)

        self._emit(
            "validate",
            "running",
            f"wrote algorithm.py ({len(extracted.code)} chars); running validators",
            attempt_index=attempt_index,
        )
        report = self.pipeline.run(self.repo_root, user_request=user_request)
        report = self._maybe_install_missing_packages(report, user_request, attempt_index)
        if report.passed:
            self._emit(
                "validate",
                "success",
                f"attempt {attempt_index + 1} passed",
                attempt_index=attempt_index,
            )
            return _AttemptOutcome(
                raw_response=raw,
                extracted=extracted,
                code_written=True,
                snapshot_path=snapshot,
                report=report,
                feedback_for_next_turn="",
            )

        self._emit(
            "validate",
            "fail",
            f"primary_failure={report.primary_failure.value}; feeding validator output back",
            attempt_index=attempt_index,
        )
        feedback = self._format_validator_feedback(report)
        return _AttemptOutcome(
            raw_response=raw,
            extracted=extracted,
            code_written=True,
            snapshot_path=snapshot,
            report=report,
            feedback_for_next_turn=feedback,
        )

    # -- Helpers ----------------------------------------------------------

    def _initial_user_prompt(self, user_request: str, current_file: str) -> str:
        if current_file.strip():
            return (
                f"Task: {user_request}\n\n"
                "Current contents of algorithm.py (treat as a starting point you may rewrite):\n"
                "```python\n"
                f"{current_file}\n"
                "```\n\n"
                "Respond with the COMPLETE updated algorithm.py inside one ```python ... ``` block."
            )
        return (
            f"Task: {user_request}\n\n"
            "algorithm.py does not exist yet. Create the COMPLETE file from scratch and return "
            "it inside one ```python ... ``` block."
        )

    def _maybe_install_missing_packages(
        self,
        report: ValidationReport,
        user_request: str,
        attempt_index: int,
    ) -> ValidationReport:
        """Optionally install missing third-party packages, then re-run validation.

        Returns the original report unchanged when no prompt is wired, when the
        primary failure is not an import error, when no missing modules can be
        parsed, when the user declines, or when the install fails.
        """
        if self.missing_package_prompt is None:
            return report
        if report.primary_failure is not FailureType.IMPORT:
            return report
        summary = report.compact_summary(max_lines=200)
        missing = _extract_missing_modules(summary)
        if not missing:
            return report
        try:
            approved = bool(self.missing_package_prompt(missing))
        except (KeyboardInterrupt, EOFError):
            approved = False
        if not approved:
            return report
        pip_names = sorted({_IMPORT_TO_PYPI.get(name, name) for name in missing})
        self._emit(
            "install",
            "running",
            f"installing {', '.join(pip_names)} into {sys.executable}",
            attempt_index=attempt_index,
        )
        installed = _pip_install(pip_names, cwd=self.repo_root)
        if not installed.ok:
            self._emit(
                "install",
                "fail",
                f"pip install failed (exit={installed.exit_code}): {installed.stderr_tail}",
                attempt_index=attempt_index,
            )
            return report
        self._emit(
            "install",
            "done",
            f"installed {', '.join(pip_names)}; re-running validators",
            attempt_index=attempt_index,
        )
        return self.pipeline.run(self.repo_root, user_request=user_request)

    def _format_validator_feedback(self, report: ValidationReport) -> str:
        max_lines = self.config.direct.error_summary_max_lines
        summary = report.compact_summary(max_lines=max_lines)
        directive = self._actionable_directive(report, summary)
        return (
            "Validators failed on your previous version of algorithm.py. "
            "Fix the issues listed below while keeping every other working part of the file. "
            "Output the COMPLETE updated algorithm.py inside one ```python ... ``` block.\n\n"
            f"{directive}"
            "VALIDATOR REPORT:\n"
            f"{summary}"
        )

    @staticmethod
    def _actionable_directive(report: ValidationReport, summary: str) -> str:
        """Return an extra instruction targeted at the dominant failure mode.

        The default validator summary is too generic for small models — they
        often rationalise and resubmit identical code. This injects a concrete
        "do this, not that" hint above the raw report.
        """
        if report.primary_failure is FailureType.IMPORT:
            missing = _extract_missing_modules(summary)
            if missing:
                joined = ", ".join(sorted(missing))
                return (
                    "REQUIRED FIX: The validator's import smoke check failed because the "
                    f"following package(s) are NOT installed: {joined}. The validator runs "
                    "in a minimal venv with ONLY the Python standard library. You MUST "
                    "remove every ``import`` and ``from`` statement that references those "
                    "packages and rewrite the affected logic using stdlib alternatives "
                    "(math, statistics, csv, json, random, ...). Re-emitting the same "
                    "imports will fail identically.\n\n"
                )
            return (
                "REQUIRED FIX: The import smoke check failed. Re-read every top-level "
                "import and remove any that refer to packages outside the Python standard "
                "library, then rewrite the affected logic with stdlib only.\n\n"
            )
        if report.primary_failure is FailureType.RUNTIME:
            tail = _extract_traceback_tail(summary)
            return (
                "REQUIRED FIX: The runtime smoke check ran ``algorithm.py`` as ``__main__`` "
                "and an uncaught exception was raised. This is NOT an environment problem — "
                "the file you produced crashes. Fix the SPECIFIC failing line shown in the "
                "traceback below: check the operator, the operand shapes/values/types, the "
                "indices and slicing. Trace what each variable contains at that point and "
                "correct the construction. Re-emitting the same buggy expression will fail "
                "identically.\n\n"
                f"TRACEBACK TAIL:\n{tail}\n\n"
            )
        return ""

    def _truncate_history(self, messages: list[ChatMessage], max_chars: int) -> list[ChatMessage]:
        if len(messages) <= 3:
            return messages
        total = sum(len(m["content"]) for m in messages)
        if total <= max_chars:
            return messages
        head = messages[:2]
        tail = list(messages[2:])
        while tail and sum(len(m["content"]) for m in head + tail) > max_chars and len(tail) > 2:
            tail.pop(0)
        return head + tail

    def _save_snapshot(self, task_id: int, attempt_index: int, code: str) -> Path | None:
        if not self.config.direct.save_attempt_snapshots:
            return None
        attempts_dir = self.repo_root / ".pythalab-agent" / "attempts"
        attempts_dir.mkdir(parents=True, exist_ok=True)
        path = attempts_dir / f"task-{task_id:06d}-attempt-{attempt_index:03d}.py"
        path.write_text(code, encoding="utf-8")
        return path

    def _track_best(
        self,
        best: ValidationReport | None,
        best_score: float,
        candidate: ValidationReport,
    ) -> tuple[ValidationReport, float]:
        if best is None or candidate.total_score >= best_score:
            return candidate, candidate.total_score
        return best, best_score

    def _effective_max_attempts(self) -> int:
        if self.continue_until_success:
            return 0
        if self.max_attempts_override is not None and self.max_attempts_override > 0:
            return self.max_attempts_override
        return self.config.direct.max_attempts

    def _budget_available(self, total_attempts: int, max_attempts: int) -> bool:
        return max_attempts <= 0 or total_attempts < max_attempts

    def _next_task_id(self) -> int:
        self._task_counter += 1
        salt = int(hashlib.sha256(str(self.repo_root).encode()).hexdigest()[:8], 16) % 1000
        return salt * 1000 + self._task_counter

    def _emit(
        self,
        stage: str,
        status: str,
        detail: str = "",
        *,
        attempt_index: int | None = None,
        total_attempts: int | None = None,
        max_attempts: int | None = None,
    ) -> None:
        self.observer(
            AgentProgressEvent(
                stage=stage,
                status=status,
                detail=detail,
                attempt_index=attempt_index,
                total_attempts=total_attempts,
                max_attempts=max_attempts,
            )
        )

    def _success(
        self,
        *,
        task_id: int,
        report: ValidationReport,
        total_attempts: int,
        max_attempts: int,
        snapshot_paths: list[str],
    ) -> AgentRunResult:
        self._emit(
            "complete",
            "success",
            f"algorithm.py validated after {total_attempts} attempt(s)",
            total_attempts=total_attempts,
            max_attempts=max_attempts,
        )
        return AgentRunResult(
            task_id=task_id,
            status="success",
            changed_files=[self.config.target_file],
            validation_report=report,
            review_summary=f"Direct generation succeeded in {total_attempts} attempt(s).",
            attempt_snapshots=snapshot_paths,
            total_attempts=total_attempts,
            max_attempts=max_attempts,
            repair_attempts=max(total_attempts - 1, 0),
        )

    def _budget_exhausted(
        self,
        *,
        task_id: int,
        report: ValidationReport | None,
        snapshot_paths: list[str],
        total_attempts: int,
        max_attempts: int,
        last_feedback: str,
    ) -> AgentRunResult:
        self._emit(
            "complete",
            "failed",
            f"stopped after {total_attempts} attempt(s)",
            total_attempts=total_attempts,
            max_attempts=max_attempts,
        )
        final_report = report or self._failure_report(
            "attempt_budget", "no validation report produced", FailureType.UNKNOWN
        )
        return AgentRunResult(
            task_id=task_id,
            status="attempt_budget_exhausted",
            changed_files=[],
            validation_report=final_report,
            review_summary=last_feedback or "Attempt budget exhausted before validation passed.",
            attempt_snapshots=snapshot_paths,
            total_attempts=total_attempts,
            max_attempts=max_attempts,
            repair_attempts=max(total_attempts - 1, 0),
        )

    def _error_result(
        self,
        *,
        task_id: int,
        exc: Exception,
        snapshot_paths: list[str],
        total_attempts: int,
        max_attempts: int,
    ) -> AgentRunResult:
        report = self._failure_report("client_error", str(exc), FailureType.UNKNOWN)
        self._emit("complete", "error", str(exc), total_attempts=total_attempts, max_attempts=max_attempts)
        return AgentRunResult(
            task_id=task_id,
            status="client_error",
            changed_files=[],
            validation_report=report,
            review_summary=str(exc),
            attempt_snapshots=snapshot_paths,
            total_attempts=total_attempts,
            max_attempts=max_attempts,
        )

    def _failure_report(self, name: str, message: str, failure_type: FailureType) -> ValidationReport:
        result = ValidationResult(
            name=name,
            command=[],
            exit_code=1,
            stdout_excerpt="",
            stderr_excerpt=message,
            passed=False,
            duration_sec=0.0,
            failure_type=failure_type,
        )
        return ValidationReport(
            results=[result],
            semantic_score=0.0,
            total_score=0.0,
            primary_failure=failure_type,
        )


def reset_attempts_dir(repo_root: Path) -> None:
    """Remove cached per-attempt code snapshots."""
    attempts_dir = repo_root / ".pythalab-agent" / "attempts"
    if attempts_dir.exists():
        shutil.rmtree(attempts_dir)


_MODULE_NOT_FOUND_RE = re.compile(r"ModuleNotFoundError: No module named ['\"]([^'\"]+)['\"]")


@dataclass(frozen=True)
class _PipResult:
    ok: bool
    exit_code: int
    stderr_tail: str


def _pip_install(packages: list[str], *, cwd: Path, timeout_sec: float = 600.0) -> _PipResult:
    """Install ``packages`` into the running interpreter via ``pip install``.

    Uses ``sys.executable -m pip install --disable-pip-version-check`` with
    ``shell=False`` so package names are never word-split. Output is captured
    and the last 600 chars of stderr are returned for diagnostics.
    """
    if not packages:
        return _PipResult(ok=True, exit_code=0, stderr_tail="")
    command = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", *packages]
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_sec,
        )
    except subprocess.TimeoutExpired:
        return _PipResult(ok=False, exit_code=124, stderr_tail=f"pip install timed out after {timeout_sec:.0f}s")
    stderr_tail = (completed.stderr or "").strip()[-600:]
    return _PipResult(ok=completed.returncode == 0, exit_code=completed.returncode, stderr_tail=stderr_tail)


def _extract_missing_modules(summary: str) -> set[str]:
    """Return the set of top-level package names reported as missing.

    Parses ``ModuleNotFoundError: No module named 'foo.bar'`` lines from the
    validator summary and keeps only the top-level package (``foo``).
    """
    missing: set[str] = set()
    for match in _MODULE_NOT_FOUND_RE.finditer(summary):
        top = match.group(1).split(".", 1)[0].strip()
        if top:
            missing.add(top)
    return missing


def _extract_traceback_tail(summary: str, max_lines: int = 30) -> str:
    """Return the last ``max_lines`` of a Python traceback block from the summary.

    Falls back to the trailing ``max_lines`` of the summary when no obvious
    traceback marker is found.
    """
    lines = summary.splitlines()
    start = 0
    for idx, line in enumerate(lines):
        if line.lstrip().startswith("Traceback (most recent call last)"):
            start = idx
            break
    tail = lines[start:] if start else lines
    if len(tail) > max_lines:
        tail = tail[-max_lines:]
    return "\n".join(tail).strip()


__all__ = ["DirectAgentLoop", "MissingPackagePrompt", "reset_attempts_dir"]
