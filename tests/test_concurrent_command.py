import asyncio
import pathlib
import re
import shlex
import sys

import pytest
import typer

from userun.cli.commands.concurrent_command import ConcurrentCommand


def strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def python_command(code: str) -> str:
    executable = shlex.quote(sys.executable)
    return f"{executable} -c {shlex.quote(code)}"


def test_run_all_outputs_prefixed_lines_and_exit_codes(
    capsys: pytest.CaptureFixture[str],
) -> None:
    command = ConcurrentCommand(typer.Typer())
    commands = [
        python_command("print('alpha')"),
        python_command("import sys; print('beta', file=sys.stderr)"),
    ]

    exit_codes = asyncio.run(command.run_all(commands))

    captured = capsys.readouterr()
    output = strip_ansi(captured.out)

    assert exit_codes == [0, 0]
    assert "[0]" in output
    assert "[1]" in output
    assert "started:" in output
    assert "exited with code 0" in output
    assert "alpha" in output
    assert "beta" in output


def test_handle_raises_on_failure() -> None:
    command = ConcurrentCommand(typer.Typer())
    commands = [
        python_command("print('ok')"),
        python_command("import sys; sys.exit(2)"),
    ]

    with pytest.raises(SystemExit) as excinfo:
        command.handle(commands=commands)

    assert excinfo.value.code == 1


def test_build_prefixes_with_names_and_no_color() -> None:
    command = ConcurrentCommand(typer.Typer())
    prefixes = command.build_prefixes(
        ["alpha", "beta"],
        names=["nuxt", "db"],
        prefix_format="<{name}:{index}>",
        no_color=True,
    )

    assert prefixes[0].startswith("<nuxt:0>")
    assert prefixes[1].startswith("<db:1>")
    assert "\x1b" not in prefixes[0]


def test_run_all_disables_subprocess_colors(
    capsys: pytest.CaptureFixture[str],
) -> None:
    command = ConcurrentCommand(typer.Typer())
    command_line = python_command("print('\\x1b[31mred\\x1b[0m')")

    exit_codes = asyncio.run(
        command.run_all(
            [command_line],
            no_color=True,
            subprocess_color=False,
        )
    )

    captured = capsys.readouterr()
    assert exit_codes == [0]
    assert "\x1b" not in captured.out


def test_run_all_sets_subprocess_color_env_by_default(
    capsys: pytest.CaptureFixture[str],
) -> None:
    command = ConcurrentCommand(typer.Typer())
    command_line = python_command("import os; print(os.getenv('FORCE_COLOR', ''))")

    exit_codes = asyncio.run(
        command.run_all(
            [command_line],
            no_color=True,
        )
    )

    captured = capsys.readouterr()
    assert exit_codes == [0]
    assert "1" in captured.out


def test_run_all_defaults_to_bash_when_available(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
) -> None:
    fake_bash = tmp_path / "bash"
    fake_bash.write_text("#!/bin/sh\necho bash\n", encoding="utf-8")
    fake_bash.chmod(0o755)
    monkeypatch.setattr(
        "userun.cli.commands.concurrent_command.shutil.which",
        lambda name: str(fake_bash) if name == "bash" else None,
    )
    command = ConcurrentCommand(typer.Typer())
    exit_codes = asyncio.run(command.run_all(["echo ${0#-}"], no_color=True))

    captured = capsys.readouterr()
    output = strip_ansi(captured.out)

    assert exit_codes == [0]
    assert re.search(r"\bbash\b", output)


def test_run_all_kill_others_completes_when_all_succeed() -> None:
    command = ConcurrentCommand(typer.Typer())
    commands = [
        python_command("print('ok-1')"),
        python_command("print('ok-2')"),
    ]

    exit_codes = asyncio.run(
        asyncio.wait_for(command.run_all(commands, kill_others=True), timeout=2.0)
    )

    assert exit_codes == [0, 0]


def test_parse_shell_accepts_shell_with_args(
    tmp_path: pathlib.Path,
) -> None:
    fake_bash = tmp_path / "bash"
    fake_bash.write_text("#!/bin/sh\necho bash\n", encoding="utf-8")
    fake_bash.chmod(0o755)

    resolved = ConcurrentCommand.parse_shell(f"{fake_bash} -lc")

    assert resolved == [str(fake_bash), "-lc"]
