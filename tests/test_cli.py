from click.testing import CliRunner

from tootuft2count.cli import main


def test_existing_commands_and_gui_are_registered():
    result = CliRunner().invoke(main, ["--help"])
    assert result.exit_code == 0
    for command in ("combine", "segment", "measure", "visualize", "quantify", "gui"):
        assert command in result.output
