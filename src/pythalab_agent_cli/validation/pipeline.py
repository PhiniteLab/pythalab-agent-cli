"""Minimal validation pipeline: syntax + import smoke check only.

Mirrors pythalab-cortex's validation surface — we do NOT run ruff, pyright,
pytest, semantic checklists, or AST safety gates. The goal is to give the
model fast, stable feedback ("does it compile? does it import?") and let it
self-correct over multiple chat turns.
"""

from __future__ import annotations

from pathlib import Path

from pythalab_agent_cli.config.schema import ValidationConfig
from pythalab_agent_cli.core.types import FailureType
from pythalab_agent_cli.sandbox.local_runner import LocalRunner
from pythalab_agent_cli.validation.import_check import ImportCheck
from pythalab_agent_cli.validation.report import ValidationReport, ValidationResult
from pythalab_agent_cli.validation.runtime_check import RuntimeCheck
from pythalab_agent_cli.validation.syntax_check import SyntaxCheck


class ValidationPipeline:
    """Run only syntax + import smoke checks against ``algorithm.py``."""

    def __init__(
        self,
        config: ValidationConfig | None = None,
        runner: LocalRunner | None = None,
    ) -> None:
        self.config = config or ValidationConfig()
        self.runner = runner or LocalRunner()

    def run(self, repo_root: Path, *, user_request: str = "") -> ValidationReport:
        """Run syntax then import then runtime; stop on the first failure."""
        _ = user_request  # accepted for signature parity with prior pipeline
        results: list[ValidationResult] = []
        syntax = SyntaxCheck(self.config.target_file, self.runner).run(repo_root)
        results.append(syntax)
        if not syntax.passed:
            return self._report(results)
        import_result = ImportCheck(self.runner, timeout_sec=self.config.import_timeout_sec).run(repo_root)
        results.append(import_result)
        if not import_result.passed:
            return self._report(results)
        if self.config.run_runtime_check:
            runtime_result = RuntimeCheck(self.runner, timeout_sec=self.config.runtime_timeout_sec).run(repo_root)
            results.append(runtime_result)
        return self._report(results)

    def _report(self, results: list[ValidationResult]) -> ValidationReport:
        primary = FailureType.UNKNOWN
        for result in results:
            if not result.passed and not result.skipped:
                primary = result.failure_type
                break
        passed = primary == FailureType.UNKNOWN
        total = 1.0 if passed else 0.0
        return ValidationReport(
            results=results,
            semantic_score=1.0 if passed else 0.0,
            total_score=total,
            primary_failure=primary,
        )
