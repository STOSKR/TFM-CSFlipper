from pathlib import Path

WEB_DIR = Path("apps/web")


def test_web_mvp_static_files_are_wired() -> None:
    html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    css = (WEB_DIR / "styles.css").read_text(encoding="utf-8")
    js = (WEB_DIR / "app.js").read_text(encoding="utf-8")

    assert 'href="./styles.css"' in html
    assert 'src="./app.js"' in html
    assert 'src="./assets/ledger-mark.svg"' in html
    assert "Crear web de recomendaciones" not in html
    assert "gradient" not in css.lower()
    assert "purple" not in css.lower()
    assert "trading_profit_v1" in js
    assert "buff/sell_price falta" in js
