from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from packages.simulation import PortfolioRiskConfig
from packages.web import build_dashboard_payload, market_items_query


def test_build_dashboard_payload_marks_profitable_current_spread_as_review(tmp_path: Path) -> None:
    payload = build_dashboard_payload(
        (
            {
                "name": "AK-47 | Slate",
                "quality": "Field-Tested",
                "stattrak": False,
                "scraped_at": datetime(2026, 6, 16, 10, 30, tzinfo=UTC),
                "steam_price": Decimal("20"),
                "steam_currency": "EUR",
                "steam_price_eur": Decimal("20"),
                "buff_price": Decimal("120"),
                "buff_currency": "CNY",
                "buff_price_eur": Decimal("15"),
                "steam_url": "https://steamcommunity.com/market/listings/730/AK",
                "buff_url": "https://buff.163.com/goods/1",
            },
        ),
        risk_config=PortfolioRiskConfig(),
        generated_at=datetime(2026, 6, 16, 12, 0, tzinfo=UTC),
        backlog_root=tmp_path,
        model_dir=tmp_path / "missing-model",
    )

    item = payload["recommendations"][0]
    assert item["status"] == "review"
    assert item["route"] == "BUFF listing -> Steam listing"
    assert item["routeDetail"] == "Compra BUFF, venta Steam neta"
    assert item["buySide"] == "BUFF listing"
    assert item["sellSide"] == "Steam listing"
    assert item["steam"] == "EUR 20.00"
    assert item["buff"] == "CNY 120.00"
    assert item["profit"] == "2.40 EUR"
    assert item["profitEur"] == 2.4
    assert item["scrapedAt"] == "2026-06-16T10:30:00+00:00"
    assert "profit actual 2.40 EUR" in item["agents"]
    assert payload["summary"] == {"total": 1, "review": 1, "observe": 0, "blocked": 0}
    assert payload["pipeline"][2] == ["Modelo", "Modelo no encontrado, uso experimental"]


def test_build_dashboard_payload_blocks_items_with_missing_prices(tmp_path: Path) -> None:
    payload = build_dashboard_payload(
        (
            {
                "name": "MP9 | Starlight Protector",
                "quality": "Minimal Wear",
                "stattrak": False,
                "steam_price": None,
                "steam_currency": None,
                "steam_price_eur": None,
                "buff_price": Decimal("180"),
                "buff_currency": "CNY",
                "buff_price_eur": Decimal("22.5"),
            },
        ),
        risk_config=PortfolioRiskConfig(min_liquidity_quantity=3),
        backlog_root=tmp_path,
    )

    item = payload["recommendations"][0]
    assert item["status"] == "blocked"
    assert item["route"] == "Ruta incompleta"
    assert item["routeDetail"] == "Faltan precios para calcular"
    assert item["model"] == "Datos insuficientes para decision"
    assert item["steam"] == "Pendiente"
    assert item["profit"] == "Sin datos"
    assert item["profitEur"] is None
    assert item["scrapedAt"] == "Sin fecha"
    assert payload["summary"] == {"total": 1, "review": 0, "observe": 0, "blocked": 1}
    assert ["Liquidez minima", "3 unidad"] in payload["risk"]


def test_market_items_query_reads_price_derivative_columns() -> None:
    query = market_items_query()

    assert "steam_price_eur" in query
    assert "buff_price_eur" in query
    assert "signal_scored_at >= coalesce" in query
    assert "i.last_checked_at" in query
    assert "i.steam_price_eur is not null" in query
    assert "i.buff_price_eur is not null" in query
    assert "greatest(" in query
    assert "limit $1" in query.lower()
