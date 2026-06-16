from datetime import date
from decimal import Decimal

from packages.simulation import (
    BUFF163,
    STEAM,
    PortfolioRiskConfig,
    PortfolioSimulator,
    RiskCandidate,
    evaluate_portfolio_risk,
)


def test_portfolio_risk_allows_candidate_inside_limits() -> None:
    simulator = PortfolioSimulator(initial_cash_eur=Decimal("100"))
    simulator.buy(
        item_id="item-1",
        item_name="AK-47 | Slate",
        buy_platform=BUFF163,
        buy_price=Decimal("80"),
        buy_currency="CNY",
        purchased_at=date(2026, 1, 1),
    )

    snapshot = evaluate_portfolio_risk(
        simulator,
        as_of=date(2026, 1, 2),
        config=PortfolioRiskConfig(
            max_position_fraction=Decimal("0.20"),
            max_item_fraction=Decimal("0.30"),
            max_platform_fraction=Decimal("0.70"),
            max_blocked_fraction=Decimal("0.60"),
            min_cash_fraction=Decimal("0.10"),
        ),
        candidate=RiskCandidate(
            item_id="item-2",
            buy_platform=STEAM,
            buy_value_eur=Decimal("15"),
            available_quantity=3,
        ),
    )

    assert snapshot.candidate_allowed is True
    assert snapshot.violations == ()
    assert snapshot.observation["candidate_position_ratio"] == Decimal("0.15")
    assert snapshot.observation["blocked_capital_ratio"] == Decimal("0.25")


def test_portfolio_risk_blocks_candidate_that_breaks_exposure_limits() -> None:
    simulator = PortfolioSimulator(initial_cash_eur=Decimal("100"))
    simulator.buy(
        item_id="item-1",
        item_name="AK-47 | Slate",
        buy_platform=BUFF163,
        buy_price=Decimal("160"),
        buy_currency="CNY",
        purchased_at=date(2026, 1, 1),
    )

    snapshot = evaluate_portfolio_risk(
        simulator,
        as_of=date(2026, 1, 2),
        config=PortfolioRiskConfig(
            max_position_fraction=Decimal("0.20"),
            max_item_fraction=Decimal("0.30"),
            max_platform_fraction=Decimal("0.70"),
            max_blocked_fraction=Decimal("0.60"),
            min_cash_fraction=Decimal("0.10"),
        ),
        candidate=RiskCandidate(
            item_id="item-1",
            buy_platform=BUFF163,
            buy_value_eur=Decimal("25"),
            available_quantity=2,
        ),
    )

    assert snapshot.candidate_allowed is False
    assert snapshot.violations == ("position_fraction", "item_fraction")
    assert snapshot.limits["position_fraction"].value == Decimal("25")
    assert snapshot.limits["item_fraction"].value == Decimal("45")


def test_portfolio_risk_reports_liquidity_and_volatility_violations() -> None:
    simulator = PortfolioSimulator(initial_cash_eur=Decimal("100"))

    snapshot = evaluate_portfolio_risk(
        simulator,
        as_of=date(2026, 1, 2),
        config=PortfolioRiskConfig(
            min_liquidity_quantity=2,
            max_volatility=Decimal("0.25"),
        ),
        candidate=RiskCandidate(
            item_id="item-1",
            buy_platform=STEAM,
            buy_value_eur=Decimal("10"),
            available_quantity=1,
            volatility=Decimal("0.30"),
        ),
    )

    assert snapshot.candidate_allowed is False
    assert snapshot.violations == ("liquidity", "volatility")
    assert snapshot.limits["liquidity"].breached is True
    assert snapshot.limits["volatility"].usage_ratio == Decimal("1.2")


def test_portfolio_risk_without_candidate_observes_existing_max_exposures() -> None:
    simulator = PortfolioSimulator(initial_cash_eur=Decimal("100"))
    simulator.buy(
        item_id="item-1",
        item_name="AK-47 | Slate",
        buy_platform=BUFF163,
        buy_price=Decimal("80"),
        buy_currency="CNY",
        purchased_at=date(2026, 1, 1),
    )
    simulator.buy(
        item_id="item-2",
        item_name="M4A1-S | Nitro",
        buy_platform=BUFF163,
        buy_price=Decimal("120"),
        buy_currency="CNY",
        purchased_at=date(2026, 1, 1),
    )

    snapshot = evaluate_portfolio_risk(
        simulator,
        as_of=date(2026, 1, 2),
        config=PortfolioRiskConfig(max_platform_fraction=Decimal("0.20")),
    )

    assert snapshot.violations == ("platform_fraction",)
    assert snapshot.observation["item_exposure_ratio"] == Decimal("0.15")
    assert snapshot.observation["platform_exposure_ratio"] == Decimal("0.25")
