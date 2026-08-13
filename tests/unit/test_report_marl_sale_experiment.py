import argparse

from apps.cli.report_marl_sale_experiment import build_report


def test_marl_sale_report_compares_all_baselines() -> None:
    report = build_report(
        argparse.Namespace(
            dataset_dir=None,
            split="test",
            limit=95,
            cash=100.0,
            supervised_probability=True,
        )
    )

    assert report["experiment"] == "marl_buy_hold_sell_functional"
    assert report["policies"]["hold"]["purchases"] == 0
    assert report["policies"]["buy-positive"]["purchases"] == 2
    assert report["policies"]["buy-and-sell"]["sales"] == 1
    assert report["policies"]["buy-and-sell"]["realized_profit_eur"] == 2.18
