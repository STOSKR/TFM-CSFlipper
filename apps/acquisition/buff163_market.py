"""BUFF163 browser scraper with verbose diagnostics."""

from __future__ import annotations

import asyncio
import json
import random
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from packages.contracts.observations import MarketObservationContract
from packages.domain.canonical_id import build_canonical_asset_id
from packages.domain.enums import SourceType
from packages.domain.market_parsing import (
    asset_name_from_market_hash,
    detect_currency,
    parse_market_decimal,
    parse_required_market_decimal,
    quality_from_market_hash,
    variant_key,
)

MONEY_PATTERN = re.compile(
    r"(?:CNY|USD|EUR|GBP|\$|\u20ac|\u00a3|\u00a5|\uffe5)\s*\d[\d.,]*"
    r"|\d[\d.,]*\s*(?:CNY|USD|EUR|GBP|\u20ac|\u00a3|\u00a5|\uffe5)",
    re.IGNORECASE,
)
LEADING_SYMBOL_MONEY_PATTERN = re.compile(r"(?:\$|\u20ac|\u00a3|\u00a5|\uffe5)\s*\d[\d.,]*")
BUFF_PRICE_SELECTORS = (
    ".detail-tab-cont .f_Strong",
    ".list_tb_csgo .f_Strong",
    ".market-card .f_Strong",
    ".selling .f_Strong",
    "[class*='price']",
)
LogCallback = Callable[[str], None]


class Buff163Error(RuntimeError):
    """Raised when BUFF163 cannot return a usable observation."""


@dataclass(frozen=True, slots=True)
class Buff163Candidate:
    market_hash_name: str
    buff_url: str
    asset_name: str | None = None
    quality: str | None = None
    stattrak: bool = False
    category: str | None = None


@dataclass(frozen=True, slots=True)
class Buff163Observation:
    observation: MarketObservationContract
    asset_name: str
    category: str | None
    quality: str | None
    variant_key: str


@dataclass(frozen=True, slots=True)
class Buff163CandidateError:
    candidate: Buff163Candidate
    message: str
    debug_log: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Buff163ConnectorConfig:
    headless: bool = True
    timeout_ms: int = 30000
    wait_after_load_ms: int = 2500
    manual_login_wait_ms: int = 0
    min_delay_seconds: float = 0.0
    max_delay_seconds: float = 0.0
    max_concurrency: int = 1
    session_state_path: Path | None = Path("data/browser-state/buff163_storage_state.json")


