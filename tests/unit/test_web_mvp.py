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
    assert 'href="#scraper"' in html
    assert 'id="scrape-start-button"' in html
    assert 'id="scrape-command"' in html
    assert 'class="deal-list"' in html
    assert 'id="deal-detail"' in html
    assert 'href="#model"' in html
    assert "Crear web de recomendaciones" not in html
    assert "gradient" not in css.lower()
    assert "purple" not in css.lower()
    assert 'get("data")' in js
    assert 'readDashboardJson("./api/dashboard")' in js
    assert "readDashboardJson(`./data/${dataFile}`)" in js
    assert "XMLHttpRequest" in js
    assert "fallbackDashboard" in js
    assert "compareRecommendations" in js
    assert "renderSummary" in js
    assert "formatRouteDetail" in js
    assert "renderDealDetail" in js
    assert "data-deal-index" in js
    assert "startScrape" in js
    assert "./api/scrape/start" in js
    assert "./api/scrape/status" in js
    assert "RLlib smoke listo" in js
    assert "BUFF listing -> Steam listing" in js
    assert "trading_profit_v1" in js
    assert "buff/sell_price historico escaso" in js
