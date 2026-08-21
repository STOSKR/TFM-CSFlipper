import pytest

from apps.cli.scrape_job_server import ScrapeJobRunner
from apps.cli.session_state_metadata import write_session_metadata
from apps.cli.web_dashboard_server import (
    _command_execution_enabled,
    _command_payload,
    _limit_from_query,
    _local_command,
    _local_commands,
    _marl_cash,
    _marl_policy,
    _marl_simulation_payload,
    _scrape_status_payload,
    _session_payload,
    _web_scrape_command,
)


def test_command_execution_can_be_disabled_for_public_deployments(monkeypatch) -> None:
    monkeypatch.setenv("WEB_COMMANDS_ENABLED", "false")

    assert _command_execution_enabled() is False

    monkeypatch.setenv("WEB_COMMANDS_ENABLED", "true")
    assert _command_execution_enabled() is True


def test_dashboard_server_limit_query_is_bounded() -> None:
    assert _limit_from_query("limit=25") == 25
    assert _limit_from_query("limit=0") == 1
    assert _limit_from_query("limit=9999") == 2000
    assert _limit_from_query("limit=nope") == 500
    assert _limit_from_query("") == 500


def test_marl_simulation_uses_controlled_scenario_with_editable_capital() -> None:
    payload = _marl_simulation_payload(cash=500.0, policy="buy-and-sell")

    assert payload["kind"] == "controlled_marl_simulation"
    assert payload["initial_cash_eur"] == 500.0
    assert payload["cash_available_eur"] == 502.18
    assert payload["portfolio"]["closed_positions"] == 1
    assert payload["candidates"][0]["item_name"] == "AK-47 | Slate_FT_0"
    assert [entry["outcome"] for entry in payload["evolution"]] == [
        "Compra simulada",
        "Venta simulada",
    ]


def test_marl_simulation_validates_public_inputs() -> None:
    assert _marl_cash("250") == 250.0
    assert _marl_policy("hold") == "hold"

    with pytest.raises(ValueError):
        _marl_cash(0)
    with pytest.raises(ValueError):
        _marl_cash("not-a-number")
    with pytest.raises(ValueError):
        _marl_policy("train-ppo")


def test_scrape_status_payload_exposes_job_without_command_path() -> None:
    payload = _scrape_status_payload(ScrapeJobRunner(command_runner=lambda command: 0))

    assert payload["job"]["running"] is False
    assert "command" not in payload


def test_session_payload_exposes_buff_cookie_counter(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    state_path = tmp_path / "data/browser-state/buff_storage_state.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text("{}", encoding="utf-8")
    write_session_metadata(platform="buff", state_path=state_path)

    payload = _session_payload()

    assert payload["buff"]["exists"] is True
    assert payload["buff"]["captured_at"] is not None
    assert payload["buff"]["days_remaining"] == 9


def test_web_scrape_command_skips_refresh_by_default() -> None:
    command = _web_scrape_command()

    assert "--steam" in command
    assert "--buff" in command
    assert "--no-refresh" in command
    assert "--no-refresh-buff" in command
    assert command[command.index("--stale-minutes") + 1] == "480"
    assert command[command.index("--steam-concurrency") + 1] == "2"
    assert command[command.index("--buff-concurrency") + 1] == "1"
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
    assert "--no-refresh-buff" in command


def test_web_scrape_command_can_refresh() -> None:
    command = _web_scrape_command(refresh=True)

    assert "--refresh" in command
    assert "--no-refresh" not in command
    assert "--no-refresh-buff" in command


def test_web_scrape_command_can_enable_buff_for_scraping_only() -> None:
    command = _web_scrape_command(scrape_buff=True, refresh=True, refresh_buff=False)

    assert "--buff" in command
    assert "--refresh" in command
    assert "--no-refresh-buff" in command


def test_web_scrape_command_can_disable_buff_for_scraping() -> None:
    command = _web_scrape_command(scrape_buff=False)

    assert "--steam" in command
    assert "--no-buff" in command


def test_web_scrape_command_can_enable_buff_for_refresh() -> None:
    command = _web_scrape_command(scrape_buff=False, refresh=True, refresh_buff=True)

    assert "--no-buff" in command
    assert "--refresh" in command
    assert "--refresh-buff" in command


def test_local_command_allowlist_exposes_expected_frontend_commands() -> None:
    commands = {command.id: command for command in _local_commands()}

    assert set(commands) == {
        "login_steam",
        "login_buff",
        "refresh_history_steam",
        "refresh_history_with_buff",
    }
    assert _local_command("login_steam") == commands["login_steam"]
    assert _local_command("login_buff") == commands["login_buff"]
    assert _local_command("refresh_history_steam") == commands["refresh_history_steam"]
    assert _local_command("refresh_history_with_buff") == commands["refresh_history_with_buff"]
    assert _local_command("rm_everything") is None

    payload = _command_payload(commands["refresh_history_steam"])
    assert payload["id"] == "refresh_history_steam"
    assert payload["group"] == "maintenance"
    assert "command" not in payload
    assert commands["refresh_history_steam"].command[
        commands["refresh_history_steam"].command.index("--stale-minutes") + 1
    ] == "480"
    assert "--no-buff" in commands["refresh_history_steam"].command
    assert "--buff" in commands["refresh_history_with_buff"].command
    assert _command_payload(commands["login_steam"])["group"] == "login"
    assert "--login-only" in commands["login_steam"].command
    assert "--steam" in commands["login_steam"].command
    assert "--no-buff" in commands["login_steam"].command
    assert "--login-only" in commands["login_buff"].command
    assert "--no-steam" in commands["login_buff"].command
    assert "--buff" in commands["login_buff"].command