class Buff163Connector:
    """Playwright connector for BUFF163 item pages."""

    def __init__(
        self,
        config: Buff163ConnectorConfig | None = None,
        *,
        log: LogCallback | None = None,
    ) -> None:
        self._config = config or Buff163ConnectorConfig()
        self._log = log

    async def fetch_candidates(
        self,
        candidates: list[Buff163Candidate],
        *,
        correlation_id: str,
    ) -> tuple[Buff163Observation, ...]:
        observations, errors = await self.fetch_candidates_lenient(
            candidates,
            correlation_id=correlation_id,
        )
        if errors:
            first_error = errors[0]
            raise Buff163Error(
                f"BUFF request failed for {first_error.candidate.market_hash_name}: "
                f"{first_error.message}"
            )
        return observations

    async def fetch_candidates_lenient(
        self,
        candidates: list[Buff163Candidate],
        *,
        correlation_id: str,
    ) -> tuple[tuple[Buff163Observation, ...], tuple[Buff163CandidateError, ...]]:
        if not candidates:
            return (), ()

        try:
            from playwright.async_api import async_playwright
        except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
            raise Buff163Error(
                "Playwright is required. Run: python -m pip install playwright"
            ) from exc

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=self._config.headless)
            context_options: dict[str, Any] = {
                "viewport": {"width": 1920, "height": 1080},
                "user_agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123 Safari/537.36"
                ),
            }
            if self._config.session_state_path and self._config.session_state_path.exists():
                context_options["storage_state"] = str(self._config.session_state_path)
            context = await browser.new_context(**context_options)
            semaphore = asyncio.Semaphore(self._config.max_concurrency)

            async def fetch_one(
                candidate: Buff163Candidate,
            ) -> Buff163Observation | Buff163CandidateError:
                async with semaphore:
                    debug_log: list[str] = []
                    try:
                        return await self._fetch_one(
                            context,
                            candidate,
                            correlation_id=correlation_id,
                            debug_log=debug_log,
                        )
                    except Exception as exc:
                        self._emit(candidate.market_hash_name, f"ERROR {exc}")
                        return Buff163CandidateError(
                            candidate=candidate,
                            message=str(exc),
                            debug_log=tuple(debug_log),
                        )

            try:
                results = await asyncio.gather(*(fetch_one(candidate) for candidate in candidates))
            finally:
                await self._save_session_state(context)
                await context.close()
                await browser.close()

        observations = tuple(
            result for result in results if isinstance(result, Buff163Observation)
        )
        errors = tuple(
            result for result in results if isinstance(result, Buff163CandidateError)
        )
        return observations, errors

    async def _fetch_one(
        self,
        context: Any,
        candidate: Buff163Candidate,
        *,
        correlation_id: str,
        debug_log: list[str],
    ) -> Buff163Observation:
        await self._sleep_between_requests()
        self._debug(candidate.market_hash_name, debug_log, f"opening {candidate.buff_url}")
        page = await context.new_page()
        try:
            await page.goto(
                candidate.buff_url,
                wait_until="domcontentloaded",
                timeout=self._config.timeout_ms,
            )
            if self._config.manual_login_wait_ms > 0:
                self._debug(
                    candidate.market_hash_name,
                    debug_log,
                    f"waiting {self._config.manual_login_wait_ms}ms for manual login",
                )
                await page.wait_for_timeout(self._config.manual_login_wait_ms)
            await page.wait_for_timeout(self._config.wait_after_load_ms)
            payload = await page.evaluate(
                f"""
                async (goodsId) => {{
                  const fetchJson = async (path, params) => {{
                    if (!goodsId) {{
                      return {{ status: 0, text: "" }};
                    }}
                    const query = new URLSearchParams({{
                      game: "csgo",
                      goods_id: goodsId,
                      ...params
                    }});
                    const url = `${{path}}?${{query.toString()}}`;
                    try {{
                      const response = await fetch(url, {{
                        credentials: "include",
                        headers: {{ accept: "application/json, text/plain, */*" }}
                      }});
                      return {{
                        status: response.status,
                        text: await response.text()
                      }};
                    }} catch (error) {{
                      return {{
                        status: 0,
                        text: "",
                        error: String(error)
                      }};
                    }}
                  }};
                  return {{
                  url: location.href,
                  title: document.title,
                  bodyText: document.body ? document.body.innerText : "",
                  selectorTexts: {list(BUFF_PRICE_SELECTORS)!r}.flatMap((selector) =>
                    Array.from(document.querySelectorAll(selector)).map((el) => ({{
                      selector,
                      text: el.innerText
                    }}))
                  ),
                  buyOrderRows: Array.from(
                    document.querySelectorAll(
                      "tr, li, [class*='buy'], [class*='order'], [class*='demand']"
                    )
                  ).map((el) => ({{
                    tag: el.tagName,
                    className: el.className || "",
                    text: el.innerText || ""
                  }})),
                  apiPayloads: {{
                    buyOrder: await fetchJson("/api/market/goods/buy_order", {{ page_num: "1" }}),
                    billOrder: await fetchJson("/api/market/goods/bill_order", {{ page_num: "1" }}),
                    priceHistory: await fetchJson(
                      "/api/market/goods/price_history/buff/v2",
                      {{
                        currency: "EUR",
                        days: "365",
                        _: String(Date.now())
                      }}
                    )
                  }}
                  }};
                }}
                """,
                _buff_goods_id(candidate.buff_url),
            )
        finally:
            await page.close()

        title = str(payload.get("title") or "")
        body_text = str(payload.get("bodyText") or "")
        selector_texts = list(payload.get("selectorTexts") or [])
        buy_order_rows = list(payload.get("buyOrderRows") or [])
        api_payloads = (
            payload.get("apiPayloads") if isinstance(payload.get("apiPayloads"), dict) else {}
        )
        buy_order_payload = _json_payload(api_payloads.get("buyOrder"))
        bill_order_payload = _json_payload(api_payloads.get("billOrder"))
        price_history_payload = _json_payload(api_payloads.get("priceHistory"))
        self._debug(candidate.market_hash_name, debug_log, f"title={title!r}")
        self._debug(
            candidate.market_hash_name,
            debug_log,
            f"selector_matches={len(selector_texts)} body_chars={len(body_text)}",
        )

        price_text = extract_buff_price_text(selector_texts, body_text, debug_log=debug_log)
        if not price_text:
            excerpt = " ".join(body_text.split())[:300]
            self._debug(candidate.market_hash_name, debug_log, f"body_excerpt={excerpt!r}")
            raise Buff163Error(f"BUFF price not found for {candidate.market_hash_name}")
        self._debug(candidate.market_hash_name, debug_log, f"price_text={price_text!r}")

        asset_name = candidate.asset_name or asset_name_from_market_hash(candidate.market_hash_name)
        quality = candidate.quality or quality_from_market_hash(candidate.market_hash_name)
        stattrak = candidate.stattrak or candidate.market_hash_name.lower().startswith("stattrak")
        asset_id = build_canonical_asset_id(name=asset_name, quality=quality, stattrak=stattrak)
        currency = detect_currency(price_text, default="CNY") or "CNY"
        price_history = extract_buff_price_history(
            price_history_payload,
            display_currency="EUR",
        )
        observation = MarketObservationContract(
            correlation_id=correlation_id,
            asset_id=asset_id,
            platform_id="buff163",
            observed_at=datetime.now(tz=UTC),
            price=parse_required_market_decimal(price_text),
            currency=currency,
            source_type=SourceType.SCRAPING,
            source_reference=candidate.buff_url,
            raw_payload={
                "market_hash_name": candidate.market_hash_name,
                "buff_url": candidate.buff_url,
                "price_text": price_text,
                "buy_orders": extract_buff_api_buy_orders(
                    buy_order_payload,
                    display_currency=currency,
                )
                or extract_buff_buy_orders(
                    buy_order_rows,
                    body_text,
                    display_currency=currency,
                ),
                "recent_sales": extract_buff_recent_sales(bill_order_payload),
                "price_history": price_history,
                "page_title": title,
                "debug_log": tuple(debug_log),
            },
        )
        return Buff163Observation(
            observation=observation,
            asset_name=asset_name,
            category=candidate.category,
            quality=quality,
            variant_key=variant_key(quality, stattrak),
        )

    async def _save_session_state(self, context: Any) -> None:
        if not self._config.session_state_path:
            return
        self._config.session_state_path.parent.mkdir(parents=True, exist_ok=True)
        await context.storage_state(path=str(self._config.session_state_path))

    async def _sleep_between_requests(self) -> None:
        if self._config.max_delay_seconds <= 0:
            return
        delay = random.uniform(
            max(0.0, self._config.min_delay_seconds),
            max(self._config.min_delay_seconds, self._config.max_delay_seconds),
        )
        await asyncio.sleep(delay)

    def _debug(self, item: str, debug_log: list[str], message: str) -> None:
        debug_log.append(message)
        self._emit(item, message)

    def _emit(self, item: str, message: str) -> None:
        if self._log:
            self._log(f"[buff163] {item}: {message}")


