import argparse

from apps.cli.report_marl_sale_experiment import _portfolio_run_summary, build_report


def test_marl_sale_report_describes_one_controlled_cycle() -> None:
    report = build_report(
        argparse.Namespace(
            cash=100.0,
            supervised_probability=True,
        )
    )

    assert report["experiment"] == "marl_buy_hold_sell_controlled_cycle"
    assert report["cycle"]["purchases"] == 1
    assert report["cycle"]["sales"] == 1
    assert report["cycle"]["unlock_date"] == "2026-01-09"
    assert report["cycle"]["realized_profit_eur"] == 2.18


def test_portfolio_run_summary_counts_concurrent_positions() -> None:
    result = {
        "steps": 3,
        "cash_available_eur": 92.0,
        "portfolio": {
            "equity_eur": 102.0,
            "realized_profit_eur": 2.0,
            "open_positions": 1,
            "closed_positions": 1,
            "capital_blocked_eur": 10.0,
            "drawdown_ratio": 0.0,
        },
        "trace": [
            {"event": "reset"},
            {"infos": {"trader": {"executed_buy": True, "executed_sale": False}}},
            {"infos": {"trader": {"executed_buy": True, "executed_sale": False}}},
            {"infos": {"trader": {"executed_buy": False, "executed_sale": True}}},
        ],
    }

    summary = _portfolio_run_summary(result, initial_cash_eur=100.0)

    assert summary["purchases"] == 2
    assert summary["sales"] == 1
    assert summary["maximum_concurrent_positions"] == 2
    assert summary["initial_cash_eur"] == 100.0
