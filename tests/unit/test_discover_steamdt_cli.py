import argparse
import sys

import pytest

from apps.cli import discover_steamdt_hanging
from apps.cli.discover_steamdt_hanging import _selected_profiles
from packages.runtime_config import SteamDTConfig, SteamDTProfileConfig


def test_selected_profiles_uses_enabled_profiles_for_all_profiles_mode() -> None:
    config = SteamDTConfig(
        default_profile="steam_sell_slow",
        run_all_profiles=True,
        enabled_profiles=("steam_sell_slow", "platform_arbitrage_safe"),
        profiles={
            "steam_sell_slow": SteamDTProfileConfig(
                balance_type="STEAM Balance",
                sell_mode="Sell at STEAM Lowest Price",
                buy_mode=None,
            ),
            "steam_sell_fast": SteamDTProfileConfig(
                balance_type="STEAM Balance",
                sell_mode="Sell to STEAM Highest Buy Order",
                buy_mode=None,
            ),
            "platform_arbitrage_safe": SteamDTProfileConfig(
                balance_type="Platform Balance",
                sell_mode="Sell at Platform Lowest Price",
                buy_mode="Buy via STEAM Buy Order",
            ),
        },
    )

    selected = _selected_profiles(argparse.Namespace(all_profiles=True), config)

    assert tuple(profile for profile, _config in selected) == (
        "steam_sell_slow",
        "platform_arbitrage_safe",
    )


def test_main_propagates_discover_exit_code(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_discover(args: argparse.Namespace) -> int:
        return 124

    monkeypatch.setattr(discover_steamdt_hanging, "discover", fake_discover)
    monkeypatch.setattr(sys, "argv", ["discover"])

    with pytest.raises(SystemExit) as exc_info:
        discover_steamdt_hanging.main()

    assert exc_info.value.code == 124
