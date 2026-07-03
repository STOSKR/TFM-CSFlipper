import os
from apps.cli.scrape_job_server import ScrapeJobRunner
from apps.cli.web_dashboard_server import (
    _command_payload,
    _limit_from_query,
    _local_command,
    _local_commands,
    _scrape_status_payload,
    _web_revision,
    _web_scrape_command,
)


def test_dashboard_server_limit_query_is_bounded() -> None:
    assert _limit_from_query("limit=25") == 25
    assert _limit_from_query("limit=0") == 1
    assert _limit_from_query("limit=9999") == 500
    assert _limit_from_query("limit=nope") == 100
    assert _limit_from_query("") == 100


def test_scrape_status_payload_exposes_job_without_command_path() -> None:
    payload = _scrape_status_payload(ScrapeJobRunner(command_runner=lambda command: 0))

    assert payload["job"]["running"] is False
    assert "command" not in payload


def test_web_scrape_command_refreshes_items_older_than_eight_hours() -> None:
    command = _web_scrape_command()

    assert "--refresh" in command
    assert command[command.index("--stale-minutes") + 1] == "480"
    assert "--score" in command
    assert "--concurrent-platforms" in command


def test_web_revision_tracks_static_file_changes(tmp_path) -> None:
    app_js = tmp_path / "app.js"
    app_js.write_text("one", encoding="utf-8")
    (tmp_path / "index.html").write_text("html", encoding="utf-8")
    (tmp_path / "styles.css").write_text("css", encoding="utf-8")
    before = _web_revision(tmp_path)

    app_js.write_text("two", encoding="utf-8")
    os.utime(app_js, ns=(before + 1_000_000_000, before + 1_000_000_000))

    assert _web_revision(tmp_path) > before


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
