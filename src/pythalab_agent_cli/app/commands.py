"""Programmatic command helpers used by the Typer CLI."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from pythalab_agent_cli.agent.direct_loop import DirectAgentLoop, MissingPackagePrompt
from pythalab_agent_cli.agent.observer import AgentObserver
from pythalab_agent_cli.agent.result import AgentRunResult
from pythalab_agent_cli.config.loader import load_config
from pythalab_agent_cli.config.schema import AppConfig
from pythalab_agent_cli.core.constants import DEFAULT_MODEL, FALLBACK_MODEL
from pythalab_agent_cli.llm.base import ModelClient
from pythalab_agent_cli.llm.fake_client import FakeModelClient
from pythalab_agent_cli.llm.ollama_client import OllamaClient
from pythalab_agent_cli.llm.ollama_service import managed_ollama_service
from pythalab_agent_cli.repo.workspace import initialize_workspace
from pythalab_agent_cli.validation.pipeline import ValidationPipeline
from pythalab_agent_cli.validation.report import ValidationReport


@dataclass(frozen=True)
class DoctorReport:
    """Environment doctor report."""

    python_ok: bool
    uv_ok: bool
    git_ok: bool
    ruff_ok: bool
    pyright_ok: bool
    pytest_ok: bool
    ollama_ok: bool
    default_model_available: bool
    fallback_model_available: bool
    message: str


def get_client(config: AppConfig, backend: str = "ollama", scenario: str = "default") -> ModelClient:
    """Create a model client from a backend name."""
    if backend == "fake":
        return FakeModelClient(scenario=scenario)
    if backend == "ollama":
        return OllamaClient(
            config.models.base_url,
            timeout_sec=config.direct.request_timeout_sec,
            models_config=config.models,
        )
    raise ValueError(f"Unsupported backend: {backend}")


def init_command(repo_root: Path, *, force: bool = False) -> None:
    """Initialize workspace."""
    initialize_workspace(repo_root, force=force)


def run_command(
    repo_root: Path,
    task: str,
    *,
    backend: str = "ollama",
    scenario: str = "default",
    max_attempts: int | None = None,
    until_success: bool | None = None,
    observer: AgentObserver | None = None,
    manage_service: bool = True,
    missing_package_prompt: MissingPackagePrompt | None = None,
) -> AgentRunResult:
    """Run one direct-generation task.

    Each attempt sends the cumulative chat history (system + task + prior
    drafts + validator feedback) to the model, writes the returned fenced
    ```python ... ``` block straight to ``algorithm.py``, and runs a syntax
    + import smoke check. On failure the validator output is appended as the
    next user turn and the model retries.
    """
    config = load_config(repo_root)
    with managed_ollama_service(config.models.base_url, enabled=manage_service and backend == "ollama"):
        client = get_client(config, backend=backend, scenario=scenario)
        return DirectAgentLoop(
            repo_root=repo_root,
            config=config,
            client=client,
            observer=observer,
            max_attempts=max_attempts,
            continue_until_success=until_success,
            missing_package_prompt=missing_package_prompt,
        ).run(task)


def validate_command(repo_root: Path, *, user_request: str = "") -> ValidationReport:
    """Run validation pipeline."""
    config = load_config(repo_root)
    return ValidationPipeline(config.validation).run(repo_root, user_request=user_request)


def doctor_command(repo_root: Path, *, backend: str = "ollama") -> DoctorReport:
    """Check runtime dependencies and model availability."""
    config = load_config(repo_root)
    python_ok = shutil.which("python") is not None
    uv_ok = shutil.which("uv") is not None
    git_ok = shutil.which("git") is not None
    ruff_ok = shutil.which("ruff") is not None
    pyright_ok = shutil.which("pyright") is not None
    pytest_ok = shutil.which("pytest") is not None
    ollama_ok = False
    default_available = False
    fallback_available = False
    message = ""
    if backend == "fake":
        ollama_ok = True
        default_available = True
        fallback_available = True
        message = "fake backend selected"
    else:
        try:
            with managed_ollama_service(config.models.base_url, enabled=True):
                models = OllamaClient(config.models.base_url).available_models()
                ollama_ok = True
                default_available = DEFAULT_MODEL in models or config.models.default_model in models
                fallback_available = FALLBACK_MODEL in models or config.models.fallback_model in models
                if not default_available:
                    message = f"Missing model. Run: ollama pull {DEFAULT_MODEL}"
        except Exception as exc:
            message = f"Ollama unavailable: {exc}. Run `ollama serve` and `ollama pull {DEFAULT_MODEL}`."
    return DoctorReport(
        python_ok=python_ok,
        uv_ok=uv_ok,
        git_ok=git_ok,
        ruff_ok=ruff_ok,
        pyright_ok=pyright_ok,
        pytest_ok=pytest_ok,
        ollama_ok=ollama_ok,
        default_model_available=default_available,
        fallback_model_available=fallback_available,
        message=message,
    )
