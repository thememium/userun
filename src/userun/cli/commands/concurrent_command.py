"""ConcurrentCommand - CLI command."""

from __future__ import annotations

import asyncio
import os
import re
import shlex
import shutil
import signal
from dataclasses import dataclass
from typing import TextIO

from usecli import Argument, BaseCommand, Option, console, theme


class ConcurrentCommand(BaseCommand):
    def signature(self) -> str:
        return "concurrent"

    def description(self) -> str:
        return "Run multiple commands concurrently"

    def aliases(self) -> list[str]:
        return ["conc"]

    @dataclass(frozen=True)
    class CommandSpec:
        index: int
        command: str
        prefix: str

    @staticmethod
    def parse_csv(value: str | None) -> list[str]:
        if value is None or not isinstance(value, str):
            return []
        items = [item.strip() for item in value.split(",")]
        return [item for item in items if item]

    @staticmethod
    def resolve_color(name: str) -> str | None:
        normalized = name.strip().lower()
        if not normalized:
            return None
        palette = {
            "primary": theme.ANSI.PRIMARY,
            "secondary": theme.ANSI.SECONDARY,
            "accent": theme.ANSI.ACCENT,
            "blue": theme.ANSI.BLUE,
            "green": theme.ANSI.GREEN,
            "yellow": theme.ANSI.YELLOW,
            "red": theme.ANSI.RED,
            "foreground": theme.ANSI.FOREGROUND,
            "foreground-muted": theme.ANSI.FOREGROUND_MUTED,
            "foreground_muted": theme.ANSI.FOREGROUND_MUTED,
            "gray": theme.ANSI.FOREGROUND_MUTED,
            "grey": theme.ANSI.FOREGROUND_MUTED,
            "white": theme.ANSI.FOREGROUND,
            "cyan": theme.ANSI.PRIMARY,
            "magenta": theme.ANSI.ACCENT,
            "purple": theme.ANSI.ACCENT,
        }
        return palette.get(normalized)

    async def stream_output(
        self, stream: asyncio.StreamReader, prefix: str, output: TextIO
    ) -> None:
        while True:
            line = await stream.readline()
            if not line:
                break
            text = line.decode(errors="replace")
            if not text.endswith("\n"):
                text = f"{text}\n"
            output.write(f"{prefix}{text}")
            output.flush()

    @staticmethod
    def strip_ansi(text: str) -> str:
        return re.sub(r"\x1b\[[0-9;]*m", "", text)

    def build_prefixes(
        self,
        commands: list[str],
        *,
        names: list[str] | None = None,
        colors: list[str] | None = None,
        prefix_format: str | None = None,
        no_prefix: bool = False,
        no_color: bool = False,
    ) -> list[str]:
        if no_prefix:
            return [""] * len(commands)

        default_colors = [
            theme.ANSI.PRIMARY,
            theme.ANSI.SECONDARY,
            theme.ANSI.ACCENT,
            theme.ANSI.BLUE,
            theme.ANSI.GREEN,
            theme.ANSI.YELLOW,
        ]
        resolved_colors = colors or []
        palette = resolved_colors or default_colors
        reset = "" if no_color else theme.ANSI.RESET

        index_width = len(str(max(len(commands) - 1, 0)))
        prefixes: list[str] = []
        for index in range(len(commands)):
            name = ""
            if names and index < len(names):
                name = names[index]
            label = name if name else f"{index:{index_width}d}"
            format_value = {
                "index": index,
                "name": name or str(index),
                "label": label,
            }
            raw_prefix = None
            if prefix_format:
                try:
                    raw_prefix = prefix_format.format_map(format_value)
                except (KeyError, ValueError):
                    raw_prefix = None
            if raw_prefix is None:
                raw_prefix = f"[{label}]"

            if no_color or not palette:
                prefixes.append(f"{raw_prefix} ")
                continue
            color = palette[index % len(palette)]
            prefixes.append(f"{color}{raw_prefix}{reset} ")
        return prefixes

    async def run_command(
        self,
        spec: CommandSpec,
        queue: asyncio.Queue[str | None],
        *,
        failure_event: asyncio.Event | None = None,
        process_registry: dict[int, asyncio.subprocess.Process] | None = None,
        registry_lock: asyncio.Lock | None = None,
        subprocess_color: bool = True,
        shell: list[str] | None = None,
    ) -> int:
        env = None
        if subprocess_color:
            env = os.environ.copy()
            env.update(
                {
                    "FORCE_COLOR": "1",
                    "CLICOLOR_FORCE": "1",
                    "RICH_FORCE_TERMINAL": "1",
                    "TERM": env.get("TERM", "xterm-256color"),
                }
            )
        argv = list(shell or self.default_shell())
        argv.append(spec.command)
        try:
            process = await asyncio.create_subprocess_exec(
                *argv,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                start_new_session=os.name != "nt",
            )
        except (FileNotFoundError, PermissionError, OSError) as exc:
            await queue.put(f"{spec.prefix}failed to start: {spec.command}: {exc}\n")
            if failure_event is not None:
                failure_event.set()
            return 127
        if process_registry is not None and registry_lock is not None:
            async with registry_lock:
                process_registry[spec.index] = process
        await queue.put(f"{spec.prefix}started: {spec.command}\n")

        async def read_and_queue(stream: asyncio.StreamReader) -> None:
            while True:
                line = await stream.readline()
                if not line:
                    break
                text = line.decode(errors="replace")
                if not text.endswith("\n"):
                    text = f"{text}\n"
                if not subprocess_color:
                    text = self.strip_ansi(text)
                await queue.put(f"{spec.prefix}{text}")

        tasks: list[asyncio.Task[None]] = []
        if process.stdout is not None:
            tasks.append(asyncio.create_task(read_and_queue(process.stdout)))
        if process.stderr is not None:
            tasks.append(asyncio.create_task(read_and_queue(process.stderr)))
        try:
            return_code = await process.wait()
            if tasks:
                await asyncio.gather(*tasks)
            await queue.put(
                f"{spec.prefix}exited with code {return_code}: {spec.command}\n"
            )
            if failure_event is not None and return_code != 0:
                failure_event.set()
            return return_code
        except asyncio.CancelledError:
            await self.terminate_process(process)
            raise
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            if process_registry is not None and registry_lock is not None:
                async with registry_lock:
                    process_registry.pop(spec.index, None)

    async def run_all(
        self,
        commands: list[str],
        *,
        names: list[str] | None = None,
        colors: list[str] | None = None,
        prefix_format: str | None = None,
        no_prefix: bool = False,
        no_color: bool = False,
        kill_others: bool = False,
        subprocess_color: bool = True,
        shell: list[str] | None = None,
    ) -> list[int]:
        if shell is None:
            shell = self.default_shell()
        prefixes = self.build_prefixes(
            commands,
            names=names,
            colors=colors,
            prefix_format=prefix_format,
            no_prefix=no_prefix,
            no_color=no_color,
        )
        specs = [
            self.CommandSpec(index=index, command=command, prefix=prefixes[index])
            for index, command in enumerate(commands)
        ]
        queue: asyncio.Queue[str | None] = asyncio.Queue()
        failure_event = asyncio.Event() if kill_others else None
        process_registry: dict[int, asyncio.subprocess.Process] = {}
        registry_lock = asyncio.Lock()

        async def writer() -> None:
            while True:
                item = await queue.get()
                if item is None:
                    break
                console.print(item, end="", markup=False, highlight=False)

        writer_task = asyncio.create_task(writer())
        results_task = asyncio.gather(
            *(
                self.run_command(
                    spec,
                    queue,
                    failure_event=failure_event,
                    process_registry=process_registry,
                    registry_lock=registry_lock,
                    subprocess_color=subprocess_color,
                    shell=shell,
                )
                for spec in specs
            )
        )
        failure_wait_task: asyncio.Task[bool] | None = None
        if kill_others and failure_event is not None:
            failure_wait_task = asyncio.create_task(failure_event.wait())
        try:
            if failure_wait_task is not None:
                done, pending = await asyncio.wait(
                    {results_task, failure_wait_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if failure_wait_task in done:
                    await self.terminate_all(process_registry, registry_lock)
                    results = await results_task
                else:
                    results = await results_task
                if failure_wait_task in pending:
                    failure_wait_task.cancel()
                    await asyncio.gather(failure_wait_task, return_exceptions=True)
            else:
                results = await results_task
            return list(results)
        except asyncio.CancelledError:
            await self.terminate_all(process_registry, registry_lock)
            raise
        finally:
            await queue.put(None)
            await writer_task

    def handle(
        self,
        commands: list[str] = Argument(
            ..., help="Commands to run concurrently. Quote each command."
        ),
        names: str | None = Option(
            None,
            "--names",
            "-n",
            help="Comma-separated names to label each command.",
        ),
        colors: str | None = Option(
            None,
            "--colors",
            "-c",
            help="Comma-separated color names for prefixes.",
        ),
        kill_others: bool = Option(
            False,
            "--kill-others",
            "-k",
            help="Stop remaining commands when a command exits non-zero.",
        ),
        prefix_format: str | None = Option(
            None,
            "--prefix-format",
            "-p",
            help="Custom prefix format using {index}, {name}, {label}.",
        ),
        no_prefix: bool = Option(
            False,
            "--no-prefix",
            help="Disable output prefixes.",
        ),
        no_color: bool = Option(
            False,
            "--no-color",
            help="Disable ANSI colors in prefixes.",
        ),
        subprocess_color: bool = Option(
            True,
            "--subprocess-color/--no-subprocess-color",
            help="Enable or disable ANSI colors from subprocess output.",
        ),
        shell: str | None = Option(
            None,
            "--shell",
            "-s",
            help=(
                "Shell command to run as '<shell> <args> <command>' "
                "(default: bash -lc if available, else /bin/sh -c)."
            ),
        ),
    ) -> None:
        resolved_shell: list[str] | None = None
        if isinstance(shell, str):
            resolved_shell = self.parse_shell(shell)
        if resolved_shell is None:
            resolved_shell = self.default_shell()
        name_list = self.parse_csv(names)
        color_names = self.parse_csv(colors)
        resolved_colors: list[str] = []
        for color_name in color_names:
            resolved = self.resolve_color(color_name)
            if resolved:
                resolved_colors.append(resolved)
        try:
            exit_codes = asyncio.run(
                self.run_all(
                    commands,
                    names=name_list,
                    colors=resolved_colors,
                    prefix_format=prefix_format,
                    no_prefix=no_prefix,
                    no_color=no_color,
                    kill_others=kill_others,
                    subprocess_color=subprocess_color,
                    shell=resolved_shell,
                )
            )
        except KeyboardInterrupt:
            raise SystemExit(130) from None
        if any(code != 0 for code in exit_codes):
            raise SystemExit(1)

    @staticmethod
    async def terminate_process(
        process: asyncio.subprocess.Process, *, timeout_seconds: float = 1.0
    ) -> None:
        if process.returncode is not None:
            return
        if os.name != "nt" and process.pid is not None:
            try:
                os.killpg(process.pid, signal.SIGINT)
            except ProcessLookupError:
                return
            except OSError:
                pass
        else:
            process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=0.5)
            return
        except asyncio.TimeoutError:
            pass
        if os.name != "nt" and process.pid is not None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                return
            except OSError:
                pass
        else:
            process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            if os.name != "nt" and process.pid is not None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    return
                except OSError:
                    return
            else:
                process.kill()
            try:
                await asyncio.wait_for(process.wait(), timeout=0.5)
            except asyncio.TimeoutError:
                return

    async def terminate_all(
        self,
        process_registry: dict[int, asyncio.subprocess.Process],
        registry_lock: asyncio.Lock,
    ) -> None:
        async with registry_lock:
            processes = list(process_registry.values())
        if not processes:
            return
        await asyncio.gather(
            *(self.terminate_process(process) for process in processes),
            return_exceptions=True,
        )

    @staticmethod
    def default_shell() -> list[str]:
        bash_path = shutil.which("bash")
        if bash_path:
            return [bash_path, "-lc"]
        return ["/bin/sh", "-c"]

    @staticmethod
    def parse_shell(shell: str) -> list[str] | None:
        shell = shell.strip()
        if not shell:
            console.print(
                "Shell cannot be empty. Use --shell 'bash -lc', or omit to use defaults."
            )
            raise SystemExit(1)
        shell_parts = shlex.split(shell)
        if not shell_parts:
            console.print(
                "Shell cannot be empty. Use --shell 'bash -lc', or omit to use defaults."
            )
            raise SystemExit(1)
        shell_executable = shell_parts[0]
        if os.path.isabs(shell_executable):
            if not (
                os.path.isfile(shell_executable)
                and os.access(shell_executable, os.X_OK)
            ):
                console.print(f"Shell not found or not executable: {shell_executable}")
                raise SystemExit(1)
            return [shell_executable, *shell_parts[1:]]
        resolved_executable = shutil.which(shell_executable)
        if resolved_executable is None:
            console.print(f"Shell not found on PATH: {shell_executable}")
            raise SystemExit(1)
        return [resolved_executable, *shell_parts[1:]]
