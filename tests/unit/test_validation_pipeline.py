"""Tests for the simplified syntax+import validation pipeline."""

from __future__ import annotations

from pathlib import Path

from pythalab_agent_cli.sandbox.local_runner import LocalRunner
from pythalab_agent_cli.validation.pipeline import ValidationPipeline


def test_pipeline_catches_syntax_failure(tmp_path: Path) -> None:
    (tmp_path / "algorithm.py").write_text("def solve(:\n")
    report = ValidationPipeline().run(tmp_path)
    assert report.primary_failure.value == "SYNTAX"
    assert not report.passed


def test_pipeline_passes_basic_module(tmp_path: Path) -> None:
    source = "def solve(data: list[int]) -> list[int]:\n    return list(data)\n"
    (tmp_path / "algorithm.py").write_text(source)
    report = ValidationPipeline().run(tmp_path)
    assert report.by_name("syntax") is not None
    assert report.by_name("import") is not None
    assert report.passed


def test_pipeline_allows_torch_import_signature(tmp_path: Path) -> None:
    """The model is free to import torch / numpy / anything: no forbidden-import gate."""
    source = (
        "from __future__ import annotations\n\n"
        "def solve(data: list[float]) -> list[float]:\n"
        '    """Echo data; signature is allowed to look like a torch tensor pipeline."""\n'
        "    return [float(x) for x in data]\n"
    )
    (tmp_path / "algorithm.py").write_text(source)
    report = ValidationPipeline().run(tmp_path)
    assert report.passed


def test_local_runner_uses_isolated_stable_subprocess_commands() -> None:
    runner = LocalRunner()
    import_command = runner._execution_command(["python", "-I", "-c", "import algorithm"])
    pytest_command = runner._execution_command(["pytest", "-q"])

    assert "-S" in import_command
    assert "-B" in import_command
    assert "-S" in pytest_command
    assert "-B" in pytest_command
    assert "-I" not in import_command
    assert "-I" not in pytest_command
