from apps.cli.scrape_job_server import ScrapeJobRunner
from apps.cli.web_dashboard_server import (
    _command_payload,
    _limit_from_query,
    _local_command,
    _local_commands,
    _scrape_status_payload,
    _web_scrape_command,
)


def test_dashboard_server_limit_query_is_bounded() -> None:
    assert _limit_from_query("limit=25") == 25
    assert _limit_from_query("limit=0") == 1
    assert _limit_from_query("limit=9999") == 2000
    assert _limit_from_query("limit=nope") == 500
    assert _limit_from_query("") == 500


def test_scrape_status_payload_exposes_job_without_command_path() -> None:
    payload = _scrape_status_payload(ScrapeJobRunner(command_runner=lambda command: 0))

    assert payload["job"]["running"] is False
    assert "command" not in payload


def test_web_scrape_command_skips_refresh_by_default() -> None:
    command = _web_scrape_command()

    assert "--no-refresh" in command
    assert command[command.index("--stale-minutes") + 1] == "480"
    assert command[command.index("--steam-concurrency") + 1] == "2"
    assert command[command.index("--buff-concurrency") + 1] == "2"
    assert command[command.index("--buff-captcha-wait-seconds") + 1] == "300"
    assert "--score" in command
    assert "--concurrent-platforms" in command
    assert "--show-browser" not in command


def test_web_scrape_command_can_show_browsers() -> None:
    command = _web_scrape_command(show_browser=True)

    assert "--show-browser" in command


def test_web_scrape_command_can_skip_refresh() -> None:
    command = _web_scrape_command(refresh=False)

    assert "--no-refresh" in command
    assert "--refresh" not in command


def test_web_scrape_command_can_refresh() -> None:
    command = _web_scrape_command(refresh=True)

    assert "--refresh" in command
    assert "--no-refresh" not in command


def test_local_command_allowlist_exposes_expected_frontend_commands() -> None:
    commands = {command.id: command for command in _local_commands()}

    assert set(commands) == {"refresh_history"}
    assert _local_command("refresh_history") == commands["refresh_history"]
    assert _local_command("rm_everything") is None

    payload = _command_payload(commands["refresh_history"])
    assert payload["id"] == "refresh_history"
    assert "command" not in payload
    assert commands["refresh_history"].command[
        commands["refresh_history"].command.index("--stale-minutes") + 1
    ] == "480"
    assert "--no-buff" in commands["refresh_history"].command
