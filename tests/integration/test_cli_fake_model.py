from pathlib import Path

from typer.testing import CliRunner

from pythalab_agent_cli.app.cli import app
from pythalab_agent_cli.app.commands import validate_command


def test_cli_init_and_models_list(tmp_path: Path) -> None:
    runner = CliRunner()
    init_result = runner.invoke(app, ["init", str(tmp_path)])
    assert init_result.exit_code == 0
    assert (tmp_path / "algorithm.py").exists()
    models_result = runner.invoke(app, ["models", "list"])
    assert models_result.exit_code == 0
    assert "qwen3:4b" in models_result.stdout


def test_init_workspace_produces_clean_baseline(tmp_path: Path) -> None:
    """Bare ``pythalab-agent init`` should leave a syntactically clean,
    importable, lint-clean baseline. The placeholder intentionally exposes
    no ``solve`` symbol, so the semantic checklist is not yet satisfied —
    the LLM is responsible for producing it on a subsequent ``run``.
    """

    runner = CliRunner()
    init_result = runner.invoke(app, ["init", str(tmp_path)])
    assert init_result.exit_code == 0

    report = validate_command(tmp_path)

    syntax = next(r for r in report.results if r.name == "syntax")
    assert syntax.exit_code == 0, syntax.stderr or syntax.stdout
    import_check = next(r for r in report.results if r.name == "import")
    assert import_check.exit_code == 0, import_check.stderr or import_check.stdout
