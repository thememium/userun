"""ConcurrentCommand - CLI command."""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from typing import TextIO

from usecli import Argument, BaseCommand, Option, theme


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
    ) -> int:
        process = await asyncio.create_subprocess_shell(
            spec.command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
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
                await queue.put(f"{spec.prefix}{text}")

        tasks: list[asyncio.Task[None]] = []
        if process.stdout is not None:
            tasks.append(asyncio.create_task(read_and_queue(process.stdout)))
        if process.stderr is not None:
            tasks.append(asyncio.create_task(read_and_queue(process.stderr)))

        return_code = await process.wait()
        if tasks:
            await asyncio.gather(*tasks)
        await queue.put(
            f"{spec.prefix}exited with code {return_code}: {spec.command}\n"
        )
        if process_registry is not None and registry_lock is not None:
            async with registry_lock:
                process_registry.pop(spec.index, None)
        if failure_event is not None and return_code != 0:
            failure_event.set()
        return return_code

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
    ) -> list[int]:
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
                sys.stdout.write(item)
                sys.stdout.flush()

        writer_task = asyncio.create_task(writer())
        results_task = asyncio.gather(
            *(
                self.run_command(
                    spec,
                    queue,
                    failure_event=failure_event,
                    process_registry=process_registry,
                    registry_lock=registry_lock,
                )
                for spec in specs
            )
        )

        if kill_others and failure_event is not None:
            await failure_event.wait()
            async with registry_lock:
                for process in process_registry.values():
                    if process.returncode is None:
                        process.terminate()

        results = await results_task
        await queue.put(None)
        await writer_task
        return list(results)

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
    ) -> None:
        name_list = self.parse_csv(names)
        color_names = self.parse_csv(colors)
        resolved_colors: list[str] = []
        for color_name in color_names:
            resolved = self.resolve_color(color_name)
            if resolved:
                resolved_colors.append(resolved)
        exit_codes = asyncio.run(
            self.run_all(
                commands,
                names=name_list,
                colors=resolved_colors,
                prefix_format=prefix_format,
                no_prefix=no_prefix,
                no_color=no_color,
                kill_others=kill_others,
            )
        )
        if any(code != 0 for code in exit_codes):
            raise SystemExit(1)