def extract_buff_price_text(
    selector_texts_or_body: list[Any] | str,
    body_text: str | None = None,
    *,
    debug_log: list[str] | None = None,
) -> str | None:
    """Extract the first plausible money value from a BUFF item page."""

    if body_text is None:
        selector_texts: list[Any] = []
        body_text = str(selector_texts_or_body)
    else:
        selector_texts = (
            list(selector_texts_or_body)
            if isinstance(selector_texts_or_body, list)
            else []
        )

    for entry in selector_texts:
        text = str(entry.get("text") if isinstance(entry, dict) else entry)
        match = MONEY_PATTERN.search(text)
        if match:
            _append_debug(debug_log, f"price matched selector text={text!r}")
            return match.group(0)

    normalized_lines = [line.strip() for line in body_text.splitlines() if line.strip()]
    preferred_labels = (
        "sell",
        "selling",
        "lowest",
        "price",
        "\u51fa\u552e",
        "\u5728\u552e",
        "\u4ef7\u683c",
        "\u552e\u4ef7",
    )
    for line in normalized_lines:
        lowered = line.lower()
        if any(label in lowered for label in preferred_labels):
            match = MONEY_PATTERN.search(line)
            if match:
                _append_debug(debug_log, f"price matched fallback line={line!r}")
                return match.group(0)

    match = MONEY_PATTERN.search(body_text)
    if match:
        _append_debug(debug_log, "price matched raw body fallback")
    return match.group(0) if match else None


