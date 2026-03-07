"""ConcurrentCommand - CLI command."""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from typing import TextIO

from usecli import Argument, BaseCommand


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

    def build_prefixes(self, commands: list[str]) -> list[str]:
        colors = [
            "\x1b[31m",
            "\x1b[32m",
            "\x1b[33m",
            "\x1b[34m",
            "\x1b[35m",
            "\x1b[36m",
        ]
        reset = "\x1b[0m"
        index_width = len(str(max(len(commands) - 1, 0)))
        prefixes: list[str] = []
        for index in range(len(commands)):
            label = f"[{index:{index_width}d}]"
            color = colors[index % len(colors)]
            prefixes.append(f"{color}{label}{reset} ")
        return prefixes

    async def run_command(
        self, spec: CommandSpec, queue: asyncio.Queue[str | None]
    ) -> int:
        process = await asyncio.create_subprocess_shell(
            spec.command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
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
        return return_code

    async def run_all(self, commands: list[str]) -> list[int]:
        prefixes = self.build_prefixes(commands)
        specs = [
            self.CommandSpec(index=index, command=command, prefix=prefixes[index])
            for index, command in enumerate(commands)
        ]
        queue: asyncio.Queue[str | None] = asyncio.Queue()

        async def writer() -> None:
            while True:
                item = await queue.get()
                if item is None:
                    break
                sys.stdout.write(item)
                sys.stdout.flush()

        writer_task = asyncio.create_task(writer())
        results = await asyncio.gather(
            *(self.run_command(spec, queue) for spec in specs)
        )
        await queue.put(None)
        await writer_task
        return list(results)

    def handle(
        self,
        commands: list[str] = Argument(
            ..., help="Commands to run concurrently. Quote each command."
        ),
    ) -> None:
        exit_codes = asyncio.run(self.run_all(commands))
        if any(code != 0 for code in exit_codes):
            raise SystemExit(1)
