"""Shared test fixtures: a local stand-in for the Scryfall search API.

The mock server speaks just enough HTTP to exercise ``scryfall_search`` without
touching the network. Tests select a canned scenario through the query string
they send (``q=ok``, ``q=badquery``, ...).
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import cast
from urllib.parse import parse_qs, urlparse

import pytest

JsonObject = dict[str, object]


def _card(name: str) -> JsonObject:
    return {"object": "card", "name": name}


class MockScryfallServer(HTTPServer):
    """An ``HTTPServer`` that records requests and tracks per-test state."""

    def __init__(
        self,
        server_address: tuple[str, int],
        handler: type[BaseHTTPRequestHandler],
    ) -> None:
        super().__init__(server_address, handler)
        self.recorded: list[JsonObject] = []
        self.flaky_hits = 0
        self.base_url = (
            f"http://127.0.0.1:{server_address[1] or self.server_address[1]}"
        )


class _MockHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        """Silence the default per-request logging to stderr."""

    def do_GET(self) -> None:  # noqa: N802 - name fixed by BaseHTTPRequestHandler
        server = cast("MockScryfallServer", self.server)
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        query = params.get("q", [""])[0]
        page = int(params.get("page", ["1"])[0])

        server.recorded.append(
            {
                "path": self.path,
                "q": query,
                "user_agent": self.headers.get("User-Agent"),
                "accept": self.headers.get("Accept"),
            }
        )

        if query == "ok":
            self._send(
                200,
                {
                    "object": "list",
                    "total_cards": 1,
                    "has_more": False,
                    "data": [_card("Shock")],
                },
            )
        elif query == "multipage":
            if page == 1:
                self._send(
                    200,
                    {
                        "object": "list",
                        "total_cards": 2,
                        "has_more": True,
                        "next_page": f"{server.base_url}/cards/search"
                        "?q=multipage&page=2",
                        "data": [_card("Page One Card")],
                    },
                )
            else:
                self._send(
                    200,
                    {
                        "object": "list",
                        "total_cards": 2,
                        "has_more": False,
                        "data": [_card("Page Two Card")],
                    },
                )
        elif query == "nomatch":
            self._send(
                404,
                {
                    "object": "error",
                    "code": "not_found",
                    "details": "No cards found matching your search.",
                },
            )
        elif query == "badrequest":
            self._send(
                400,
                {
                    "object": "error",
                    "code": "bad_request",
                    "details": "Your search contains unclosed parentheses.",
                },
            )
        elif query == "badquery":
            self._send(
                422,
                {
                    "object": "error",
                    "code": "validation_error",
                    "details": "Your query didn't match any of the expected patterns.",
                },
            )
        elif query == "ratelimited":
            self._send(
                429,
                {
                    "object": "error",
                    "code": "too_many_requests",
                    "details": "Slow down.",
                },
            )
        elif query == "evilnext":
            # First page is fine, but points next_page at a foreign host on the
            # SAME scheme as the base URL -- only the host check can reject it.
            self._send(
                200,
                {
                    "object": "list",
                    "total_cards": 2,
                    "has_more": True,
                    "next_page": "http://evil.example.com/cards/search?q=evilnext",
                    "data": [_card("Page One Card")],
                },
            )
        elif query == "badjson":
            # A 200 response whose body is not valid JSON at all.
            self._send_raw(200, b"<html>not json</html>")
        elif query == "flaky":
            server.flaky_hits += 1
            if server.flaky_hits == 1:
                self._send(500, {"object": "error", "details": "Internal error."})
            else:
                self._send(
                    200,
                    {
                        "object": "list",
                        "total_cards": 1,
                        "has_more": False,
                        "data": [_card("Recovered Card")],
                    },
                )
        elif query == "weird":
            # A 200 response whose JSON body is not an object.
            self._send(200, ["this", "is", "a", "list"])
        else:  # "alwaysdown" and anything unmapped
            self._send(500, {"object": "error", "details": "Internal error."})

    def _send(self, status: int, body: object) -> None:
        self._send_raw(status, json.dumps(body).encode())

    def _send_raw(self, status: int, payload: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


@pytest.fixture
def mock_scryfall() -> Iterator[MockScryfallServer]:
    """Start the mock server on an ephemeral port for the duration of a test."""
    server = MockScryfallServer(("127.0.0.1", 0), _MockHandler)
    thread = threading.Thread(
        target=lambda: server.serve_forever(poll_interval=0.02), daemon=True
    )
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.fixture(autouse=True)
def _reset_rate_limit_state() -> Iterator[None]:
    """Clear the module-level rate-limit timestamp between tests."""
    import scryfall_search

    scryfall_search._last_request_time = 0.0
    yield
    scryfall_search._last_request_time = 0.0