def extract_buff_buy_orders(
    rows: list[Any],
    body_text: str = "",
    *,
    display_currency: str | None = None,
) -> tuple[dict[str, str | int], ...]:
    buy_orders: dict[tuple[str, Decimal], dict[str, str | int]] = {}
    seen: set[tuple[str, int]] = set()
    for text in _buy_order_candidate_texts(rows, body_text):
        for price_text, price_end in _iter_money_candidates(text):
            currency = detect_currency(price_text, default="CNY") or "CNY"
            if display_currency and currency != display_currency.upper():
                continue
            price = parse_market_decimal(price_text)
            if price is None or not _is_plausible_buff_order_price(price_text, price):
                continue
            quantity = _first_int_after(text, price_end)
            if quantity is None:
                continue
            key = (price_text, quantity)
            if key in seen:
                continue
            seen.add(key)
            price_key = (currency, price)
            current = buy_orders.get(price_key)
            if current is None or quantity > int(current["quantity"]):
                buy_orders[price_key] = {"price": price_text, "quantity": quantity}
    return tuple(buy_orders.values())


def extract_buff_api_buy_orders(
    payload: object,
    *,
    display_currency: str | None = None,
    limit: int = 20,
) -> tuple[dict[str, str | int], ...]:
    data = _ok_data(payload)
    if not data:
        return ()
    items = data.get("items")
    if not isinstance(items, list):
        return ()
    currency = (display_currency or "CNY").upper()
    rows: list[dict[str, str | int]] = []
    for item in items:
        if len(rows) >= limit:
            break
        if not isinstance(item, dict):
            continue
        price = _optional_decimal_text(item.get("price"))
        quantity = _optional_int(item.get("num"))
        if price is None or quantity is None:
            continue
        row: dict[str, str | int] = {
            "source": "buff_buy_order",
            "price": f"{currency} {price}",
            "quantity": quantity,
        }
        order_id = _optional_str(item.get("id"))
        buyer_id = _optional_str(item.get("user_id"))
        created_at = _unix_timestamp_iso(item.get("created_at"))
        if order_id:
            row["order_id"] = order_id
        if buyer_id:
            row["buyer_id"] = buyer_id
        if created_at:
            row["created_at"] = created_at
        rows.append(row)
    return tuple(rows)


def extract_buff_recent_sales(
    payload: object,
    *,
    display_currency: str = "CNY",
    limit: int = 20,
) -> tuple[dict[str, str | int], ...]:
    data = _ok_data(payload)
    if not data:
        return ()
    items = data.get("items")
    if not isinstance(items, list):
        return ()
    rows: list[dict[str, str | int]] = []
    for item in items:
        if len(rows) >= limit:
            break
        if not isinstance(item, dict):
            continue
        price = _optional_decimal_text(item.get("price"))
        if price is None:
            continue
        row: dict[str, str | int] = {
            "source": "buff_bill_order",
            "price": f"{display_currency.upper()} {price}",
        }
        sold_at = _unix_timestamp_iso(
            item.get("buyer_pay_time") or item.get("transact_time") or item.get("created_at")
        )
        if sold_at:
            row["sold_at"] = sold_at
        asset_info = item.get("asset_info")
        if isinstance(asset_info, dict):
            asset_id = _optional_str(asset_info.get("assetid"))
            if asset_id:
                row["asset_id"] = asset_id
        rows.append(row)
    return tuple(rows)


