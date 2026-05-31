from decimal import Decimal

from packages.domain.market_parsing import (
    asset_name_from_market_hash,
    detect_currency,
    parse_int_from_text,
    parse_market_decimal,
    quality_from_market_hash,
    steam_currency_code,
    variant_key,
)


def test_parse_market_decimal_handles_common_market_formats() -> None:
    assert parse_market_decimal("12,34 EUR") == Decimal("12.34")
    assert parse_market_decimal("1,234.56 USD") == Decimal("1234.56")
    assert parse_market_decimal("90,-- EUR") == Decimal("90.00")
    assert parse_market_decimal("EUR unavailable") is None


def test_parse_market_identity_helpers() -> None:
    market_hash = "StatTrak AK-47 | Slate (Field-Tested)"

    assert asset_name_from_market_hash(market_hash) == "StatTrak AK-47 | Slate"
    assert quality_from_market_hash(market_hash) == "Field-Tested"
    assert variant_key("Field-Tested", stattrak=True) == "field-tested_st1"


def test_currency_and_integer_helpers() -> None:
    assert steam_currency_code("12,34 EUR", "1") == "EUR"
    assert steam_currency_code("$1.23", "3") == "USD"
    assert steam_currency_code("12.34", "3") == "EUR"
    assert detect_currency("12.34 CNY") == "CNY"
    assert parse_int_from_text("volume 1,234") == 1234
