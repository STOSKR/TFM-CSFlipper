import pytest

from apps.acquisition.steamdt_ui import (
    change_currency,
    click_tab_by_text,
    current_option_description,
)


@pytest.mark.asyncio
async def test_click_tab_by_text_uses_exact_normalized_label() -> None:
    page = FakeSteamDTPage()

    await click_tab_by_text(page, "STEAM Balance")

    assert page.clicked_label == "STEAM Balance"


@pytest.mark.asyncio
async def test_click_tab_by_text_supports_platform_buy_order_label() -> None:
    page = FakeSteamDTPage()

    await click_tab_by_text(page, "Buy via Platform Buy Order")

    assert page.clicked_label == "Buy via PlatformPlace Buy Order"


@pytest.mark.asyncio
async def test_click_tab_by_text_reports_missing_option() -> None:
    page = FakeSteamDTPage()

    with pytest.raises(RuntimeError, match="SteamDT option not found"):
        await click_tab_by_text(page, "Sell at STEAM Lowest Price")


@pytest.mark.asyncio
async def test_change_currency_skips_dropdown_when_currency_already_selected() -> None:
    page = FakeCurrencyPage("EUR")

    await change_currency(page, "EUR")

    assert page.locator_used is False


@pytest.mark.asyncio
async def test_current_option_description_extracts_summary() -> None:
    page = FakeSteamDTPage(
        body_text=(
            "Current Option Description: FromSteam MarketPlace Buy Order, "
            "ToPlatformSell at Lowest Price for Platform Balance Name Platform Lowest"
        )
    )

    assert await current_option_description(page) == (
        "FromSteam MarketPlace Buy Order, ToPlatformSell at Lowest Price for Platform Balance"
    )


class FakeSteamDTPage:
    def __init__(self, body_text: str = "") -> None:
        self.body_text = body_text
        self.clicked_label: str | None = None

    async def evaluate(self, script: str, labels: list[str] | None = None) -> object:
        if labels is None:
            marker = "Current Option Description:"
            index = self.body_text.find(marker)
            if index < 0:
                return ""
            rest = self.body_text[index + len(marker) :].strip()
            next_section = rest.find("Name")
            return rest[:next_section].strip() if next_section >= 0 else rest
        candidates = [
            "Platform Balance",
            "Buy at STEAM Lowest Price",
            "STEAM Balance",
            "Buy via PlatformPlace Buy Order",
        ]
        self.clicked_label = next((label for label in candidates if label in labels), None)
        return self.clicked_label is not None

    async def wait_for_timeout(self, _milliseconds: int) -> None:
        return None


class FakeCurrencyPage:
    def __init__(self, current_currency: str) -> None:
        self.current_currency = current_currency
        self.locator_used = False

    async def evaluate(self, _script: str, currency: str) -> bool:
        return self.current_currency == currency

    def locator(self, _selector: str) -> object:
        self.locator_used = True
        raise AssertionError("locator should not be used")
