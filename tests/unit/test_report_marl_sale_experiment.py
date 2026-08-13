import argparse

from apps.cli.report_marl_sale_experiment import build_report


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
