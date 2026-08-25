"""Build supervised trading datasets from normalized Steam/BUFF history."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
import pyarrow as pa
import pyarrow.parquet as pq

from packages.simulation.economics import (
    BUFF,
    STEAM,
    MarketEconomicsConfig,
    default_excel_economics_config,
    effective_cash_value,
    net_sale_value_eur,
    return_ratio,
)

TRADING_TARGET_COLUMN = "is_profitable"
TRADING_DATE_COLUMN = "observed_day"
TRADING_TRACE_COLUMNS = (
    "item_id",
    "representation_name",
    "name",
    "quality",
    "stattrak",
    TRADING_DATE_COLUMN,
)
TRADING_ROUTE_COLUMNS = (
    "buy_platform",
    "buy_price_type",
    "sell_platform",
    "sell_price_type",
    "cash_destination",
)
TRADING_NON_FEATURE_COLUMNS = frozenset(
    (
        *TRADING_TRACE_COLUMNS,
        *TRADING_ROUTE_COLUMNS,
        "future_day",
        "target_future_day",
        "future_steam_sell_price_eur",
        "future_steam_net_sale_eur",
        "future_steam_cash_value_eur",
        "future_buff_buy_order_price_eur",
        "future_buff_buy_order_net_sale_eur",
        "future_exit_net_eur",
        "future_cash_value_eur",
        "future_profit_eur",
        "future_cash_profit_eur",
        "future_return",
        "future_cash_return",
        TRADING_TARGET_COLUMN,
    )
)


@dataclass(frozen=True, slots=True)
class TradingDatasetBuildConfig:
    output_dir: Path
    trade_direction: str = "buff_to_steam_sell"
    horizon_days: int = 8
    future_tolerance_days: int = 0
    min_profit_eur: Decimal = Decimal("0")
    min_return: Decimal = Decimal("0.10")
    cny_per_eur: Decimal = Decimal("8")
    steam_sale_factor: Decimal = Decimal("0.87")
    buff_sale_factor: Decimal = Decimal("0.975")
    steam_cashout_loss: Decimal = Decimal("0.20")
    start_date: datetime | None = None
    validation_start: datetime = datetime(2026, 1, 1)
    test_start: datetime = datetime(2026, 3, 1)
    test_end: datetime | None = None
    purge_gap_days: int = 0


def build_trading_dataset_from_history(
    history: pd.DataFrame,
    *,
    config: TradingDatasetBuildConfig,
) -> dict[str, Any]:
    frame = trading_examples_from_history(history, config=config)
    feature_columns = tuple(
        column
        for column in frame.columns
        if column not in TRADING_NON_FEATURE_COLUMNS and not frame[column].isna().all()
    )
    numeric_features = tuple(
        column for column in feature_columns if pd.api.types.is_numeric_dtype(frame[column])
    )
    categorical_features = tuple(
        column for column in feature_columns if column not in numeric_features
    )

    output_columns = (
        *TRADING_TRACE_COLUMNS,
        *TRADING_ROUTE_COLUMNS,
        *feature_columns,
        TRADING_TARGET_COLUMN,
    )
    output_dir = config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    split_frames = _split_frames(frame, config=config)
    split_stats = {}
    schema = pa.Schema.from_pandas(frame.loc[:, output_columns], preserve_index=False)
    for split_name, split in split_frames.items():
        split_stats[split_name] = _split_stats(split)
        table = pa.Table.from_pandas(
            split.loc[:, output_columns],
            schema=schema,
            preserve_index=False,
        )
        pq.write_table(table, output_dir / f"{split_name}.parquet")  # type: ignore[no-untyped-call]

    metadata = {
        "schema_version": "trading_supervised_dataset.v1",
        "created_at": datetime.now(tz=UTC).isoformat(),
        "output_dir": str(output_dir),
        "rows_included": int(len(frame)),
        "date_column": TRADING_DATE_COLUMN,
        "target_column": TRADING_TARGET_COLUMN,
        "target_semantics": (
            f"1 when {config.trade_direction} after horizon beats configured min profit "
            "and return after sale fees"
        ),
        "trade_direction": config.trade_direction,
        "horizon_days": config.horizon_days,
        "future_tolerance_days": config.future_tolerance_days,
        "purge_gap_days": config.purge_gap_days,
        "min_profit_eur": str(config.min_profit_eur),
        "min_return": str(config.min_return),
        "cny_per_eur": str(config.cny_per_eur),
        "steam_sale_factor": str(config.steam_sale_factor),
        "buff_sale_factor": str(config.buff_sale_factor),
        "steam_cashout_loss": str(config.steam_cashout_loss),
        "split_policy": {
            "start": (
                f"{TRADING_DATE_COLUMN} >= {config.start_date.date().isoformat()}"
                if config.start_date is not None
                else None
            ),
            "train": f"{TRADING_DATE_COLUMN} < {(config.validation_start - timedelta(days=config.purge_gap_days)).date().isoformat()}",
            "validation": (
                f"{config.validation_start.date().isoformat()} <= {TRADING_DATE_COLUMN} "
                f"< {(config.test_start - timedelta(days=config.purge_gap_days)).date().isoformat()}"
            ),
            "test": (
                f"{config.test_start.date().isoformat()} <= {TRADING_DATE_COLUMN} "
                f"< {config.test_end.date().isoformat()}"
                if config.test_end is not None
                else f"{TRADING_DATE_COLUMN} >= {config.test_start.date().isoformat()}"
            ),
        },
        "splits": split_stats,
        "trace_columns": list(TRADING_TRACE_COLUMNS),
        "route_columns": list(TRADING_ROUTE_COLUMNS),
        "feature_columns": list(feature_columns),
        "numeric_features": list(numeric_features),
        "categorical_features": list(categorical_features),
        "primary_group_column": "representation_name",
        "excluded_columns": sorted(TRADING_NON_FEATURE_COLUMNS),
    }
    _write_json(output_dir / "metadata.json", metadata)
    return metadata


def trading_examples_from_history(
    history: pd.DataFrame,
    *,
    config: TradingDatasetBuildConfig,
) -> pd.DataFrame:
    if config.horizon_days <= 0:
        raise ValueError("horizon_days must be positive")
    if config.future_tolerance_days < 0:
        raise ValueError("future_tolerance_days must be non-negative")
    required = {
        "item_id",
        "representation_name",
        "name",
        "quality",
        "stattrak",
        "observed_at",
        "platform_id",
        "metric_name",
        "metric_value",
        "price_eur",
    }
    missing = required - set(history.columns)
    if missing:
        raise ValueError(f"missing required history columns: {', '.join(sorted(missing))}")

    daily = _daily_metrics(history)
    daily = _ensure_metric_columns(daily)
    if config.start_date is not None:
        start_day = pd.Timestamp(config.start_date.date())
        daily = daily[daily[TRADING_DATE_COLUMN] >= start_day].copy()
    daily = daily.dropna(subset=_required_price_columns(config.trade_direction))
    if daily.empty:
        return _empty_trading_frame()

    economics = _economics_config(config)
    daily["steam_net_sale_eur"] = daily["steam_sell_price_eur"].map(
        lambda value: float(
            net_sale_value_eur(
                Decimal(str(value)),
                sale_platform=STEAM,
                sale_currency="EUR",
                config=economics,
            )
        )
    )
    daily["steam_cash_value_eur"] = daily["steam_net_sale_eur"].map(
        lambda value: float(
            effective_cash_value(Decimal(str(value)), platform=STEAM, config=economics)
        )
    )
    daily["buff_buy_order_net_sale_eur"] = daily["buff_buy_order_price_eur"].map(
        lambda value: float(
            net_sale_value_eur(
                Decimal(str(value)),
                sale_platform=BUFF,
                sale_currency="EUR",
                config=economics,
            )
        )
        if pd.notna(value)
        else np.nan
    )
    daily["buy_price_eur"] = _buy_price(daily, config.trade_direction)
    daily["current_exit_net_eur"] = _current_exit_value(daily, config.trade_direction)
    daily["current_cash_value_eur"] = _current_cash_value(daily, config.trade_direction)
    daily["current_profit_eur"] = daily["current_exit_net_eur"] - daily["buy_price_eur"]
    daily["current_return"] = _safe_ratio(daily["current_profit_eur"], daily["buy_price_eur"])
    daily["current_cash_profit_eur"] = daily["current_cash_value_eur"] - daily["buy_price_eur"]
    daily["current_cash_return"] = _safe_ratio(
        daily["current_cash_profit_eur"],
        daily["buy_price_eur"],
    )
    for column, value in _route_columns(config.trade_direction).items():
        daily[column] = value
    daily["steam_buff_spread_eur"] = (
        daily["steam_sell_price_eur"] - daily["buff_sell_price_eur"]
    )
    daily["steam_buff_spread_pct"] = _safe_ratio(
        daily["steam_buff_spread_eur"],
        daily["buff_sell_price_eur"],
    )
    daily["buff_buy_sell_spread_eur"] = (
        daily["buff_sell_price_eur"] - daily["buff_buy_order_price_eur"]
    )
    daily["buff_buy_sell_spread_pct"] = _safe_ratio(
        daily["buff_buy_sell_spread_eur"],
        daily["buff_sell_price_eur"],
    )
    daily["log_steam_price_eur"] = np.log1p(daily["steam_sell_price_eur"])
    daily["log_buff_price_eur"] = np.log1p(daily["buff_sell_price_eur"])
    daily["log_steam_sales_count"] = np.log1p(daily["steam_sales_count"].fillna(0))
    daily["log_buff_listing_count"] = np.log1p(daily["buff_listing_count"].fillna(0))
    daily = _add_time_features(daily)
    daily = _add_lag_features(
        daily,
        columns=(
            "steam_sell_price_eur",
            "buff_sell_price_eur",
            "buff_buy_order_price_eur",
            "steam_sales_count",
            "buff_listing_count",
        ),
    )

    future = daily.loc[
        :,
        [
            "item_id",
            TRADING_DATE_COLUMN,
            "steam_sell_price_eur",
            "steam_net_sale_eur",
            "steam_cash_value_eur",
            "buff_buy_order_price_eur",
            "buff_buy_order_net_sale_eur",
        ],
    ].rename(
        columns={
            TRADING_DATE_COLUMN: "future_day",
            "steam_sell_price_eur": "future_steam_sell_price_eur",
            "steam_net_sale_eur": "future_steam_net_sale_eur",
            "steam_cash_value_eur": "future_steam_cash_value_eur",
            "buff_buy_order_price_eur": "future_buff_buy_order_price_eur",
            "buff_buy_order_net_sale_eur": "future_buff_buy_order_net_sale_eur",
        }
    )
    examples = daily.copy().sort_values(["item_id", TRADING_DATE_COLUMN])
    examples["target_future_day"] = examples[TRADING_DATE_COLUMN] + pd.to_timedelta(
        config.horizon_days,
        unit="D",
    )
    examples = pd.merge_asof(
        examples.sort_values("target_future_day"),
        future.sort_values("future_day"),
        left_on="target_future_day",
        right_on="future_day",
        by="item_id",
        direction="forward",
        tolerance=pd.Timedelta(days=config.future_tolerance_days),
    ).dropna(subset=["future_day"])
    examples["future_exit_net_eur"] = _future_exit_value(examples, config.trade_direction)
    examples["future_cash_value_eur"] = _future_cash_value(examples, config.trade_direction)
    examples["future_profit_eur"] = examples["future_exit_net_eur"] - examples["buy_price_eur"]
    examples["future_cash_profit_eur"] = (
        examples["future_cash_value_eur"] - examples["buy_price_eur"]
    )
    examples["future_return"] = examples.apply(
        lambda row: float(
            return_ratio(
                Decimal(str(row["future_profit_eur"])),
                Decimal(str(row["buy_price_eur"])),
            )
        ),
        axis=1,
    )
    examples["future_cash_return"] = _safe_ratio(
        examples["future_cash_profit_eur"],
        examples["buy_price_eur"],
    )
    examples[TRADING_TARGET_COLUMN] = (
        (examples["future_profit_eur"] >= float(config.min_profit_eur))
        & (examples["future_return"] >= float(config.min_return))
    ).astype(int)
    return examples.sort_values(["item_id", TRADING_DATE_COLUMN]).reset_index(drop=True)


def _daily_metrics(history: pd.DataFrame) -> pd.DataFrame:
    frame = history.copy()
    # El archivo histórico mezcla marcas ISO con y sin microsegundos. Pedir el
    # formato mixto evita que una variante válida descarte todo el conjunto.
    frame["observed_at"] = pd.to_datetime(frame["observed_at"], utc=True, format="mixed")
    frame[TRADING_DATE_COLUMN] = frame["observed_at"].dt.floor("D").dt.tz_localize(None)
    frame["metric_value_numeric"] = pd.to_numeric(frame["metric_value"], errors="coerce")
    frame["price_eur_numeric"] = pd.to_numeric(frame["price_eur"], errors="coerce")
    frame["value"] = frame["price_eur_numeric"].where(
        frame["price_eur_numeric"].notna(),
        frame["metric_value_numeric"],
    )
    index_columns = [
        "item_id",
        "representation_name",
        "name",
        "quality",
        "stattrak",
        TRADING_DATE_COLUMN,
    ]
    grouped = (
        frame.sort_values("observed_at")
        .groupby([*index_columns, "platform_id", "metric_name"], dropna=False)["value"]
        .last()
        .reset_index()
    )
    pivot = grouped.pivot_table(
        index=index_columns,
        columns=["platform_id", "metric_name"],
        values="value",
        aggfunc="last",
    )
    pivot.columns = [_metric_column(platform, metric) for platform, metric in pivot.columns]
    return pivot.reset_index()


def _economics_config(config: TradingDatasetBuildConfig) -> MarketEconomicsConfig:
    default_config = default_excel_economics_config(
        cny_per_eur=config.cny_per_eur,
        trade_hold_days=config.horizon_days,
    )
    return MarketEconomicsConfig(
        cny_per_eur=config.cny_per_eur,
        trade_hold_days=config.horizon_days,
        sale_fee_factors={
            STEAM: config.steam_sale_factor,
            BUFF: config.buff_sale_factor,
        },
        steam_cashout_loss=config.steam_cashout_loss,
        steam_cashout_loss_scenarios=default_config.steam_cashout_loss_scenarios,
    )


def _required_price_columns(trade_direction: str) -> list[str]:
    if trade_direction == "buff_to_steam_sell":
        return ["steam_sell_price_eur", "buff_sell_price_eur"]
    if trade_direction == "steam_to_buff_buy_order":
        return ["steam_sell_price_eur", "buff_buy_order_price_eur"]
    raise ValueError(f"unknown trade_direction: {trade_direction}")


def _buy_price(frame: pd.DataFrame, trade_direction: str) -> pd.Series:
    if trade_direction == "buff_to_steam_sell":
        return frame["buff_sell_price_eur"]
    if trade_direction == "steam_to_buff_buy_order":
        return frame["steam_sell_price_eur"]
    raise ValueError(f"unknown trade_direction: {trade_direction}")


def _current_exit_value(frame: pd.DataFrame, trade_direction: str) -> pd.Series:
    if trade_direction == "buff_to_steam_sell":
        return frame["steam_net_sale_eur"]
    if trade_direction == "steam_to_buff_buy_order":
        return frame["buff_buy_order_net_sale_eur"]
    raise ValueError(f"unknown trade_direction: {trade_direction}")


def _current_cash_value(frame: pd.DataFrame, trade_direction: str) -> pd.Series:
    if trade_direction == "buff_to_steam_sell":
        return frame["steam_cash_value_eur"]
    if trade_direction == "steam_to_buff_buy_order":
        return frame["buff_buy_order_net_sale_eur"]
    raise ValueError(f"unknown trade_direction: {trade_direction}")


def _future_exit_value(frame: pd.DataFrame, trade_direction: str) -> pd.Series:
    if trade_direction == "buff_to_steam_sell":
        return frame["future_steam_net_sale_eur"]
    if trade_direction == "steam_to_buff_buy_order":
        return frame["future_buff_buy_order_net_sale_eur"]
    raise ValueError(f"unknown trade_direction: {trade_direction}")


def _future_cash_value(frame: pd.DataFrame, trade_direction: str) -> pd.Series:
    if trade_direction == "buff_to_steam_sell":
        return frame["future_steam_cash_value_eur"]
    if trade_direction == "steam_to_buff_buy_order":
        return frame["future_buff_buy_order_net_sale_eur"]
    raise ValueError(f"unknown trade_direction: {trade_direction}")


def _route_columns(trade_direction: str) -> dict[str, str]:
    if trade_direction == "buff_to_steam_sell":
        return {
            "buy_platform": BUFF,
            "buy_price_type": "listing",
            "sell_platform": STEAM,
            "sell_price_type": "listing",
            "cash_destination": "reinvest",
        }
    if trade_direction == "steam_to_buff_buy_order":
        return {
            "buy_platform": STEAM,
            "buy_price_type": "listing",
            "sell_platform": BUFF,
            "sell_price_type": "buy_order",
            "cash_destination": "reinvest",
        }
    raise ValueError(f"unknown trade_direction: {trade_direction}")


def _metric_column(platform: str, metric: str) -> str:
    if platform == "steam" and metric == "sell_price":
        return "steam_sell_price_eur"
    if platform == "steam" and metric == "sales_count":
        return "steam_sales_count"
    if platform == "buff" and metric == "sell_price":
        return "buff_sell_price_eur"
    if platform == "buff" and metric == "buy_order_price":
        return "buff_buy_order_price_eur"
    if platform == "buff" and metric == "listing_count":
        return "buff_listing_count"
    return f"{platform}_{metric}"


def _ensure_metric_columns(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for column in (
        "steam_sell_price_eur",
        "steam_sales_count",
        "buff_sell_price_eur",
        "buff_buy_order_price_eur",
        "buff_listing_count",
    ):
        if column not in result:
            result[column] = np.nan
    return result


def _add_time_features(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    dates = pd.to_datetime(result[TRADING_DATE_COLUMN])
    result["day_of_week"] = dates.dt.dayofweek
    result["month"] = dates.dt.month
    result["is_weekend"] = dates.dt.dayofweek.isin((5, 6)).astype(int)
    return result


def _add_lag_features(
    frame: pd.DataFrame,
    *,
    columns: tuple[str, ...],
) -> pd.DataFrame:
    result = frame.sort_values(["item_id", TRADING_DATE_COLUMN]).copy()
    groups = result.groupby("item_id", sort=False)
    for column in columns:
        if column not in result:
            continue
        series = pd.to_numeric(result[column], errors="coerce")
        grouped = series.groupby(result["item_id"], sort=False)
        for days in (1, 3, 7):
            lag = grouped.shift(days)
            result[f"{column}_lag_{days}d"] = lag
            result[f"{column}_change_{days}d"] = series - lag
            result[f"{column}_return_{days}d"] = _safe_ratio(series - lag, lag)
        result[f"{column}_rolling_mean_7d"] = groups[column].transform(
            lambda values: pd.to_numeric(values, errors="coerce")
            .shift(1)
            .rolling(7, min_periods=2)
            .mean()
        )
        result[f"{column}_rolling_std_7d"] = groups[column].transform(
            lambda values: pd.to_numeric(values, errors="coerce")
            .shift(1)
            .rolling(7, min_periods=2)
            .std()
        )
    return result


def _empty_trading_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=(*TRADING_TRACE_COLUMNS, TRADING_TARGET_COLUMN))


def _safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    return numerator.divide(denominator.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan)


def _split_frames(
    frame: pd.DataFrame,
    *,
    config: TradingDatasetBuildConfig,
) -> dict[str, pd.DataFrame]:
    dates = pd.to_datetime(frame[TRADING_DATE_COLUMN])
    train_end = pd.Timestamp((config.validation_start - timedelta(days=config.purge_gap_days)).date())
    validation_end = pd.Timestamp((config.test_start - timedelta(days=config.purge_gap_days)).date())
    test_mask = dates >= pd.Timestamp(config.test_start.date())
    if config.test_end is not None:
        test_mask &= dates < pd.Timestamp(config.test_end.date())
    return {
        "train": frame[dates < train_end],
        "validation": frame[
            (dates >= pd.Timestamp(config.validation_start.date()))
            & (dates < validation_end)
        ],
        "test": frame[test_mask],
    }


def _split_stats(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {
            "rows": 0,
            "items": 0,
            "target_rate": None,
            "min_date": None,
            "max_date": None,
        }
    return {
        "rows": int(len(frame)),
        "items": int(frame["item_id"].nunique()),
        "target_rate": float(frame[TRADING_TARGET_COLUMN].mean()),
        "min_date": pd.to_datetime(frame[TRADING_DATE_COLUMN]).min().isoformat(),
        "max_date": pd.to_datetime(frame[TRADING_DATE_COLUMN]).max().isoformat(),
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(_jsonable(payload), indent=2, sort_keys=True), encoding="utf-8")


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value
