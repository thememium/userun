from __future__ import annotations

import importlib.metadata
import pathlib
import re
import shutil
import subprocess
import sys


def coerce_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except subprocess.TimeoutExpired as exc:
        output = coerce_output(exc.stdout) + coerce_output(exc.stderr)
        raise AssertionError("Command timed out. Output:\n" + output) from exc


def assert_userun_help() -> None:
    executable = shutil.which("userun")
    if executable is None:
        raise AssertionError("userun executable not found in PATH")

    executable_path = pathlib.Path(executable)
    python_bin_dir = pathlib.Path(sys.executable).parent
    try:
        same_env = executable_path.parent.samefile(python_bin_dir)
    except FileNotFoundError:
        same_env = executable_path.parent.resolve() == python_bin_dir.resolve()
    if not same_env:
        raise AssertionError(
            "userun executable is not from the current environment. "
            f"sys.executable={sys.executable} userun={executable}"
        )

    result = run_command([executable, "--help"])
    output = coerce_output(result.stdout) + coerce_output(result.stderr)
    if result.returncode != 0:
        raise AssertionError(
            "userun --help failed with exit code "
            f"{result.returncode}. Output:\n{output}"
        )
    if re.search(r"\bconcurrent\b", output) is None:
        raise AssertionError(
            "userun --help output missing 'concurrent'. Output:\n" + output
        )

    subcommand = run_command([executable, "concurrent", "--help"])
    sub_output = coerce_output(subcommand.stdout) + coerce_output(subcommand.stderr)
    if subcommand.returncode != 0:
        raise AssertionError(
            "userun concurrent --help failed with exit code "
            f"{subcommand.returncode}. Output:\n{sub_output}"
        )


def assert_import() -> None:
    import userun

    package_file = pathlib.Path(userun.__file__).resolve()
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    if package_file.is_relative_to(repo_root):
        raise AssertionError(
            "userun import resolved to the repo checkout. "
            f"repo_root={repo_root} userun.__file__={userun.__file__}"
        )

    importlib.metadata.version("userun")


def main() -> int:
    assert_import()
    assert_userun_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
