from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from pythalab_agent_cli.agent.result import AgentRunResult
from pythalab_agent_cli.app import commands
from pythalab_agent_cli.config.loader import load_config
from pythalab_agent_cli.validation.report import ValidationReport


def test_run_command_manages_ollama_service_once(tmp_path: Path, monkeypatch) -> None:
    config = load_config(tmp_path)
    lifecycle: list[tuple[str, bool, str]] = []

    @contextmanager
    def fake_managed_service(base_url: str, *, enabled: bool = True):
        lifecycle.append((base_url, enabled, "enter"))
        try:
            yield
        finally:
            lifecycle.append((base_url, enabled, "exit"))

    class _DummyLoop:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        def run(self, task: str) -> AgentRunResult:
            return AgentRunResult(
                task_id=1,
                status="ok",
                changed_files=[],
                validation_report=ValidationReport(),
                review_summary="",
                reward=0.0,
                repair_attempts=0,
                strategy_name="test",
            )

    monkeypatch.setattr(commands, "managed_ollama_service", fake_managed_service)
    monkeypatch.setattr(commands, "load_config", lambda repo_root: config)
    monkeypatch.setattr(commands, "get_client", lambda config, backend, scenario: object())
    monkeypatch.setattr(commands, "DirectAgentLoop", _DummyLoop)

    result = commands.run_command(tmp_path, "test task", backend="ollama")

    assert result.status == "ok"
    assert lifecycle == [
        (config.models.base_url, True, "enter"),
        (config.models.base_url, True, "exit"),
    ]


def test_run_command_skips_ollama_service_for_fake_backend(tmp_path: Path, monkeypatch) -> None:
    config = load_config(tmp_path)
    lifecycle: list[tuple[str, bool, str]] = []

    @contextmanager
    def fake_managed_service(base_url: str, *, enabled: bool = True):
        lifecycle.append((base_url, enabled, "enter"))
        try:
            yield
        finally:
            lifecycle.append((base_url, enabled, "exit"))

    class _DummyLoop:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        def run(self, task: str) -> AgentRunResult:
            return AgentRunResult(
                task_id=1,
                status="ok",
                changed_files=[],
                validation_report=ValidationReport(),
                review_summary="",
                reward=0.0,
                repair_attempts=0,
                strategy_name="test",
            )

    monkeypatch.setattr(commands, "managed_ollama_service", fake_managed_service)
    monkeypatch.setattr(commands, "load_config", lambda repo_root: config)
    monkeypatch.setattr(commands, "get_client", lambda config, backend, scenario: object())
    monkeypatch.setattr(commands, "DirectAgentLoop", _DummyLoop)

    commands.run_command(tmp_path, "test task", backend="fake")

    assert lifecycle == [
        (config.models.base_url, False, "enter"),
        (config.models.base_url, False, "exit"),
    ]
