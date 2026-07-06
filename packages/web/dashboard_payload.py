"""Build the static dashboard JSON consumed by apps/web."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from packages.prediction.supervised_service import DEFAULT_SUPERVISED_MODEL_DIR
from packages.simulation import STEAM, PortfolioRiskConfig
from packages.simulation.economics import default_excel_economics_config, net_sale_value_eur


def build_dashboard_payload(
    market_rows: Sequence[Mapping[str, Any]],
    *,
    risk_config: PortfolioRiskConfig,
    generated_at: datetime | None = None,
    backlog_root: Path = Path("backlog"),
    model_dir: Path = DEFAULT_SUPERVISED_MODEL_DIR,
) -> dict[str, Any]:
    recommendations = [_recommendation(row) for row in market_rows]
    return {
        "generated_at": _datetime_text(generated_at or datetime.now(tz=UTC)),
        "pipeline": _pipeline(model_dir),
        "summary": _summary(recommendations),
        "recommendations": recommendations,
        "agents": _agents(),
        "risk": _risk(risk_config),
        "backlog": _backlog(backlog_root),
    }


def market_items_query() -> str:
    return """
        with latest_signals as (
            select distinct on (item_id)
                item_id,
                scored_at as signal_scored_at,
                model_name as signal_model_name,
                model_version as signal_model_version,
                route_label as signal_route_label,
                buy_platform as signal_buy_platform,
                buy_price_type as signal_buy_price_type,
                sell_platform as signal_sell_platform,
                sell_price_type as signal_sell_price_type,
                buy_price_eur as signal_buy_price_eur,
                exit_value_eur as signal_exit_value_eur,
                expected_profit_eur as signal_expected_profit_eur,
                expected_return as signal_expected_return,
                probability_profitable as signal_probability_profitable,
                decision_threshold as signal_decision_threshold,
                is_signal as signal_is_signal,
                status as signal_status,
                reason as signal_reason,
                data_quality_status as signal_data_quality_status
            from market_opportunity_signals
            order by item_id, scored_at desc
        )
        select
            i.id,
            i.name,
            i.quality,
            i.stattrak,
            i.representation_name,
            i.steam_url,
            i.buff_url,
            i.scraped_at,
            i.steam_price,
            i.steam_currency,
            i.steam_price_eur,
            i.steam_price_cny,
            i.buff_price,
            i.buff_currency,
            i.buff_price_eur,
            i.buff_price_cny,
            latest_signals.*
        from market_items i
        left join latest_signals
          on latest_signals.item_id = i.id
         and latest_signals.signal_scored_at >= coalesce(
             i.last_checked_at,
             i.scraped_at,
             i.updated_at,
             i.created_at
         )
        where i.steam_price_eur is not null
          and i.buff_price_eur is not null
        order by
            greatest(
                coalesce(latest_signals.signal_scored_at, '-infinity'::timestamptz),
                coalesce(i.last_checked_at, '-infinity'::timestamptz),
                coalesce(i.scraped_at, '-infinity'::timestamptz),
                coalesce(i.updated_at, '-infinity'::timestamptz),
                coalesce(i.created_at, '-infinity'::timestamptz)
            ) desc,
            i.scraped_at desc nulls last,
            i.updated_at desc nulls last,
            i.created_at desc
        limit $1
    """


def _pipeline(model_dir: Path) -> list[list[str]]:
    model_state = "Modelo versionado" if model_dir.exists() else "Modelo no encontrado"
    return [
        ["Scraping", "Semanal listo, logs compactos"],
        ["Persistencia", "Historial incremental en market_history_points"],
        ["Modelo", f"{model_state}, uso experimental"],
        ["MARL", "RLlib smoke listo, critico central pendiente"],
    ]


def _recommendation(row: Mapping[str, Any]) -> dict[str, Any]:
    steam_eur = _optional_decimal(row.get("steam_price_eur"))
    buff_eur = _optional_decimal(row.get("buff_price_eur"))
    signal_profit = _optional_decimal(row.get("signal_expected_profit_eur"))
    profit = signal_profit if signal_profit is not None else _current_buff_to_steam_profit(
        steam_eur,
        buff_eur,
    )
    status = str(row.get("signal_status") or _status(steam_eur, buff_eur, profit))
    route = _route(status, row)
    model_text = _model_text(row, status)
    if status == "blocked":
        model_text = "Datos insuficientes para decision"
    return {
        "name": str(row.get("name") or "Sin nombre"),
        "quality": str(row.get("quality") or "Sin calidad"),
        "stattrak": bool(row.get("stattrak")),
        "status": status,
        "route": route["route"],
        "routeDetail": route["detail"],
        "buySide": route["buy_side"],
        "sellSide": route["sell_side"],
        "steam": _price_text(row.get("steam_price"), row.get("steam_currency")),
        "buff": _price_text(row.get("buff_price"), row.get("buff_currency")),
        "steamEur": _optional_float(steam_eur),
        "buffEur": _optional_float(buff_eur),
        "profitEur": _optional_float(profit),
        "profit": _profit_text(profit),
        "scrapedAt": _optional_datetime_text(row.get("signal_scored_at") or row.get("scraped_at")),
        "model": model_text,
        "agents": _agent_text(status, profit),
        "steamUrl": str(row.get("steam_url") or "https://steamcommunity.com/market/"),
        "buffUrl": str(row.get("buff_url") or "https://buff.163.com/market/csgo"),
    }


def _current_buff_to_steam_profit(
    steam_price_eur: Decimal | None,
    buff_price_eur: Decimal | None,
) -> Decimal | None:
    if steam_price_eur is None or buff_price_eur is None:
        return None
    config = default_excel_economics_config()
    steam_net = net_sale_value_eur(
        steam_price_eur,
        sale_platform=STEAM,
        sale_currency="EUR",
        config=config,
    )
    return steam_net - buff_price_eur


def _status(
    steam_price_eur: Decimal | None,
    buff_price_eur: Decimal | None,
    profit_eur: Decimal | None,
) -> str:
    if steam_price_eur is None or buff_price_eur is None or profit_eur is None:
        return "blocked"
    if profit_eur > Decimal("0"):
        return "review"
    return "observe"


def _route(status: str, row: Mapping[str, Any] | None = None) -> dict[str, str]:
    if row and row.get("signal_route_label"):
        buy_side = _side_label(row.get("signal_buy_platform"), row.get("signal_buy_price_type"))
        sell_side = _side_label(row.get("signal_sell_platform"), row.get("signal_sell_price_type"))
        reason = str(row.get("signal_reason") or "Ruta evaluada por el scorer")
        return {
            "route": str(row.get("signal_route_label")),
            "detail": reason,
            "buy_side": buy_side,
            "sell_side": sell_side,
        }
    if status == "blocked":
        return {
            "route": "Ruta incompleta",
            "detail": "Faltan precios para calcular",
            "buy_side": "BUFF listing",
            "sell_side": "Steam listing",
        }
    return {
        "route": "BUFF listing -> Steam listing",
        "detail": "Compra BUFF, venta Steam neta",
        "buy_side": "BUFF listing",
        "sell_side": "Steam listing",
    }


def _side_label(platform: Any, price_type: Any) -> str:
    platform_text = str(platform or "").strip() or "Mercado"
    price_text = str(price_type or "").strip() or "precio"
    return f"{platform_text} {price_text}"


def _model_text(row: Mapping[str, Any], status: str) -> str:
    model_name = str(row.get("signal_model_name") or "").strip()
    model_version = str(row.get("signal_model_version") or "").strip()
    probability = _optional_decimal(row.get("signal_probability_profitable"))
    if model_name:
        suffix = f" p={_money(probability)}" if probability is not None else ""
        return f"{model_name} {model_version}{suffix}".strip()
    if status == "blocked":
        return "Datos insuficientes para decision"
    return "Experimental, validar"


def _agent_text(status: str, profit_eur: Decimal | None) -> str:
    if status == "blocked":
        return "Portfolio: bloquea por datos insuficientes"
    if profit_eur is None:
        return "Scout: pendiente, Trader: pendiente, Portfolio: revisar"
    return f"Scout: revisar, Trader: esperar, Portfolio: profit actual {_money(profit_eur)} EUR"


def _summary(recommendations: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return {
        "total": len(recommendations),
        "review": sum(1 for item in recommendations if item.get("status") == "review"),
        "observe": sum(1 for item in recommendations if item.get("status") == "observe"),
        "blocked": sum(1 for item in recommendations if item.get("status") == "blocked"),
    }


def _risk(config: PortfolioRiskConfig) -> list[list[str]]:
    return [
        ["Max posicion", _percent(config.max_position_fraction)],
        ["Max articulo", _percent(config.max_item_fraction)],
        ["Max plataforma", _percent(config.max_platform_fraction)],
        ["Capital bloqueado", _percent(config.max_blocked_fraction)],
        ["Caja minima", _percent(config.min_cash_fraction)],
        ["Liquidez minima", f"{config.min_liquidity_quantity} unidad"],
    ]


def _agents() -> list[list[str]]:
    return [
        ["Scout", "Activo en entorno minimo", "Marca oportunidad o ignora"],
        ["Trader", "Activo en entorno minimo", "Compra uno o mantiene"],
        ["Portfolio", "Riesgo conectado", "Aprueba o rechaza por limites"],
    ]


def _backlog(root: Path) -> list[list[str]]:
    entries: list[list[str]] = []
    for directory, state in (
        (root / "1 progreso", "En progreso"),
        (root / "2 realizadas", "Realizada"),
    ):
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.md")):
            task_id = path.name.split("-", 1)[0]
            title = path.stem.split("-", 1)[1].replace("-", " ") if "-" in path.stem else path.stem
            entries.append([task_id, title.capitalize(), state])
    return entries


def _price_text(value: Any, currency: Any) -> str:
    amount = _optional_decimal(value)
    if amount is None:
        return "Pendiente"
    return f"{str(currency or '').strip() or 'EUR'} {_money(amount)}"


def _profit_text(value: Decimal | None) -> str:
    if value is None:
        return "Sin datos"
    return f"{_money(value)} EUR"


def _optional_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return Decimal(text)


def _optional_float(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


def _optional_datetime_text(value: Any) -> str:
    if isinstance(value, datetime):
        return _datetime_text(value)
    if value is None:
        return "Sin fecha"
    text = str(value).strip()
    return text or "Sin fecha"


def _money(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01")), "f")


def _percent(value: Decimal) -> str:
    return f"{_money(value * Decimal('100'))}%"


def _datetime_text(value: datetime) -> str:
    return (value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)).isoformat()
