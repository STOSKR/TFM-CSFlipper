import pytest

from apps.acquisition.steamdt_ui import click_tab_by_text, current_option_description


@pytest.mark.asyncio
async def test_click_tab_by_text_uses_exact_normalized_label() -> None:
    page = FakeSteamDTPage()

    await click_tab_by_text(page, "STEAM Balance")

    assert page.clicked_label == "STEAM Balance"


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
        ]
        self.clicked_label = next((label for label in candidates if label in labels), None)
        return self.clicked_label is not None

    async def wait_for_timeout(self, _milliseconds: int) -> None:
        return None
