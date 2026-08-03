import pytest

import userun


def test_main_prints_hello(capsys: pytest.CaptureFixture[str]) -> None:
    userun.main()
    captured = capsys.readouterr()
    assert "Hello from userun!" in captured.out
