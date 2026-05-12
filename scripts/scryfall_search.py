"""Search the Scryfall Magic: The Gathering card database.

Works as a command-line tool and as an importable module. Standard library
only -- no third-party dependencies -- so the skill runs anywhere Python 3.10+
is installed, with no ``pip install`` step.

A future version could add a small TTL cache; v1 is deliberately stateless.

Note: rate limiting uses a module-level timestamp, so :func:`search` is not
safe to call concurrently from multiple threads. This matches the intended use
-- a CLI tool or a single-threaded caller.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, TypedDict

# Scryfall card and response objects have no fixed schema -- their fields vary
# by card layout, set, and endpoint -- so `Any`-valued dicts are unavoidable.
# Per CLAUDE.md, this comment is the required justification for the `Any`.
JsonDict = dict[str, Any]

BASE_URL = "https://api.scryfall.com/cards/search"
# urllib's default "Python-urllib/3.x" User-Agent is called out by Scryfall's
# docs as flagged-as-junk traffic. A real User-Agent is mandatory.
USER_AGENT = "ScryfallSearchSkill/0.1"
ACCEPT = "application/json;q=0.9,*/*;q=0.8"
# Search is in Scryfall's heavier rate-limit tier; keep requests >=100ms apart.
MIN_REQUEST_INTERVAL_S = 0.1
SERVER_ERROR_RETRY_DELAY_S = 1.0

_last_request_time: float = 0.0


class ScryfallError(Exception):
    """Raised for any Scryfall API error or network failure."""


class SearchResult(TypedDict):
    """The normalised shape returned by :func:`search`."""

    query: str
    total_cards: int
    pages_fetched: int
    has_more: bool
    data: list[JsonDict]


def _validate_url(url: str) -> None:
    """Reject any URL not on the same scheme and host as ``BASE_URL``.

    Scryfall hands back ``next_page`` URLs to follow during pagination; this
    keeps the client from being steered to an unexpected host.
    """
    allowed = urllib.parse.urlsplit(BASE_URL)
    target = urllib.parse.urlsplit(url)
    # Scheme and host are case-insensitive; `.hostname` is lower-cased and has
    # any userinfo/port stripped, so a host smuggled into userinfo cannot pass.
    same_scheme = target.scheme.lower() == allowed.scheme.lower()
    same_host = target.hostname == allowed.hostname and target.port == allowed.port
    if not (same_scheme and same_host):
        raise ScryfallError(
            f"Refusing to fetch unexpected URL '{url}' -- "
            f"expected {allowed.scheme}://{allowed.netloc}"
        )


def _throttle() -> None:
    """Sleep so consecutive requests stay at least ``MIN_REQUEST_INTERVAL_S`` apart."""
    global _last_request_time
    elapsed = time.monotonic() - _last_request_time
    if elapsed < MIN_REQUEST_INTERVAL_S:
        time.sleep(MIN_REQUEST_INTERVAL_S - elapsed)
    _last_request_time = time.monotonic()


def _open(url: str, timeout: float) -> tuple[int, bytes]:
    """Fetch ``url`` and return ``(status, body)``.

    A non-2xx response is returned like any other -- ``HTTPError`` is file-like,
    so its body (Scryfall's JSON error details) is still readable.
    """
    _validate_url(url)
    _throttle()
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": ACCEPT}
    )
    try:
        # URL scheme/host are checked by _validate_url above.
        with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def _error_details(body: bytes) -> str:
    """Pull Scryfall's human-readable ``details`` field out of an error body."""
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return "no details provided"
    if isinstance(parsed, dict):
        details = parsed.get("details")
        if isinstance(details, str):
            return details
    return "no details provided"


def _request(url: str, timeout: float) -> JsonDict | None:
    """Fetch one Scryfall page, retrying once on a 5xx server error.

    Returns the parsed JSON dict, or ``None`` for a 404 (no cards matched).
    Raises :class:`ScryfallError` for any other failure.
    """
    try:
        status, body = _open(url, timeout)
        if status >= 500:  # noqa: PLR2004 - HTTP status, self-explanatory
            time.sleep(SERVER_ERROR_RETRY_DELAY_S)  # one retry for transient errors
            status, body = _open(url, timeout)
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ScryfallError(f"Could not reach Scryfall: {exc}") from exc

    if status == 200:  # noqa: PLR2004
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError as exc:
            raise ScryfallError("Scryfall returned a non-JSON response.") from exc
        if not isinstance(parsed, dict):
            raise ScryfallError("Scryfall returned an unexpected response shape.")
        return parsed
    if status == 404:  # noqa: PLR2004
        return None  # Scryfall's "no cards matched" signal -- not an error.

    details = _error_details(body)
    if status in (400, 422):  # noqa: PLR2004 - malformed-query status codes
        raise ScryfallError(f"Scryfall rejected the query: {details}")
    if status == 429:  # noqa: PLR2004
        raise ScryfallError(
            "Rate limited by Scryfall -- wait 30s before retrying. "
            "Do not retry immediately; the lockout extends if you do."
        )
    raise ScryfallError(f"Scryfall returned HTTP {status}: {details}")


def _as_int(value: object) -> int:
    """Coerce a JSON value to ``int``, defaulting to 0 when absent or wrong-typed."""
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value


def search(
    query: str,
    *,
    unique: str = "cards",
    order: str | None = None,
    direction: str | None = None,
    include_extras: bool = False,
    include_multilingual: bool = False,
    include_variations: bool = False,
    max_pages: int = 1,
    timeout: float = 10.0,
) -> SearchResult:
    """Search Scryfall and return a normalised result.

    Args:
        query: A Scryfall query string (see references/query_syntax.md).
        unique: How to collapse duplicates -- "cards", "art", or "prints".
        order: Sort field, e.g. "name", "cmc", "released", "usd".
        direction: Sort direction -- "auto", "asc", or "desc".
        include_extras: Include funny/oversized/token cards.
        include_multilingual: Include non-English printings.
        include_variations: Include rare print variations.
        max_pages: Maximum pages to fetch (each is ~175 cards). 1 = first page.
        timeout: Per-request socket timeout in seconds.

    Returns:
        A dict with the query sent, total_cards, pages_fetched, has_more, and
        the combined card data from every fetched page.

    Raises:
        ScryfallError: On a malformed query (400/422), rate limiting (429), a
            persistent server error, or a network failure.
        ValueError: If ``max_pages`` is less than 1.
    """
    if max_pages < 1:
        raise ValueError(f"max_pages must be >= 1, got {max_pages}")

    params: dict[str, str] = {"q": query, "unique": unique}
    if order is not None:
        params["order"] = order
    if direction is not None:
        params["dir"] = direction
    if include_extras:
        params["include_extras"] = "true"
    if include_multilingual:
        params["include_multilingual"] = "true"
    if include_variations:
        params["include_variations"] = "true"

    url: str | None = f"{BASE_URL}?{urllib.parse.urlencode(params)}"
    cards: list[JsonDict] = []
    total_cards = 0
    pages_fetched = 0
    has_more = False

    while url is not None and pages_fetched < max_pages:
        page = _request(url, timeout)
        if page is None:  # 404 -- no cards matched.
            return SearchResult(
                query=query,
                total_cards=0,
                pages_fetched=0,
                has_more=False,
                data=[],
            )
        pages_fetched += 1
        if pages_fetched == 1:
            total_cards = _as_int(page.get("total_cards"))
        page_data = page.get("data")
        if isinstance(page_data, list):
            cards.extend(page_data)
        has_more = bool(page.get("has_more"))
        next_page = page.get("next_page")
        url = next_page if has_more and isinstance(next_page, str) else None

    return SearchResult(
        query=query,
        total_cards=total_cards,
        pages_fetched=pages_fetched,
        has_more=has_more,
        data=cards,
    )


def _positive_int(raw: str) -> int:
    """Parse a CLI argument that must be a positive integer."""
    value = int(raw)
    if value < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return value


def _build_parser() -> argparse.ArgumentParser:
    """Construct the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Search the Scryfall Magic: The Gathering card database."
    )
    parser.add_argument("query", help="A Scryfall query string.")
    parser.add_argument("--order", help="Sort field, e.g. name, cmc, released, usd.")
    parser.add_argument(
        "--dir",
        dest="direction",
        choices=["auto", "asc", "desc"],
        help="Sort direction.",
    )
    parser.add_argument(
        "--unique",
        choices=["cards", "art", "prints"],
        default="cards",
        help="How to collapse duplicate cards (default: cards).",
    )
    parser.add_argument(
        "--include-extras",
        action="store_true",
        help="Include funny/oversized/token cards.",
    )
    parser.add_argument(
        "--include-multilingual",
        action="store_true",
        help="Include non-English printings.",
    )
    parser.add_argument(
        "--include-variations",
        action="store_true",
        help="Include rare print variations.",
    )
    parser.add_argument(
        "--max-pages",
        type=_positive_int,
        default=1,
        help="Maximum result pages to fetch, ~175 cards each (default: 1).",
    )
    parser.add_argument(
        "--json-output",
        action="store_true",
        help="Emit compact single-line JSON, suitable for piping into jq.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the command-line interface. Returns a process exit code."""
    args = _build_parser().parse_args(argv)
    try:
        result = search(
            args.query,
            unique=args.unique,
            order=args.order,
            direction=args.direction,
            include_extras=args.include_extras,
            include_multilingual=args.include_multilingual,
            include_variations=args.include_variations,
            max_pages=args.max_pages,
        )
    except ScryfallError as exc:
        print(exc, file=sys.stderr)
        return 1
    print(json.dumps(result) if args.json_output else json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
