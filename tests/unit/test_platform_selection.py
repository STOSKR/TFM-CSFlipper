import argparse

from apps.cli.platform_selection import (
    PlatformSelection,
    append_platform_flags,
    platform_env,
    platform_selection_from_args,
    platform_selection_from_env,
)


def test_platform_selection_defaults_to_steam_and_buff() -> None:
    assert platform_selection_from_args(argparse.Namespace()) == PlatformSelection(
        steam=True,
        buff=True,
    )


def test_platform_selection_can_disable_buff() -> None:
    selection = platform_selection_from_args(argparse.Namespace(steam=True, buff=False))
    command: list[str] = []

    append_platform_flags(command, selection)

    assert command == ["--steam", "--no-buff"]


def test_platform_selection_allows_buff_only() -> None:
    selection = platform_selection_from_args(argparse.Namespace(steam=False, buff=True))
    command: list[str] = []

    append_platform_flags(command, selection)

    assert command == ["--no-steam", "--buff"]


def test_platform_selection_from_env_can_disable_buff() -> None:
    assert platform_selection_from_env({"SCRAPE_BUFF": "false"}) == PlatformSelection(
        steam=True,
        buff=False,
    )


def test_platform_env_uses_scrape_keys() -> None:
    assert platform_env(PlatformSelection(steam=False, buff=True)) == {
        "SCRAPE_STEAM": "false",
        "SCRAPE_BUFF": "true",
    }
