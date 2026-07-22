"""Shared Steam/BUFF platform selection helpers for CLI flows."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PlatformSelection:
    steam: bool = True
    buff: bool = True


DEFAULT_PLATFORM_SELECTION = PlatformSelection()


def add_platform_flags(
    parser: argparse.ArgumentParser,
    *,
    steam_default: bool = True,
    buff_default: bool = True,
) -> None:
    parser.add_argument("--steam", action=argparse.BooleanOptionalAction, default=steam_default)
    parser.add_argument("--buff", action=argparse.BooleanOptionalAction, default=buff_default)


def platform_selection_from_args(args: argparse.Namespace) -> PlatformSelection:
    return PlatformSelection(
        steam=bool(getattr(args, "steam", True)),
        buff=bool(getattr(args, "buff", True)),
    )


def platform_selection_from_env(
    values: Mapping[str, str],
    *,
    default: PlatformSelection = DEFAULT_PLATFORM_SELECTION,
) -> PlatformSelection:
    return PlatformSelection(
        steam=_bool(values.get("SCRAPE_STEAM"), default=default.steam),
        buff=_bool(values.get("SCRAPE_BUFF"), default=default.buff),
    )


def append_platform_flags(command: list[str], selection: PlatformSelection) -> None:
    command.append("--steam" if selection.steam else "--no-steam")
    command.append("--buff" if selection.buff else "--no-buff")


def append_buff_flag(command: list[str], selection: PlatformSelection) -> None:
    command.append("--buff" if selection.buff else "--no-buff")


def append_no_buff_when_disabled(command: list[str], selection: PlatformSelection) -> None:
    if not selection.buff:
        command.append("--no-buff")


def platform_env(selection: PlatformSelection) -> dict[str, str]:
    return {
        "SCRAPE_STEAM": "true" if selection.steam else "false",
        "SCRAPE_BUFF": "true" if selection.buff else "false",
    }


def _bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}