def extract_buff_price_history(
    payload: object,
    *,
    display_currency: str = "EUR",
    limit: int | None = None,
) -> tuple[dict[str, str | int], ...]:
    data = _ok_data(payload)
    if not data:
        return ()
    series_by_kind = _buff_history_series_by_kind(data)
    if not series_by_kind:
        return ()

    grouped: dict[str, dict[str, str | int]] = {}
    for kind, points in series_by_kind.items():
        selected_points = points[-max(1, limit) :] if limit is not None else points
        for point in selected_points:
            parsed = _buff_history_point(point, kind=kind)
            if parsed is None:
                continue
            observed_at, value = parsed
            row = grouped.setdefault(
                observed_at,
                {
                    "source": "buff_price_history_v2",
                    "observed_at": observed_at,
                    "currency": display_currency.upper(),
                },
            )
            if kind == "sell_price":
                row["buff_sell_price"] = value
            elif kind == "buy_order_price":
                row["buff_buy_order_price"] = value
            elif kind == "listing_count":
                count = _optional_int(value)
                if count is not None:
                    row["buff_listing_count"] = count

    return tuple(grouped[key] for key in sorted(grouped))


def _buff_history_series_by_kind(data: dict[str, Any]) -> dict[str, list[Any]]:
    series_by_kind: dict[str, list[Any]] = {}

    def add_series(label: str, points: object) -> None:
        kind = _buff_history_kind(label)
        if kind is None or not isinstance(points, list):
            return
        series_by_kind.setdefault(kind, points)

    for key, value in data.items():
        if isinstance(value, list):
            add_series(key, value)
        elif isinstance(value, dict):
            nested_points = (
                value.get("data")
                or value.get("values")
                or value.get("points")
                or value.get("history")
            )
            label = str(value.get("name") or value.get("type") or key)
            add_series(label, nested_points)

    for container_key in ("series", "legend", "lines", "datasets"):
        container = data.get(container_key)
        if not isinstance(container, list):
            continue
        for entry in container:
            if not isinstance(entry, dict):
                continue
            label = str(
                entry.get("name")
                or entry.get("label")
                or entry.get("type")
                or entry.get("key")
                or ""
            )
            points = (
                entry.get("data")
                or entry.get("values")
                or entry.get("points")
                or entry.get("history")
            )
            add_series(label, points)

    return series_by_kind


def _buff_history_kind(label: str) -> str | None:
    normalized = label.strip().lower().replace("-", "_")
    if not normalized:
        return None
    if any(token in normalized for token in ("buy", "bid", "offer", "求购", "收购")):
        return "buy_order_price"
    if any(
        token in normalized
        for token in (
            "count",
            "num",
            "listing",
            "exist",
            "stock",
            "inventory",
            "在售",
            "出售数量",
        )
    ):
        return "listing_count"
    if any(
        token in normalized
        for token in ("price_history", "sell", "sale", "lowest", "buff", "出售")
    ):
        return "sell_price"
    return None


def _buff_history_point(point: object, *, kind: str) -> tuple[str, str] | None:
    timestamp: object
    value: object
    if isinstance(point, dict):
        timestamp = (
            point.get("time")
            or point.get("timestamp")
            or point.get("date")
            or point.get("observed_at")
            or point.get("t")
        )
        if kind == "listing_count":
            value = (
                point.get("count")
                or point.get("num")
                or point.get("value")
                or point.get("y")
            )
        else:
            value = (
                point.get("price")
                or point.get("value")
                or point.get("y")
                or point.get("sell_price")
                or point.get("buy_order_price")
            )
    elif isinstance(point, list | tuple) and len(point) >= 2:
        timestamp = point[0]
        value = point[1]
    else:
        return None

    observed_at = _unix_timestamp_iso_auto(timestamp)
    normalized_value = (
        str(_optional_int(value))
        if kind == "listing_count"
        else _optional_decimal_text(value)
    )
    if observed_at is None or normalized_value is None:
        return None
    return observed_at, normalized_value


