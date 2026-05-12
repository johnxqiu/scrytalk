"""Tests for the Scryfall search helper, driven by the local mock server."""

from __future__ import annotations

import json
import time

import pytest
import scryfall_search
from conftest import MockScryfallServer
from scryfall_search import ScryfallError, main, search


def _point_at_mock(monkeypatch: pytest.MonkeyPatch, server: MockScryfallServer) -> None:
    """Redirect the helper's base URL at the local mock server."""
    monkeypatch.setattr(scryfall_search, "BASE_URL", f"{server.base_url}/cards/search")


def test_search_returns_normalised_shape(
    monkeypatch: pytest.MonkeyPatch, mock_scryfall: MockScryfallServer
) -> None:
    _point_at_mock(monkeypatch, mock_scryfall)

    result = search("ok")

    assert result["query"] == "ok"
    assert result["total_cards"] == 1
    assert result["pages_fetched"] == 1
    assert result["has_more"] is False
    assert [card["name"] for card in result["data"]] == ["Shock"]


def test_search_sends_explicit_user_agent_and_accept_headers(
    monkeypatch: pytest.MonkeyPatch, mock_scryfall: MockScryfallServer
) -> None:
    _point_at_mock(monkeypatch, mock_scryfall)

    search("ok")

    recorded = mock_scryfall.recorded[0]
    assert recorded["user_agent"] == scryfall_search.USER_AGENT
    assert recorded["accept"] == scryfall_search.ACCEPT
    # urllib's flagged-as-junk default must never reach Scryfall.
    assert not str(recorded["user_agent"]).startswith("Python-urllib")


def test_search_no_match_returns_empty_data_without_raising(
    monkeypatch: pytest.MonkeyPatch, mock_scryfall: MockScryfallServer
) -> None:
    _point_at_mock(monkeypatch, mock_scryfall)

    result = search("nomatch")

    assert result["total_cards"] == 0
    assert result["data"] == []
    assert result["has_more"] is False


def test_search_bad_query_raises_with_api_details(
    monkeypatch: pytest.MonkeyPatch, mock_scryfall: MockScryfallServer
) -> None:
    _point_at_mock(monkeypatch, mock_scryfall)

    with pytest.raises(ScryfallError, match="didn't match any of the expected"):
        search("badquery")


def test_search_http_400_is_reported_as_a_rejected_query(
    monkeypatch: pytest.MonkeyPatch, mock_scryfall: MockScryfallServer
) -> None:
    _point_at_mock(monkeypatch, mock_scryfall)

    with pytest.raises(ScryfallError, match="rejected the query"):
        search("badrequest")


def test_search_rate_limited_raises_and_does_not_retry(
    monkeypatch: pytest.MonkeyPatch, mock_scryfall: MockScryfallServer
) -> None:
    _point_at_mock(monkeypatch, mock_scryfall)

    with pytest.raises(ScryfallError, match="[Rr]ate limit"):
        search("ratelimited")

    assert len(mock_scryfall.recorded) == 1


def test_search_retries_once_on_server_error_then_succeeds(
    monkeypatch: pytest.MonkeyPatch, mock_scryfall: MockScryfallServer
) -> None:
    _point_at_mock(monkeypatch, mock_scryfall)
    monkeypatch.setattr(scryfall_search, "SERVER_ERROR_RETRY_DELAY_S", 0.0)

    result = search("flaky")

    assert result["total_cards"] == 1
    assert len(mock_scryfall.recorded) == 2


def test_search_gives_up_after_one_retry_on_server_error(
    monkeypatch: pytest.MonkeyPatch, mock_scryfall: MockScryfallServer
) -> None:
    _point_at_mock(monkeypatch, mock_scryfall)
    monkeypatch.setattr(scryfall_search, "SERVER_ERROR_RETRY_DELAY_S", 0.0)

    with pytest.raises(ScryfallError):
        search("alwaysdown")

    assert len(mock_scryfall.recorded) == 2


def test_pagination_follows_next_page_up_to_max_pages(
    monkeypatch: pytest.MonkeyPatch, mock_scryfall: MockScryfallServer
) -> None:
    _point_at_mock(monkeypatch, mock_scryfall)

    result = search("multipage", max_pages=2)

    assert result["pages_fetched"] == 2
    assert result["has_more"] is False
    assert [card["name"] for card in result["data"]] == [
        "Page One Card",
        "Page Two Card",
    ]


def test_pagination_stops_at_max_pages_even_when_more_exist(
    monkeypatch: pytest.MonkeyPatch, mock_scryfall: MockScryfallServer
) -> None:
    _point_at_mock(monkeypatch, mock_scryfall)

    result = search("multipage", max_pages=1)

    assert result["pages_fetched"] == 1
    assert result["has_more"] is True
    assert len(mock_scryfall.recorded) == 1


def test_pagination_throttles_between_requests(
    monkeypatch: pytest.MonkeyPatch, mock_scryfall: MockScryfallServer
) -> None:
    _point_at_mock(monkeypatch, mock_scryfall)

    # Spy on time.sleep so we prove the throttle actually slept, rather than
    # relying on wall-clock timing the mock's own latency could satisfy.
    slept: list[float] = []

    def _record_sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr(time, "sleep", _record_sleep)

    search("multipage", max_pages=2)

    # The second request follows the first immediately, so the throttle must
    # sleep for a positive interval before it.
    assert slept, "throttle did not sleep between paginated requests"
    assert max(slept) > 0
    assert max(slept) <= scryfall_search.MIN_REQUEST_INTERVAL_S


def test_search_refuses_to_follow_next_page_on_a_foreign_host(
    monkeypatch: pytest.MonkeyPatch, mock_scryfall: MockScryfallServer
) -> None:
    _point_at_mock(monkeypatch, mock_scryfall)

    with pytest.raises(ScryfallError, match="[Uu]nexpected|[Hh]ost"):
        search("evilnext", max_pages=2)


