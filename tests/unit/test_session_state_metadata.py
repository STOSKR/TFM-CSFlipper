from datetime import UTC, datetime
from pathlib import Path

from apps.cli.session_state_metadata import read_session_metadata, write_session_metadata


def test_session_metadata_tracks_nine_day_counter(tmp_path: Path) -> None:
    state_path = tmp_path / "buff_storage_state.json"
    state_path.write_text("{}", encoding="utf-8")
    captured_at = datetime(2026, 7, 1, 10, 0, tzinfo=UTC)

    write_session_metadata(
        platform="buff",
        state_path=state_path,
        captured_at=captured_at,
    )
    payload = read_session_metadata(
        platform="buff",
        state_path=state_path,
        now=datetime(2026, 7, 3, 9, 0, tzinfo=UTC),
    )

    assert payload["exists"] is True
    assert payload["captured_at"] == "2026-07-01T10:00:00+00:00"
    assert payload["expires_at"] == "2026-07-10T10:00:00+00:00"
    assert payload["days_remaining"] == 8
    assert payload["expired"] is False


def test_session_metadata_handles_missing_sidecar(tmp_path: Path) -> None:
    state_path = tmp_path / "steam_storage_state.json"
    state_path.write_text("{}", encoding="utf-8")

    payload = read_session_metadata(platform="steam", state_path=state_path)

    assert payload["exists"] is True
    assert payload["captured_at"] is None
    assert payload["days_remaining"] is None
