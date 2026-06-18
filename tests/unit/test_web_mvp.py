from pathlib import Path

WEB_DIR = Path("apps/web")


def test_web_mvp_static_files_are_wired() -> None:
    html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    css = (WEB_DIR / "styles.css").read_text(encoding="utf-8")
    js = (WEB_DIR / "app.js").read_text(encoding="utf-8")

    assert 'href="./styles.css"' in html
    assert 'src="./app.js"' in html
    assert 'src="./assets/ledger-mark.svg"' in html
    assert 'id="sort-select"' in html
    assert 'id="recommendation-summary"' in html
    assert "<th>Ruta</th>" in html
    assert "Crear web de recomendaciones" not in html
    assert "gradient" not in css.lower()
    assert "purple" not in css.lower()
    assert 'get("data")' in js
    assert "readDashboardJson(`./data/${dataFile}`)" in js
    assert "XMLHttpRequest" in js
    assert "fallbackDashboard" in js
    assert "compareRecommendations" in js
    assert "renderSummary" in js
    assert "formatRouteDetail" in js
    assert "RLlib smoke listo" in js
    assert "BUFF listing -> Steam listing" in js
    assert "trading_profit_v1" in js
    assert "buff/sell_price falta" in js