def _buy_order_candidate_texts(rows: list[Any], body_text: str) -> tuple[str, ...]:
    labels = (
        "buy",
        "order",
        "purchase",
        "demand",
        "\u6c42\u8d2d",
        "\u6536\u8d2d",
        "\u8d2d\u4e70",
    )
    texts: list[str] = []
    for row in rows:
        text = ""
        if isinstance(row, dict):
            text = " ".join(
                str(row.get(key) or "")
                for key in ("className", "text")
            )
        elif isinstance(row, list):
            text = " ".join(str(cell) for cell in row)
        else:
            text = str(row)
        normalized = " ".join(text.split())
        if normalized and any(label in normalized.lower() for label in labels):
            texts.append(normalized)

    for line in body_text.splitlines():
        normalized = " ".join(line.split())
        if normalized and any(label in normalized.lower() for label in labels):
            texts.append(normalized)
    return tuple(texts)


def _first_int_after(value: str, start: int) -> int | None:
    match = re.search(r"\d[\d.,]*", value[start:])
    if not match:
        return None
    digits = re.sub(r"[^0-9]", "", match.group(0))
    return int(digits) if digits else None


def _iter_money_candidates(value: str) -> tuple[tuple[str, int], ...]:
    candidates = [
        (match.start(), match.end(), match.group(0))
        for match in MONEY_PATTERN.finditer(value)
    ]
    candidates.extend(
        (match.start(), match.end(), match.group(0))
        for match in LEADING_SYMBOL_MONEY_PATTERN.finditer(value)
    )
    ordered: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for _start, end, text in sorted(candidates):
        key = (text, end)
        if key in seen:
            continue
        seen.add(key)
        ordered.append((text, end))
    return tuple(ordered)


def _is_plausible_buff_order_price(raw_value: str, value: Decimal) -> bool:
    if value <= 0:
        return False
    if re.search(r"\d[\d.,]*\s*(?:\u00a5|\uffe5)\s*$", raw_value):
        return False
    if re.search(r"(?:\u00a5|\uffe5)\s*\d{5,}\s*$", raw_value):
        return False
    return value <= 1_000_000


def _append_debug(debug_log: list[str] | None, message: str) -> None:
    if debug_log is not None:
        debug_log.append(message)


def _buff_goods_id(buff_url: str) -> str | None:
    parsed = urlparse(buff_url)
    path_match = re.search(r"/goods/(\d+)", parsed.path)
    if path_match:
        return path_match.group(1)
    query = parse_qs(parsed.query)
    for key in ("goods_id", "id"):
        values = query.get(key)
        if values and values[0].isdigit():
            return values[0]
    return None


def _json_payload(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    text = value.get("text")
    if not isinstance(text, str) or not text.strip():
        return {}
    try:
        payload = json.loads(text)
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _ok_data(payload: object) -> dict[str, Any]:
    if not isinstance(payload, dict) or payload.get("code") != "OK":
        return {}
    data = payload.get("data")
    return data if isinstance(data, dict) else {}


def _optional_decimal_text(value: object) -> str | None:
    try:
        number = Decimal(str(value))
    except Exception:
        return None
    return format(number.normalize(), "f")


def _optional_int(value: object) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _optional_str(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _unix_timestamp_iso(value: object) -> str | None:
    timestamp = _optional_int(value)
    if timestamp is None or timestamp <= 0:
        return None
    return datetime.fromtimestamp(timestamp, tz=UTC).isoformat()


def _unix_timestamp_iso_ms(value: object) -> str | None:
    try:
        timestamp_ms = int(str(value))
    except (TypeError, ValueError):
        return None
    if timestamp_ms <= 0:
        return None
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC).isoformat()


def _unix_timestamp_iso_auto(value: object) -> str | None:
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if not text.isdigit():
            try:
                parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            except ValueError:
                return None
            return (parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)).isoformat()
        value = text
    try:
        timestamp = int(str(value))
    except (TypeError, ValueError):
        return None
    if timestamp <= 0:
        return None
    if timestamp > 10_000_000_000:
        timestamp = timestamp // 1000
    return datetime.fromtimestamp(timestamp, tz=UTC).isoformat()
