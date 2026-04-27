"""Smoke tests for generated algorithm implementations."""

from collections.abc import Callable

import algorithm


def test_algorithm_exposes_a_public_component() -> None:
    public_names = [name for name in dir(algorithm) if not name.startswith("_")]
    has_generated_component = any(name.startswith("Generated") for name in public_names)
    assert "solve" in public_names or has_generated_component
    assert isinstance(getattr(algorithm, "main", None), Callable)
    assert isinstance(getattr(algorithm, "run_component", None), Callable)
    solve = getattr(algorithm, "solve", None)
    if solve is not None:
        assert isinstance(solve, Callable)


def test_algorithm_runtime_demo_returns_result_envelope() -> None:
    result = algorithm.run_component()
    assert set(result) == {"outputs", "metrics", "artifacts", "diagnostics"}
    assert result["outputs"] is not None
    assert isinstance(result["diagnostics"], dict)