def test_validate_url_rejects_non_https_scheme() -> None:
    with pytest.raises(ScryfallError):
        scryfall_search._validate_url("http://api.scryfall.com/cards/search?q=x")


def test_validate_url_rejects_foreign_host() -> None:
    with pytest.raises(ScryfallError):
        scryfall_search._validate_url("https://evil.example.com/cards/search")


def test_validate_url_rejects_host_smuggled_in_userinfo() -> None:
    # The allowed host appears only as URL userinfo; the real host is foreign.
    with pytest.raises(ScryfallError):
        scryfall_search._validate_url(
            "https://api.scryfall.com@evil.example.com/cards/search"
        )


def test_validate_url_accepts_the_canonical_endpoint() -> None:
    # Should not raise — the real Scryfall endpoint.
    scryfall_search._validate_url("https://api.scryfall.com/cards/search?q=t:dragon")


def test_validate_url_accepts_uppercase_scheme_and_host() -> None:
    # Scheme and host are case-insensitive; an upper-case URL is still valid.
    scryfall_search._validate_url("HTTPS://API.SCRYFALL.COM/cards/search?q=t:elf")


def test_search_rejects_a_non_positive_max_pages() -> None:
    for bad in (0, -1):
        with pytest.raises(ValueError, match="max_pages"):
            search("ok", max_pages=bad)


def test_search_raises_on_a_non_json_response_body(
    monkeypatch: pytest.MonkeyPatch, mock_scryfall: MockScryfallServer
) -> None:
    _point_at_mock(monkeypatch, mock_scryfall)

    with pytest.raises(ScryfallError, match="non-JSON"):
        search("badjson")


def test_network_error_is_wrapped_in_scryfall_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Port 1 is reserved and refuses connections immediately.
    monkeypatch.setattr(scryfall_search, "BASE_URL", "http://127.0.0.1:1/cards/search")

    with pytest.raises(ScryfallError):
        search("ok")


def test_search_forwards_optional_parameters_to_scryfall(
    monkeypatch: pytest.MonkeyPatch, mock_scryfall: MockScryfallServer
) -> None:
    _point_at_mock(monkeypatch, mock_scryfall)

    search(
        "ok",
        unique="prints",
        order="cmc",
        direction="asc",
        include_extras=True,
        include_multilingual=True,
        include_variations=True,
    )

    path = str(mock_scryfall.recorded[0]["path"])
    for fragment in (
        "unique=prints",
        "order=cmc",
        "dir=asc",
        "include_extras=true",
        "include_multilingual=true",
        "include_variations=true",
    ):
        assert fragment in path


def test_search_raises_on_unexpected_response_shape(
    monkeypatch: pytest.MonkeyPatch, mock_scryfall: MockScryfallServer
) -> None:
    _point_at_mock(monkeypatch, mock_scryfall)

    with pytest.raises(ScryfallError, match="unexpected response shape"):
        search("weird")


def test_error_details_handles_a_non_json_body() -> None:
    assert scryfall_search._error_details(b"<html>502</html>") == "no details provided"


def test_error_details_handles_a_json_body_without_details() -> None:
    assert (
        scryfall_search._error_details(b'{"object": "error"}') == "no details provided"
    )


def test_as_int_coerces_missing_or_wrong_typed_values_to_zero() -> None:
    assert scryfall_search._as_int(7) == 7
    assert scryfall_search._as_int(None) == 0
    assert scryfall_search._as_int("12") == 0
    # bool is a subclass of int but must not leak through as a count.
    assert scryfall_search._as_int(True) == 0


def test_cli_prints_pretty_json_by_default(
    monkeypatch: pytest.MonkeyPatch,
    mock_scryfall: MockScryfallServer,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _point_at_mock(monkeypatch, mock_scryfall)

    exit_code = main(["ok", "--max-pages", "1"])
    out = capsys.readouterr().out

    assert exit_code == 0
    assert json.loads(out)["total_cards"] == 1
    assert "\n" in out.strip()  # indented, multi-line


def test_cli_json_output_flag_emits_compact_single_line(
    monkeypatch: pytest.MonkeyPatch,
    mock_scryfall: MockScryfallServer,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _point_at_mock(monkeypatch, mock_scryfall)

    exit_code = main(["ok", "--json-output"])
    out = capsys.readouterr().out

    assert exit_code == 0
    assert json.loads(out)["total_cards"] == 1
    assert out.strip().count("\n") == 0  # single line


def test_cli_reports_errors_to_stderr_with_nonzero_exit(
    monkeypatch: pytest.MonkeyPatch,
    mock_scryfall: MockScryfallServer,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _point_at_mock(monkeypatch, mock_scryfall)

    exit_code = main(["badquery"])
    captured = capsys.readouterr()

    assert exit_code != 0
    assert captured.out == ""
    assert "didn't match" in captured.err


def test_cli_include_flags_reach_scryfall(
    monkeypatch: pytest.MonkeyPatch,
    mock_scryfall: MockScryfallServer,
) -> None:
    _point_at_mock(monkeypatch, mock_scryfall)

    exit_code = main(
        ["ok", "--include-extras", "--include-multilingual", "--include-variations"]
    )

    assert exit_code == 0
    path = str(mock_scryfall.recorded[0]["path"])
    for fragment in (
        "include_extras=true",
        "include_multilingual=true",
        "include_variations=true",
    ):
        assert fragment in path


def test_cli_rejects_a_non_positive_max_pages(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # argparse rejects the value before any request is made.
    with pytest.raises(SystemExit):
        main(["ok", "--max-pages", "0"])

    assert "positive" in capsys.readouterr().err
