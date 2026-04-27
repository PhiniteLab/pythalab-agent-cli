"""Pydantic configuration schemas."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from pythalab_agent_cli.core.constants import (
    DEFAULT_MAX_REPAIRS,
    DEFAULT_MODEL,
    DEFAULT_NUM_CTX,
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_TARGET_FILE,
    FALLBACK_MODEL,
)


class ModelProfile(BaseModel):
    """Runtime options for one LLM role."""

    model: str = DEFAULT_MODEL
    think: bool | None = None
    temperature: float = Field(default=0.03, ge=0.0, le=2.0)
    top_p: float = Field(default=0.65, ge=0.0, le=1.0)
    top_k: int | None = Field(default=None, ge=1, le=200)
    repeat_penalty: float = Field(default=1.05, ge=0.0)
    num_ctx: int = Field(default=DEFAULT_NUM_CTX, ge=1024)
    num_predict: int = Field(default=1024, ge=-2)
    num_gpu: int | None = Field(
        default=None,
        ge=0,
        le=999,
        description=(
            "Number of model layers to keep on the GPU. None lets Ollama decide. "
            "On RTX 3060 6 GB the safe maximum for qwen3:4b at num_ctx=8192 is around 28-32 layers."
        ),
    )
    num_thread: int | None = Field(default=None, ge=1, le=64)
    seed: int | None = Field(
        default=None,
        description="Fixed sampler seed for reproducible generation; leave None to let Ollama pick.",
    )
    keep_alive: str | int | None = Field(default="30s")

    def to_options(self) -> dict[str, int | float]:
        """Return Ollama-compatible options."""
        options: dict[str, int | float] = {
            "temperature": self.temperature,
            "top_p": self.top_p,
            "repeat_penalty": self.repeat_penalty,
            "num_ctx": self.num_ctx,
            "num_predict": self.num_predict,
        }
        if self.top_k is not None:
            options["top_k"] = self.top_k
        if self.num_gpu is not None:
            options["num_gpu"] = self.num_gpu
        if self.num_thread is not None:
            options["num_thread"] = self.num_thread
        if self.seed is not None:
            options["seed"] = self.seed
        return options


class ModelsConfig(BaseModel):
    """Model backend configuration."""

    default_model: str = DEFAULT_MODEL
    fallback_model: str = FALLBACK_MODEL
    base_url: str = DEFAULT_OLLAMA_BASE_URL
    default_options: dict[str, int | float] = Field(
        default_factory=lambda: {"num_ctx": DEFAULT_NUM_CTX, "repeat_penalty": 1.05, "top_p": 0.70}
    )
    profiles: dict[str, ModelProfile] = Field(
        default_factory=lambda: {
            "planner": ModelProfile(think=False, temperature=0.05, top_p=0.65, num_predict=768),
            "patcher": ModelProfile(think=False, temperature=0.02, top_p=0.55, num_predict=1280),
            "code_unit": ModelProfile(think=False, temperature=0.02, top_p=0.55, num_predict=1280),
            "repairer": ModelProfile(think=False, temperature=0.01, top_p=0.50, num_predict=1024),
            "reviewer": ModelProfile(think=False, temperature=0.05, top_p=0.65, num_predict=768),
            "reflection": ModelProfile(think=False, temperature=0.05, top_p=0.65, num_predict=512),
            "json_repair": ModelProfile(think=False, temperature=0.0, top_p=0.40, num_ctx=4096, num_predict=768),
            # Mirrors pythalab-cortex chat options so Ollama makes the same
            # offload decision on a 6 GB GPU. With num_ctx=16384 the qwen3:4b
            # Q4 model (~2.6 GB) plus KV cache (~2.3 GB) sits near the 6 GB
            # VRAM limit, so Ollama partially offloads to CPU. That is what
            # caps GPU utilisation at ~50% on RTX 3060 (matching pythalab),
            # vs. 100% sustained when num_ctx=8192 fits fully on-GPU.
            # We deliberately do NOT send top_k / seed / num_gpu / num_thread
            # — leave them unset so Ollama picks defaults, exactly like
            # pythalab does. think=True is kept because the UI streams the
            # model's reasoning live; without it qwen3 emits no <think> chunks.
            "direct": ModelProfile(
                think=True,
                temperature=0.4,
                top_p=0.9,
                repeat_penalty=1.1,
                num_ctx=16384,
                num_predict=-1,
                keep_alive="30m",
            ),
        }
    )

    def profile(self, name: str) -> ModelProfile:
        """Return a named profile or a conservative fallback."""
        return self.profiles.get(name, ModelProfile(model=self.default_model))


class ValidationConfig(BaseModel):
    """Validation pipeline settings."""

    target_file: str = DEFAULT_TARGET_FILE
    max_repairs: int = Field(default=DEFAULT_MAX_REPAIRS, ge=0, le=10)
    semantic_threshold: float = Field(default=0.50, ge=0.0, le=1.0)
    run_ruff: bool = True
    run_pyright: bool = True
    run_pytest: bool = True
    run_semantic: bool = True
    run_hypothesis: bool = False
    pytest_timeout_sec: float = Field(
        default=180.0,
        ge=5.0,
        le=1800.0,
        description="Timeout for the staged/final pytest invocation; can be slow on first import.",
    )
    pyright_timeout_sec: float = Field(
        default=120.0,
        ge=5.0,
        le=900.0,
        description="Timeout for the staged/final Pyright invocation.",
    )
    ruff_timeout_sec: float = Field(
        default=60.0,
        ge=5.0,
        le=600.0,
        description="Timeout for each Ruff lint/format invocation.",
    )
    import_timeout_sec: float = Field(
        default=30.0,
        ge=5.0,
        le=300.0,
        description="Timeout for the import smoke check.",
    )
    runtime_timeout_sec: float = Field(
        default=60.0,
        ge=5.0,
        le=600.0,
        description="Timeout for the runtime smoke check (executes the target file as __main__).",
    )
    run_runtime_check: bool = Field(
        default=True,
        description=(
            "When true, the pipeline executes the target file as __main__ after the import "
            "smoke check passes, capturing stdout/stderr and feeding any uncaught exception "
            "back to the model on the next attempt."
        ),
    )
    pyright_strict: bool = Field(
        default=False,
        description=(
            "When true, the staging Pyright run uses strict mode. Default is the basic mode "
            "since small local models often trip on aggressive strict-only diagnostics."
        ),
    )


class SecurityConfig(BaseModel):
    """Filesystem and command policy configuration."""

    workspace_only: bool = True
    allow_test_generation: bool = False
    allow_multi_file_edit: bool = False
    allow_third_party_imports: bool = False
    allow_data_science_imports: bool = Field(
        default=False,
        description=(
            "When true, generated code may import numpy, pandas, scipy, sklearn, matplotlib, "
            "torch, and tensorflow. Security-critical roots (subprocess, socket, os, sys, shutil, "
            "urllib, requests, httpx) remain blocked regardless of this flag."
        ),
    )
    write_allowlist: list[str] = Field(default_factory=lambda: [DEFAULT_TARGET_FILE])
    explicit_test_write_allowlist: list[str] = Field(default_factory=lambda: ["tests/test_algorithm.py"])
    deny_write_patterns: list[str] = Field(
        default_factory=lambda: [
            ".env",
            ".git/**",
            ".ssh/**",
            "**/*token*",
            "**/*secret*",
            "pyproject.toml",
            "configs/security.yaml",
        ]
    )
    forbidden_code_patterns: list[str] = Field(
        default_factory=lambda: [
            "eval(",
            "exec(",
            "subprocess",
            "socket",
            "urllib",
            "requests",
            "httpx",
        ]
    )


class AgentConfig(BaseModel):
    """Loop-level runtime limits."""

    max_steps: int = Field(default=8, ge=1, le=50)
    max_repairs: int = Field(default=DEFAULT_MAX_REPAIRS, ge=0, le=10)
    max_total_attempts: int = Field(
        default=25,
        ge=1,
        le=500,
        description="Maximum staged generate/repair/final-validation attempts before stopping.",
    )
    continue_until_success: bool = Field(
        default=False,
        description="When true, keep generating new staged candidates until validation passes or the user interrupts.",
    )
    max_duplicate_drafts: int = Field(
        default=2,
        ge=1,
        le=20,
        description="Maximum identical staged code drafts tolerated before forcing a fresh candidate.",
    )
    max_same_failure_streak: int = Field(
        default=4,
        ge=1,
        le=50,
        description="Maximum repeated primary failure streak before abandoning the current candidate.",
    )
    min_score_improvement: float = Field(
        default=0.01,
        ge=0.0,
        le=1.0,
        description="Minimum validation-score improvement required to keep repairing a candidate.",
    )
    default_backend: str = "ollama"


class RepoConfig(BaseModel):
    """Repository context settings."""

    target_file: str = DEFAULT_TARGET_FILE
    max_file_window_lines: int = Field(default=120, ge=20, le=400)


class MemoryConfig(BaseModel):
    """Memory store settings."""

    path: str = ".pythalab-agent/memory.sqlite"
    top_k_reflections: int = Field(default=3, ge=0, le=10)
    top_k_tasks: int = Field(default=3, ge=0, le=10)


class DirectGenerationConfig(BaseModel):
    """Settings for the direct (template-free) generation loop.

    Tuned for stable serial code generation on a single low-VRAM GPU
    (RTX 3060 6 GB) with cumulative chat-history merging across attempts.
    """

    profile_name: str = Field(
        default="direct",
        description="Name of the ModelProfile to use for direct generation calls.",
    )
    max_attempts: int = Field(
        default=10,
        ge=1,
        le=200,
        description="Maximum direct-generation attempts before giving up on a task.",
    )
    max_history_chars: int = Field(
        default=24000,
        ge=2000,
        le=200000,
        description=(
            "Maximum total characters retained across all assistant/user turns; older "
            "intermediate turns are dropped first while preserving system prompt and "
            "the latest exchange."
        ),
    )
    request_timeout_sec: float = Field(
        default=600.0,
        ge=10.0,
        le=3600.0,
        description="Per-call HTTP timeout for direct chat generation.",
    )
    save_attempt_snapshots: bool = Field(
        default=True,
        description="When true, each attempt's generated code is saved under .pythalab-agent/attempts/.",
    )
    error_summary_max_lines: int = Field(
        default=80,
        ge=5,
        le=400,
        description="How many lines of validation feedback to feed back to the model per turn.",
    )


class AppConfig(BaseModel):
    """Top-level config object."""

    repo: RepoConfig = Field(default_factory=RepoConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    validation: ValidationConfig = Field(default_factory=ValidationConfig)
    models: ModelsConfig = Field(default_factory=ModelsConfig)
    direct: DirectGenerationConfig = Field(default_factory=DirectGenerationConfig)

    @property
    def target_file(self) -> str:
        """Return the configured target file."""
        return self.repo.target_file or self.validation.target_file

    def memory_path(self, repo_root: Path) -> Path:
        """Resolve the SQLite database path relative to ``repo_root``."""
        return (repo_root / self.memory.path).resolve()
