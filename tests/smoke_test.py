from __future__ import annotations

import shutil
import subprocess
import sys


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )


def assert_userun_help() -> None:
    executable = shutil.which("userun")
    if executable is None:
        raise AssertionError("userun executable not found in PATH")

    result = run_command([executable, "--help"])
    output = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0:
        raise AssertionError(
            "userun --help failed with exit code "
            f"{result.returncode}. Output:\n{output}"
        )
    if "concurrent" not in output:
        raise AssertionError(
            "userun --help output missing 'concurrent'. Output:\n" + output
        )


def assert_import() -> None:
    import userun

    if not hasattr(userun, "main"):
        raise AssertionError("userun.main not found")


def main() -> int:
    assert_import()
    assert_userun_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
