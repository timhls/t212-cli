from t212_cli.cli.main import app
from typer.testing import CliRunner

runner = CliRunner()


def test_app() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "account" in result.stdout
    assert "orders" in result.stdout
    assert "history" in result.stdout
