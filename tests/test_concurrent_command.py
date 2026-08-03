import asyncio
import io
import pathlib
import re
import shlex
import sys
from typing import cast

import pytest
import typer
from usecli import theme

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


def make_command() -> ConcurrentCommand:
    return ConcurrentCommand(typer.Typer())


def test_parse_csv() -> None:
    command = make_command()
    assert command.parse_csv(None) == []
    assert command.parse_csv("") == []
    assert command.parse_csv("  a , b ,, c  ") == ["a", "b", "c"]


def test_resolve_color() -> None:
    command = make_command()
    assert command.resolve_color("") is None
    assert command.resolve_color("   ") is None
    assert command.resolve_color("blue") == theme.ANSI.BLUE
    assert command.resolve_color("green") == theme.ANSI.GREEN
    assert command.resolve_color("grey") == theme.ANSI.FOREGROUND_MUTED
    assert command.resolve_color("magenta") == theme.ANSI.ACCENT
    assert command.resolve_color("not-a-color") is None


def test_stream_output_handles_partial_lines() -> None:
    command = make_command()

    async def scenario() -> str:
        reader = asyncio.StreamReader()
        reader.feed_data(b"first line\n")
        reader.feed_data(b"partial")
        reader.feed_eof()
        buf = io.StringIO()
        await command.stream_output(reader, ">", buf)
        return buf.getvalue()

    output = asyncio.run(scenario())
    assert output == ">first line\n>partial\n"


def test_stream_output_empty() -> None:
    command = make_command()

    async def scenario() -> str:
        reader = asyncio.StreamReader()
        reader.feed_eof()
        buf = io.StringIO()
        await command.stream_output(reader, ">", buf)
        return buf.getvalue()

    assert asyncio.run(scenario()) == ""


def test_build_prefixes_no_prefix() -> None:
    command = make_command()
    assert command.build_prefixes(["a", "b", "c"], no_prefix=True) == ["", "", ""]


def test_build_prefixes_prefix_format_error_falls_back() -> None:
    command = make_command()
    prefixes = command.build_prefixes(
        ["a"],
        names=["n"],
        prefix_format="{missing_key}",
        no_color=True,
    )
    assert prefixes[0].startswith("[")
    assert prefixes[0].endswith(" ")


def test_build_prefixes_applies_colors() -> None:
    command = make_command()
    prefixes = command.build_prefixes(
        ["a", "b"],
        colors=[theme.ANSI.RED, theme.ANSI.GREEN],
    )
    assert theme.ANSI.RED in prefixes[0]
    assert theme.ANSI.GREEN in prefixes[1]
    assert theme.ANSI.RESET in prefixes[0]


def test_build_prefixes_default_without_names() -> None:
    command = make_command()
    prefixes = command.build_prefixes(["a", "b", "c"], no_color=True)
    assert prefixes[0] == "[0] "
    assert prefixes[1] == "[1] "
    assert prefixes[2] == "[2] "


def test_build_prefixes_names_longer_than_commands() -> None:
    command = make_command()
    prefixes = command.build_prefixes(["a"], names=["one", "two"], no_color=True)
    assert prefixes[0] == "[one] "


def test_run_all_failed_to_start_returns_127() -> None:
    command = make_command()
    exit_codes = asyncio.run(
        command.run_all(
            ["echo hi"],
            shell=["/nonexistent/binary/xyz", "-c"],
            kill_others=True,
        )
    )
    assert exit_codes == [127]


def test_run_all_strips_colors_when_disabled() -> None:
    command = make_command()
    command_line = python_command("import sys; sys.stdout.write('\\x1b[31mred')")
    exit_codes = asyncio.run(command.run_all([command_line], subprocess_color=False))
    assert exit_codes == [0]


def test_run_command_cancellation_terminates_process() -> None:
    command = make_command()
    spec = command.CommandSpec(0, python_command("import time; time.sleep(5)"), "[0]")
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    async def scenario() -> None:
        task = asyncio.create_task(command.run_command(spec, queue))
        await asyncio.sleep(0.3)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())


def test_run_all_cancellation_terminates_processes() -> None:
    command = make_command()

    async def scenario() -> None:
        task = asyncio.create_task(
            command.run_all([python_command("import time; time.sleep(5)")])
        )
        await asyncio.sleep(0.3)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())


def test_run_all_kill_others_on_failure() -> None:
    command = make_command()
    commands = [
        python_command("import time; time.sleep(5)"),
        python_command("import sys; sys.exit(3)"),
    ]

    async def scenario() -> list[int]:
        return await asyncio.wait_for(
            command.run_all(commands, kill_others=True), timeout=5.0
        )

    exit_codes = asyncio.run(scenario())
    assert 3 in exit_codes


def test_handle_with_shell(capsys: pytest.CaptureFixture[str]) -> None:
    command = make_command()
    command.handle(
        commands=[python_command("print('shelled')")],
        shell="bash -lc",
    )
    captured = capsys.readouterr()
    assert "shelled" in captured.out


def test_handle_with_colors(capsys: pytest.CaptureFixture[str]) -> None:
    command = make_command()
    command.handle(
        commands=[python_command("print('colored')")],
        names="only",
        colors="blue,not-a-color",
    )
    captured = capsys.readouterr()
    assert "colored" in captured.out


