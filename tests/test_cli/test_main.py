from typer.testing import CliRunner
from t212_cli.cli.main import app

runner = CliRunner()

def test_app() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "account" in result.stdout
