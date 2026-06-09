"""Runtime numeric configuration loaded from the root TOML file."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_PATH = Path("csflipper_config.toml")


@dataclass(frozen=True, slots=True)
class DiscoveryConfig:
    candidates_limit: int = 50
    min_price: Decimal | None = Decimal("300")
    min_volume: int | None = 12
    currency: str = "EUR"


@dataclass(frozen=True, slots=True)
class FeeConfig:
    steam_sale_percent: Decimal = Decimal("13")
    withdrawal_percent: Decimal = Decimal("20")

    @property
    def steam_sale_rate(self) -> Decimal:
        return self.steam_sale_percent / Decimal("100")

    @property
    def withdrawal_rate(self) -> Decimal:
        return self.withdrawal_percent / Decimal("100")


@dataclass(frozen=True, slots=True)
class WorkerConfig:
    steam_concurrency: int = 1
    buff_concurrency: int = 1
    batch_size: int = 5


@dataclass(frozen=True, slots=True)
class DelayConfig:
    steam_min_seconds: float = 1.5
    steam_max_seconds: float = 4.0
    buff_min_seconds: float = 2.5
    buff_max_seconds: float = 6.0


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    discovery: DiscoveryConfig
    fees: FeeConfig
    workers: WorkerConfig
    delays: DelayConfig


def load_runtime_config(path: Path | str = DEFAULT_CONFIG_PATH) -> RuntimeConfig:
    config_path = Path(path)
    payload: dict[str, Any] = {}
    if config_path.exists():
        payload = tomllib.loads(config_path.read_text(encoding="utf-8"))

    return RuntimeConfig(
        discovery=_discovery_config(_section(payload, "discovery")),
        fees=_fee_config(_section(payload, "fees")),
        workers=_worker_config(_section(payload, "workers")),
        delays=_delay_config(_section(payload, "delays")),
    )


def _discovery_config(section: dict[str, Any]) -> DiscoveryConfig:
    return DiscoveryConfig(
        candidates_limit=_int(section, "candidates_limit", 50),
        min_price=_optional_decimal(section, "min_price", Decimal("300")),
        min_volume=_optional_int(section, "min_volume", 12),
        currency=_str(section, "currency", "EUR"),
    )


def _fee_config(section: dict[str, Any]) -> FeeConfig:
    return FeeConfig(
        steam_sale_percent=_decimal(section, "steam_sale_percent", Decimal("13")),
        withdrawal_percent=_decimal(section, "withdrawal_percent", Decimal("20")),
    )


def _worker_config(section: dict[str, Any]) -> WorkerConfig:
    return WorkerConfig(
        steam_concurrency=_int(section, "steam_concurrency", 1),
        buff_concurrency=_int(section, "buff_concurrency", 1),
        batch_size=_int(section, "batch_size", 5),
    )


def _delay_config(section: dict[str, Any]) -> DelayConfig:
    return DelayConfig(
        steam_min_seconds=_float(section, "steam_min_seconds", 1.5),
        steam_max_seconds=_float(section, "steam_max_seconds", 4.0),
        buff_min_seconds=_float(section, "buff_min_seconds", 2.5),
        buff_max_seconds=_float(section, "buff_max_seconds", 6.0),
    )


def _section(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    return value if isinstance(value, dict) else {}


def _str(section: dict[str, Any], key: str, default: str) -> str:
    value = section.get(key, default)
    return str(value)


def _int(section: dict[str, Any], key: str, default: int) -> int:
    value = section.get(key, default)
    return int(value)


def _optional_int(section: dict[str, Any], key: str, default: int | None) -> int | None:
    value = section.get(key, default)
    return None if value is None else int(value)


def _float(section: dict[str, Any], key: str, default: float) -> float:
    value = section.get(key, default)
    return float(value)


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
