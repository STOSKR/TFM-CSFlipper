import subprocess
import sys
from collections.abc import Sequence

import pytest

import steamdt


def test_steamdt_wrapper_disables_uu_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[Sequence[str]] = []

    def fake_run(command: Sequence[str], *, check: bool) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(sys, "argv", ["steamdt.py", "1", "--no-output"])
    monkeypatch.setattr(subprocess, "run", fake_run)

    assert steamdt.main() == 0

    command = tuple(str(part) for part in commands[0])
    assert _option_pair(command, "--timeout") == ("--timeout", "60")
    assert _option_pair(command, "--retries") == ("--retries", "2")
    assert "--no-platform-uu" in command
    assert "--platform-uu" not in command


def test_steamdt_wrapper_can_enable_uu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[Sequence[str]] = []

    def fake_run(command: Sequence[str], *, check: bool) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(sys, "argv", ["steamdt.py", "1", "--uu", "--no-output"])
    monkeypatch.setattr(subprocess, "run", fake_run)

    assert steamdt.main() == 0

    command = tuple(str(part) for part in commands[0])
    assert "--platform-uu" in command
    assert "--no-platform-uu" not in command


def test_steamdt_wrapper_can_override_timeout_and_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[Sequence[str]] = []

    def fake_run(command: Sequence[str], *, check: bool) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(
        sys,
        "argv",
        ["steamdt.py", "1", "--timeout", "90", "--retries", "3", "--no-output"],
    )
    monkeypatch.setattr(subprocess, "run", fake_run)

    assert steamdt.main() == 0

    command = tuple(str(part) for part in commands[0])
    assert _option_pair(command, "--timeout") == ("--timeout", "90")
    assert _option_pair(command, "--retries") == ("--retries", "3")


def _option_pair(command: tuple[str, ...], option: str) -> tuple[str, str]:
    index = command.index(option)
    return command[index], command[index + 1]
