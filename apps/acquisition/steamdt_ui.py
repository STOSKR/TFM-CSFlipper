"""Playwright helpers for SteamDT filters."""

from __future__ import annotations

from decimal import Decimal
from typing import Any


async def close_modal(page: Any) -> None:
    close_selectors = (
        ".el-dialog__headerbtn",
        'button[aria-label="Close"]',
        'button:has-text("\\u6211\\u5df2\\u77e5\\u6653")',
        'button:has-text("\\u6211\\u77e5\\u9053\\u4e86")',
        'button:has-text("\\u540c\\u610f")',
        'button:has-text("I understand")',
        'button:has-text("OK")',
        ".el-overlay-dialog .el-button",
    )
    for _ in range(2):
        clicked = False
        for selector in close_selectors:
            locator = page.locator(selector)
            try:
                count = min(await locator.count(), 3)
            except Exception:
                continue
            for index in range(count):
                element = locator.nth(index)
                try:
                    visible = await element.is_visible(timeout=500)
                    if not visible:
                        continue
                    await element.click(force=True, timeout=1000)
                    await page.wait_for_timeout(250)
                    clicked = True
                except Exception:
                    continue
        if not clicked:
            return


async def change_currency(page: Any, currency_code: str) -> None:
    if not currency_code:
        return
    current = await page.evaluate(
        """
        (currency) => {
          const clean = (value) => String(value || "").replace(/\\s+/g, " ").trim();
          const nodes = Array.from(document.querySelectorAll(".el-dropdown-link"));
          return nodes.some((node) => clean(node.innerText || node.textContent) === currency);
        }
        """,
        currency_code,
    )
    if current:
        return
    for selector in (".el-dropdown-link", "[class*='currency']", "[class*='dropdown']"):
        locator = page.locator(selector)
        try:
            count = await locator.count()
        except Exception:
            continue
        if count == 0:
            continue
        try:
            await locator.first.click(force=True)
        except Exception:
            continue
        await page.wait_for_timeout(500)
        option = page.locator(f'li:has-text("{currency_code}")')
        if await option.count() > 0:
            await option.first.click(force=True)
            await page.wait_for_timeout(1500)
            return
        await page.keyboard.press("Escape")


async def click_tab_by_text(page: Any, text: str | None) -> None:
    if await try_click_tab_by_text(page, text):
        return
    raise RuntimeError(f"SteamDT option not found: {text}")


async def try_click_tab_by_text(page: Any, text: str | None) -> bool:
    if not text:
        return True
    labels = localized_tab_labels(text)
    clicked = await page.evaluate(
        """
        (labels) => {
          const clean = (value) => String(value || "").replace(/\\s+/g, " ").trim();
          const wanted = new Set(labels.map(clean));
          const nodes = Array.from(
            document.querySelectorAll(".tabs-item, [role='tab'], button")
          );
          const target = nodes.find((node) =>
            wanted.has(clean(node.innerText || node.textContent))
          );
          if (!target) {
            return false;
          }
          target.scrollIntoView({ block: "center", inline: "center" });
          target.click();
          return true;
        }
        """,
        list(labels),
    )
    if clicked:
        await page.wait_for_timeout(700)
        return True
    return False


async def current_option_description(page: Any) -> str:
    return str(
        await page.evaluate(
            """
            () => {
              const clean = (value) => String(value || "").replace(/\\s+/g, " ").trim();
              const body = clean(document.body && document.body.innerText);
              const marker = "Current Option Description:";
              const index = body.indexOf(marker);
              if (index < 0) {
                return "";
              }
              const rest = body.slice(index + marker.length).trim();
              const nextSection = rest.search(
                /\\b(Name|Platform Lowest|Steam Lowest|Net Platform)\\b/
              );
              return clean(nextSection >= 0 ? rest.slice(0, nextSection) : rest);
            }
            """
        )
        or ""
    )


async def fill_price_volume_filters(
    page: Any,
    *,
    min_price: Decimal | None,
    max_price: Decimal | None,
    min_volume: int | None,
) -> None:
    inputs = await page.locator(".el-input__inner:not(#searchInput)").all()
    values = [min_price, max_price, min_volume]
    for index, value in enumerate(values):
        if value is None or index >= len(inputs):
            continue
        await inputs[index].fill(str(value), force=True)
        await page.wait_for_timeout(150)


async def configure_platforms(
    page: Any,
    *,
    platform_buff: bool,
    platform_c5game: bool,
    platform_uu: bool,
) -> None:
    settings = page.locator('.text-blue:has-text("Platform Settings")')
    if await settings.count() > 0:
        await settings.first.click()
        await page.wait_for_timeout(500)
    for label, enabled in (
        ("C5GAME", platform_c5game),
        ("UU", platform_uu),
        ("BUFF", platform_buff),
    ):
        checkbox = page.locator(f'.el-checkbox:has-text("{label}")')
        if await checkbox.count() == 0:
            continue
        input_box = checkbox.first.locator('input[type="checkbox"]')
        if await input_box.count() == 0:
            continue
        checked = await input_box.first.is_checked()
        if checked != enabled:
            await checkbox.first.click(force=True)
            await page.wait_for_timeout(150)


async def click_confirm_search(page: Any) -> None:
    for selector in (
        '.bg-\\[\\#0252D9\\]:has-text("Confirm and Search")',
        'button:has-text("Confirm and Search")',
        'button:has-text("Search")',
        'text="\\u786e\\u5b9a\\u5e76\\u641c\\u7d22"',
    ):
        locator = page.locator(selector)
        if await locator.count() > 0:
            await locator.first.click(force=True)
            return


def localized_tab_labels(text: str) -> tuple[str, ...]:
    labels = {
        "STEAM Balance": ("STEAM Balance", "\u0053\u0054\u0045\u0041\u004d\u4f59\u989d"),
        "Platform Balance": ("Platform Balance", "\u5e73\u53f0\u4f59\u989d"),
        "Sell at STEAM Lowest Price": (
            "Sell at STEAM Lowest Price",
            "\u0053\u0054\u0045\u0041\u004d\u6302\u5e95\u4ef7",
        ),
        "Sell to STEAM Highest Buy Order": (
            "Sell to STEAM Highest Buy Order",
            "\u0053\u0054\u0045\u0041\u004d\u4e22\u6c42\u8d2d",
        ),
        "Sell at Platform Lowest Price": (
            "Sell at Platform Lowest Price",
            "\u5e73\u53f0\u6302\u5e95\u4ef7",
        ),
        "Sell to Platform Highest Buy Order": (
            "Sell to Platform Highest Buy Order",
            "\u5e73\u53f0\u4e22\u6c42\u8d2d",
        ),
        "Buy via STEAM Buy Order": (
            "Buy via STEAM Buy Order",
            "\u0053\u0054\u0045\u0041\u004d\u6c42\u8d2d",
        ),
        "Buy at STEAM Lowest Price": (
            "Buy at STEAM Lowest Price",
            "\u0053\u0054\u0045\u0041\u004d\u5e95\u4ef7",
        ),
        "Buy via Platform Buy Order": (
            "Buy via Platform Buy Order",
            "Buy via PlatformPlace Buy Order",
            "Buy via Platform Place Buy Order",
            "PlatformPlace Buy Order",
            "Platform Place Buy Order",
        ),
        "Buy at Platform Lowest Price": (
            "Buy at Platform Lowest Price",
            "Platform Lowest Price",
        ),
    }
    return labels.get(text, (text,))