def test_handle_keyboard_interrupt_exits_130(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    command = make_command()

    async def boom(*args: object, **kwargs: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(command, "run_all", boom)
    with pytest.raises(SystemExit) as excinfo:
        command.handle(commands=["echo hi"])
    assert excinfo.value.code == 130


def test_terminate_process_already_exited() -> None:
    command = make_command()

    async def scenario() -> None:
        shell = command.default_shell()
        process = await asyncio.create_subprocess_exec(*shell, "true")
        await process.wait()
        await command.terminate_process(process)

    asyncio.run(scenario())


def test_terminate_process_sigint() -> None:
    command = make_command()

    async def scenario() -> None:
        shell = command.default_shell()
        process = await asyncio.create_subprocess_exec(*shell, "sleep 5")
        await command.terminate_process(process)

    asyncio.run(scenario())


def test_terminate_process_stubborn_reaches_sigkill() -> None:
    command = make_command()

    async def scenario() -> None:
        shell = command.default_shell()
        script = "trap '' INT TERM; while true; do sleep 1; done"
        process = await asyncio.create_subprocess_exec(*shell, script)
        await command.terminate_process(process, timeout_seconds=0.2)

    asyncio.run(scenario())


class _StubProcess:
    def __init__(self) -> None:
        self.pid = 999999
        self.returncode = None

    async def wait(self) -> None:
        await asyncio.sleep(3600)

    def terminate(self) -> None:
        pass

    def kill(self) -> None:
        self.returncode = -9


def stub_process() -> asyncio.subprocess.Process:
    return cast(asyncio.subprocess.Process, _StubProcess())


def test_terminate_process_process_lookup_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_lookup(*args: object) -> None:
        raise ProcessLookupError

    monkeypatch.setattr(
        "userun.cli.commands.concurrent_command.os.killpg", raise_lookup
    )
    process = stub_process()
    asyncio.run(make_command().terminate_process(process))


def test_terminate_process_oserror_and_timeouts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_oserror(*args: object) -> None:
        raise OSError

    monkeypatch.setattr(
        "userun.cli.commands.concurrent_command.os.killpg", raise_oserror
    )
    process = stub_process()
    asyncio.run(make_command().terminate_process(process, timeout_seconds=0.05))


def test_terminate_process_sigkill_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "userun.cli.commands.concurrent_command.os.killpg",
        lambda *args: None,
    )
    process = stub_process()
    asyncio.run(make_command().terminate_process(process, timeout_seconds=0.05))


def test_terminate_process_windows_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("userun.cli.commands.concurrent_command.os.name", "nt")
    process = stub_process()
    asyncio.run(make_command().terminate_process(process, timeout_seconds=0.05))
    assert process.returncode == -9


def test_terminate_process_lookup_error_on_sigterm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"n": 0}

    def killpg(*args: object) -> None:
        calls["n"] += 1
        if calls["n"] >= 2:
            raise ProcessLookupError

    monkeypatch.setattr("userun.cli.commands.concurrent_command.os.killpg", killpg)
    process = stub_process()
    asyncio.run(make_command().terminate_process(process, timeout_seconds=0.05))


def test_terminate_process_lookup_error_on_sigkill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"n": 0}

    def killpg(*args: object) -> None:
        calls["n"] += 1
        if calls["n"] >= 3:
            raise ProcessLookupError

    monkeypatch.setattr("userun.cli.commands.concurrent_command.os.killpg", killpg)
    process = stub_process()
    asyncio.run(make_command().terminate_process(process, timeout_seconds=0.05))


def test_run_command_cancel_with_live_reader(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    command = make_command()

    async def noop(_process: object) -> None:
        return None

    monkeypatch.setattr(command, "terminate_process", noop)
    spec = command.CommandSpec(0, python_command("import time; time.sleep(0.5)"), "[0]")
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    async def scenario() -> None:
        task = asyncio.create_task(command.run_command(spec, queue))
        await asyncio.sleep(0.1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())


def test_default_shell_falls_back_to_bin_sh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "userun.cli.commands.concurrent_command.shutil.which",
        lambda name: None,
    )
    assert ConcurrentCommand.default_shell() == ["/bin/sh", "-c"]


def test_parse_shell_empty() -> None:
    with pytest.raises(SystemExit) as excinfo:
        ConcurrentCommand.parse_shell("   ")
    assert excinfo.value.code == 1


def test_parse_shell_empty_after_split() -> None:
    with pytest.raises(SystemExit) as excinfo:
        ConcurrentCommand.parse_shell("'' ''")
    assert excinfo.value.code == 1


def test_parse_shell_split_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "userun.cli.commands.concurrent_command.shlex.split",
        lambda value: [],
    )
    with pytest.raises(SystemExit) as excinfo:
        ConcurrentCommand.parse_shell("some shell")
    assert excinfo.value.code == 1


def test_parse_shell_absolute_not_executable() -> None:
    with pytest.raises(SystemExit) as excinfo:
        ConcurrentCommand.parse_shell("/nonexistent/path/sh -c")
    assert excinfo.value.code == 1


def test_parse_shell_not_on_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "userun.cli.commands.concurrent_command.shutil.which",
        lambda name: None,
    )
    with pytest.raises(SystemExit) as excinfo:
        ConcurrentCommand.parse_shell("nosuchshell -lc")
    assert excinfo.value.code == 1


def test_parse_shell_resolves_on_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "userun.cli.commands.concurrent_command.shutil.which",
        lambda name: "/bin/bash" if name == "bash" else None,
    )
    resolved = ConcurrentCommand.parse_shell("bash -lc")
    assert resolved == ["/bin/bash", "-lc"]
