import sys

from apps.cli.scrape_job_server import ScrapeJobRunner
from apps.cli.web_dashboard_server import _limit_from_query, _scrape_status_payload


def test_dashboard_server_limit_query_is_bounded() -> None:
    assert _limit_from_query("limit=25") == 25
    assert _limit_from_query("limit=0") == 1
    assert _limit_from_query("limit=9999") == 500
    assert _limit_from_query("limit=nope") == 100
    assert _limit_from_query("") == 100


def test_scrape_status_payload_exposes_job_and_command() -> None:
    payload = _scrape_status_payload(ScrapeJobRunner(command_runner=lambda command: 0))

    assert payload["job"]["running"] is False
    assert payload["command"][:5] == [
        sys.executable,
        "-u",
        "-m",
        "apps.cli.render_stream_scrape",
        "50",
    ]
    assert "--all-profiles" in payload["command"]
    assert "--buff" in payload["command"]
    assert "--refresh" in payload["command"]
    assert "--persist" in payload["command"]
