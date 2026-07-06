import os
import subprocess
import sys
from collections import Counter
from dataclasses import replace

import pytest

from apps.acquisition.steamdt_hanging import SteamDTCandidate
from apps.acquisition.streaming_pipeline import StreamingPipelineSummary
from apps.cli import render_stream_scrape
from apps.cli.render_stream_scrape import build_parser
from packages.runtime_config import load_runtime_config


def test_render_stream_scrape_defaults_match_local_fast_flow() -> None:
    args = build_parser(load_runtime_config()).parse_args([])

    assert args.limit == 25
    assert args.all_profiles is True
    assert args.steam is True
    assert args.buff is True
    assert args.steam_api is False
    assert args.steam_concurrency == 2
    assert args.buff_concurrency == 1
    assert args.batch_size == 10
    assert args.persist is True
    assert args.refresh is False
    assert args.score is False


def test_render_stream_scrape_accepts_scrape_flow_style_filter_aliases() -> None:
    args = build_parser(load_runtime_config()).parse_args(
        ["10", "--no-all-profiles", "--min", "100", "--max", "500", "--vol", "12"]
    )

    assert args.limit == 10
    assert args.all_profiles is False
    assert args.min_price == 100
    assert args.max_price == 500
    assert args.min_volume == 12


def test_render_stream_scrape_fast_alias_selects_fast_profile() -> None:
    args = build_parser(load_runtime_config()).parse_args(["--fast", "--no-all-profiles"])
    if args.fast:
        args.profile = "platform_arbitrage_fast"

    assert args.profile == "platform_arbitrage_fast"


def test_render_stream_scrape_prints_unicode_when_parent_encoding_is_cp1252() -> None:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "cp1252"

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import apps.cli.render_stream_scrape; print('render_stream_candidate=★ item')",
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )

    assert result.returncode == 0
    assert "render_stream_candidate=★ item" in result.stdout


def test_render_stream_refresh_child_forces_utf8(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, str]] = []

    class Result:
        returncode = 0

    def fake_run(*_args: object, **kwargs: object) -> Result:
        calls.append(kwargs["env"])
        return Result()

    monkeypatch.setenv("PYTHONIOENCODING", "cp1252")
    monkeypatch.setenv("PWDEBUG", "1")
    monkeypatch.setattr(render_stream_scrape.subprocess, "run", fake_run)

    args = build_parser(load_runtime_config()).parse_args(["--no-refresh"])
    render_stream_scrape._run_refresh(args)

    assert calls[0]["PYTHONIOENCODING"] == "utf-8"
    assert calls[0]["PYTHONUTF8"] == "1"
    assert "PWDEBUG" not in calls[0]


@pytest.mark.asyncio
async def test_render_stream_scrape_limit_applies_per_profile(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class FakeDiscovery:
        def __init__(self, filters: object, *, progress_log: object) -> None:
            self.filters = filters

        async def discover(self) -> tuple[SteamDTCandidate, ...]:
            max_candidates = int(self.filters.max_candidates)
            balance_type = str(self.filters.balance_type).replace(" ", "_")
            return tuple(
                SteamDTCandidate(
                    item_name=f"{balance_type}_{index}",
                    market_hash_name=f"{balance_type}_{index} (Field-Tested)",
                    quality="Field-Tested",
                )
                for index in range(max_candidates)
            )

    monkeypatch.setattr(render_stream_scrape, "SteamDTHangingDiscovery", FakeDiscovery)

    args = build_parser(load_runtime_config()).parse_args(["2"])
    candidates = [
        candidate async for candidate in render_stream_scrape._iter_steamdt_candidates(args)
    ]

    assert len(candidates) == 4
    assert Counter(candidate.strategy_id for candidate in candidates) == {
        "steam_sell_slow": 2,
        "platform_arbitrage_safe": 2,
    }
    assert {
        candidate.buy_mode
        for candidate in candidates
        if candidate.strategy_id == "steam_sell_slow"
    } == {"Buy via Platform Buy Order"}
    output = capsys.readouterr().out
    assert "render_stream_profile_done=steam_sell_slow candidates=2" in output
    assert "render_stream_profile_emitted=steam_sell_slow candidates=2" in output
    assert "render_stream_profile_done=platform_arbitrage_safe candidates=2" in output
    assert "render_stream_profile_emitted=platform_arbitrage_safe candidates=2" in output


@pytest.mark.asyncio
async def test_render_stream_scrape_refresh_runs_once_after_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    async def fake_pipeline(*_args: object, **_kwargs: object) -> StreamingPipelineSummary:
        return replace(StreamingPipelineSummary(), candidates_enqueued=4)

    def fake_refresh(_args: object) -> int:
        nonlocal calls
        calls += 1
        return 0

    monkeypatch.setattr(render_stream_scrape, "run_streaming_pipeline", fake_pipeline)
    monkeypatch.setattr(render_stream_scrape, "_run_refresh", fake_refresh)

    args = build_parser(load_runtime_config()).parse_args(["--refresh", "--no-score"])

    assert await render_stream_scrape.run(args) == 0
    assert calls == 1
