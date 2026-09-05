"""Runtime numeric configuration loaded from the root TOML file."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from packages.simulation.risk import PortfolioRiskConfig

DEFAULT_CONFIG_PATH = Path("csflipper_config.toml")


@dataclass(frozen=True, slots=True)
class DiscoveryConfig:
    candidates_limit: int = 25
    min_price: Decimal | None = Decimal("300")
    min_volume: int | None = 12
    currency: str = "EUR"


@dataclass(frozen=True, slots=True)
class FeeConfig:
    steam_sale_percent: Decimal = Decimal("13")
    withdrawal_percent: Decimal = Decimal("20")
    withdrawal_percent_by_balance: dict[str, Decimal] | None = None

    @property
    def steam_sale_rate(self) -> Decimal:
        return self.steam_sale_percent / Decimal("100")

    @property
    def withdrawal_rate(self) -> Decimal:
        return self.withdrawal_percent / Decimal("100")

    def withdrawal_percent_for_balance(self, balance_type: str) -> Decimal:
        key = _balance_key(balance_type)
        configured = self.withdrawal_percent_by_balance or {}
        return configured.get(key, self.withdrawal_percent)


@dataclass(frozen=True, slots=True)
class SteamDTProfileConfig:
    balance_type: str
    sell_mode: str
    buy_mode: str | None


@dataclass(frozen=True, slots=True)
class SteamDTConfig:
    default_profile: str
    run_all_profiles: bool
    enabled_profiles: tuple[str, ...]
    profiles: dict[str, SteamDTProfileConfig]


@dataclass(frozen=True, slots=True)
class WorkerConfig:
    steam_concurrency: int = 1
    buff_concurrency: int = 1
    batch_size: int = 10


@dataclass(frozen=True, slots=True)
class DelayConfig:
    steam_min_seconds: float = 1.5
    steam_max_seconds: float = 4.0
    buff_min_seconds: float = 5.0
    buff_max_seconds: float = 10.0


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    discovery: DiscoveryConfig
    fees: FeeConfig
    steamdt: SteamDTConfig
    workers: WorkerConfig
    delays: DelayConfig
    risk: PortfolioRiskConfig


def load_runtime_config(path: Path | str = DEFAULT_CONFIG_PATH) -> RuntimeConfig:
    config_path = Path(path)
    payload: dict[str, Any] = {}
    if config_path.exists():
        payload = tomllib.loads(config_path.read_text(encoding="utf-8"))

    return RuntimeConfig(
        discovery=_discovery_config(_section(payload, "discovery")),
        fees=_fee_config(_section(payload, "fees")),
        steamdt=_steamdt_config(_section(payload, "steamdt")),
        workers=_worker_config(_section(payload, "workers")),
        delays=_delay_config(_section(payload, "delays")),
        risk=_risk_config(_section(payload, "risk")),
    )


def _discovery_config(section: dict[str, Any]) -> DiscoveryConfig:
    return DiscoveryConfig(
        candidates_limit=_int(section, "candidates_limit", 25),
        min_price=_optional_decimal(section, "min_price", Decimal("300")),
        min_volume=_optional_int(section, "min_volume", 12),
        currency=_str(section, "currency", "EUR"),
    )


def _fee_config(section: dict[str, Any]) -> FeeConfig:
    return FeeConfig(
        steam_sale_percent=_decimal(section, "steam_sale_percent", Decimal("13")),
        withdrawal_percent=_decimal(section, "withdrawal_percent", Decimal("20")),
        withdrawal_percent_by_balance=_balance_withdrawal_map(
            _section(section, "withdrawal_percent_by_balance")
        ),
    )


def _steamdt_config(section: dict[str, Any]) -> SteamDTConfig:
    profile_payload = _section(section, "profiles")
    profiles = {
        key: _steamdt_profile(value)
        for key, value in profile_payload.items()
        if isinstance(value, dict)
    }
    if not profiles:
        profiles = _default_steamdt_profiles()
    default_profile = _str(section, "default_profile", "platform_arbitrage_safe")
    if default_profile not in profiles:
        default_profile = "platform_arbitrage_safe"
    enabled_profiles = tuple(
        profile
        for profile in _str_list(section, "enabled_profiles", tuple(profiles))
        if profile in profiles
    )
    if not enabled_profiles:
        enabled_profiles = tuple(profiles)
    return SteamDTConfig(
        default_profile=default_profile,
        run_all_profiles=_bool(section, "run_all_profiles", False),
        enabled_profiles=enabled_profiles,
        profiles=profiles,
    )


def _steamdt_profile(section: dict[str, Any]) -> SteamDTProfileConfig:
    buy_mode = _str(section, "buy_mode", "")
    return SteamDTProfileConfig(
        balance_type=_str(section, "balance_type", "Platform Balance"),
        sell_mode=_str(section, "sell_mode", "Sell at Platform Lowest Price"),
        buy_mode=buy_mode or None,
    )


def _default_steamdt_profiles() -> dict[str, SteamDTProfileConfig]:
    return {
        "steam_sell_slow": SteamDTProfileConfig(
            balance_type="STEAM Balance",
            sell_mode="Sell at STEAM Lowest Price",
            buy_mode="Buy via Platform Buy Order",
        ),
        "steam_sell_fast": SteamDTProfileConfig(
            balance_type="STEAM Balance",
            sell_mode="Sell to STEAM Highest Buy Order",
            buy_mode="Buy via Platform Buy Order",
        ),
        "platform_arbitrage_safe": SteamDTProfileConfig(
            balance_type="Platform Balance",
            sell_mode="Sell at Platform Lowest Price",
            buy_mode="Buy via STEAM Buy Order",
        ),
        "platform_arbitrage_fast": SteamDTProfileConfig(
            balance_type="Platform Balance",
            sell_mode="Sell to Platform Highest Buy Order",
            buy_mode="Buy at STEAM Lowest Price",
        ),
    }


def _worker_config(section: dict[str, Any]) -> WorkerConfig:
    return WorkerConfig(
        steam_concurrency=_int(section, "steam_concurrency", 1),
        buff_concurrency=_int(section, "buff_concurrency", 1),
        batch_size=_int(section, "batch_size", 10),
    )


def _delay_config(section: dict[str, Any]) -> DelayConfig:
    return DelayConfig(
        steam_min_seconds=_float(section, "steam_min_seconds", 1.5),
        steam_max_seconds=_float(section, "steam_max_seconds", 4.0),
        buff_min_seconds=_float(section, "buff_min_seconds", 5.0),
        buff_max_seconds=_float(section, "buff_max_seconds", 10.0),
    )


def _risk_config(section: dict[str, Any]) -> PortfolioRiskConfig:
    return PortfolioRiskConfig(
        max_position_fraction=_decimal(
            section,
            "max_position_fraction",
            Decimal("0.20"),
        ),
        max_item_fraction=_decimal(section, "max_item_fraction", Decimal("0.30")),
        max_platform_fraction=_decimal(section, "max_platform_fraction", Decimal("0.70")),
        min_cash_fraction=_decimal(section, "min_cash_fraction", Decimal("0.10")),
        warning_usage_ratio=_decimal(section, "warning_usage_ratio", Decimal("0.80")),
        max_open_positions=_optional_int(section, "max_open_positions", None),
    )


def _section(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    return value if isinstance(value, dict) else {}


def _str(section: dict[str, Any], key: str, default: str) -> str:
    value = section.get(key, default)
    return str(value)


def _str_list(section: dict[str, Any], key: str, default: tuple[str, ...]) -> tuple[str, ...]:
    value = section.get(key)
    if value is None:
        return default
    if isinstance(value, list | tuple):
        return tuple(str(item) for item in value)
    return (str(value),)


def _int(section: dict[str, Any], key: str, default: int) -> int:
    value = section.get(key, default)
    return int(value)


def _optional_int(section: dict[str, Any], key: str, default: int | None) -> int | None:
    value = section.get(key, default)
    return None if value is None else int(value)


def _float(section: dict[str, Any], key: str, default: float) -> float:
    value = section.get(key, default)
    return float(value)


def _bool(section: dict[str, Any], key: str, default: bool) -> bool:
    value = section.get(key, default)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _decimal(section: dict[str, Any], key: str, default: Decimal) -> Decimal:
    value = section.get(key, default)
    return Decimal(str(value))


def _optional_decimal(
    section: dict[str, Any],
    key: str,
    default: Decimal | None,
) -> Decimal | None:
    value = section.get(key, default)
    return None if value is None else Decimal(str(value))


def _balance_withdrawal_map(section: dict[str, Any]) -> dict[str, Decimal]:
    return {_balance_key(key): Decimal(str(value)) for key, value in section.items()}


def _balance_key(value: str) -> str:
    return value.strip().lower().replace(" ", "_")
