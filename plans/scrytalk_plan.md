# Scryfall Search Skill — Build Plan

A planning document for Claude Code. Build the project described below following the specs in each section. If a decision isn't pinned down here, prefer the simplest reasonable choice and note the assumption in a comment — don't expand scope.

---

## 1. What we're building

An **Anthropic Skill** that lets Claude search the Scryfall MTG card database from natural-language prompts.

Flow:
1. User asks something in plain English (e.g. *"red dragons with flying that cost 5 or less"*).
2. Claude (with this skill loaded) translates the prompt into a Scryfall query string (e.g. `t:dragon c:r o:flying cmc<=5`).
3. Claude invokes the bundled helper script with that query.
4. The script hits `https://api.scryfall.com/cards/search`, handles headers / rate limiting / pagination, and returns the raw JSON.
5. Claude returns **both** the translated query and the raw JSON to the user.

This is a **GitHub portfolio project**, so the README and code quality matter as much as the functionality.

### Background links (read these if anything below is unclear)
- Anthropic Skills format: https://github.com/anthropics/skills (look at the repo's example skills for SKILL.md conventions)
- Scryfall API root: https://scryfall.com/docs/api
- Scryfall search syntax: https://scryfall.com/docs/syntax
- Scryfall rate limits: https://scryfall.com/docs/api/rate-limits

---

## 2. Repo structure

```
scryfall-search/
├── SKILL.md                          # Skill entrypoint (Claude reads this)
├── README.md                         # GitHub-facing docs
├── LICENSE                           # MIT
├── .gitignore                        # Standard Python
├── scripts/
│   └── scryfall_search.py            # The helper — CLI + importable
├── references/
│   ├── query_syntax.md               # Scryfall syntax cheatsheet for Claude
│   └── translation_examples.md       # NL → Scryfall worked examples
└── evals/
    └── evals.json                    # Test prompts (optional but recommended)
```

---

## 3. File specs

### 3.1 `SKILL.md`

YAML frontmatter, then markdown body. Format:

```markdown
---
name: scryfall-search
description: Search the Scryfall Magic: The Gathering card database from a natural-language description. Use this skill whenever the user asks about MTG cards — finding cards by color, type, mana cost, set, format legality, oracle text, power/toughness, rarity, price, or any combination thereof. Trigger even when the user doesn't explicitly say "Scryfall" — phrases like "find me MTG cards that…", "what red instants exist with…", or "list commanders with…" should activate this skill.
---

# Scryfall Search

[brief description of what the skill does]

## When to use

[trigger conditions — finding MTG cards by any criteria]

## How to use

1. Translate the user's natural-language request into a Scryfall query string. The Scryfall query language is documented in `references/query_syntax.md` — consult it for any non-trivial query. Worked examples are in `references/translation_examples.md`.
2. Run the bundled helper:
   ```bash
   python scripts/scryfall_search.py "<query string>"
   ```
   Optional flags: `--order`, `--dir`, `--unique`, `--include-extras`, `--max-pages`.
3. Return BOTH the translated query and the raw JSON response to the user. Do not summarize or filter the JSON unless the user explicitly asks for that — the raw response is the deliverable.

## Translation guidelines

[short list of heuristics for NL → Scryfall — e.g. prefer short operators (`c:` over `color:`), use color identity `id:` for commander questions, etc. Pull a few from translation_examples.md]

## Error handling

- If the script exits with a non-zero code, show the user the stderr message verbatim and don't retry automatically.
- If Scryfall returns 422, the query was malformed — relay the error and try a corrected query.
- If Scryfall returns 404, no cards matched — tell the user the query ran successfully but matched zero cards, and show the query so they can refine.
```

Keep the body under ~150 lines. The heavy reference material lives in `references/`.

### 3.2 `scripts/scryfall_search.py`

A single Python file that works as both a CLI and an importable module.

**Dependencies:** none — uses only the Python 3.10+ standard library (`urllib.request`, `urllib.parse`, `urllib.error`, `json`, `argparse`, `time`, `sys`). Keeping the skill zero-dep means it works anywhere Python 3 is installed, with no `pip install` step.

**Required constants:**
```python
BASE_URL = "https://api.scryfall.com/cards/search"
USER_AGENT = "ScryfallSearchSkill/0.1"      # MUST be set; urllib's default "Python-urllib/3.x" is flagged by Scryfall as junk traffic
ACCEPT = "application/json;q=0.9,*/*;q=0.8"
MIN_REQUEST_INTERVAL_S = 0.1                  # 100ms; search is in Scryfall's heavier 2 req/sec tier
```

**Public function:**
```python
def search(
    query: str,
    *,
    unique: str = "cards",          # "cards" | "art" | "prints"
    order: str | None = None,        # e.g. "name", "cmc", "released", "usd"
    direction: str | None = None,    # "auto" | "asc" | "desc"
    include_extras: bool = False,
    include_multilingual: bool = False,
    include_variations: bool = False,
    max_pages: int = 1,              # 1 = first page only (~175 cards); use higher for full sweeps
    timeout: float = 10.0,
) -> dict:
    """
    Returns a dict shaped like:
    {
        "query": "<the query string sent to Scryfall>",
        "total_cards": <int from first page's total_cards>,
        "pages_fetched": <int>,
        "has_more": <bool from final page>,
        "data": [<all card objects from all fetched pages>],
    }

    Raises ScryfallError on 4xx (with the API's error details message).
    Returns empty data with total_cards=0 on 404 (Scryfall's "no cards matched" response).
    """
```

**CLI invocation:**
```bash
python scripts/scryfall_search.py "<query>" [--order ORDER] [--dir DIR] \
    [--unique {cards,art,prints}] [--include-extras] [--max-pages N] [--json-output]
```

By default the CLI prints pretty-printed JSON (`json.dumps(result, indent=2)`) for human reading. Passing `--json-output` switches to compact single-line JSON (`json.dumps(result)`) suitable for piping into `jq` or other tools. Errors go to stderr with a non-zero exit code regardless of mode.

**Behavior requirements:**

1. **Headers** — every request MUST include `User-Agent` and `Accept`, set explicitly on the `urllib.request.Request` object. `urllib` will otherwise send `User-Agent: Python-urllib/3.x`, which Scryfall's docs explicitly call out as flagged-as-junk. This is the most common footgun with stdlib HTTP — get it right.
2. **Query construction** — use `urllib.parse.urlencode({"q": query, ...})` to build the query string. Don't hand-concatenate; the query language uses characters (`:`, `<=`, spaces, quotes) that need proper percent-encoding.
3. **Rate limiting** — track the timestamp of the last request as a module-level variable. Before each request, sleep so that requests are at least `MIN_REQUEST_INTERVAL_S` apart. Matters when paginating.
4. **Pagination** — Scryfall responses include `has_more` (bool) and `next_page` (URL). If `max_pages > 1` and `has_more`, follow `next_page` directly (don't reconstruct it — use the URL as given). Cap at `max_pages` pages even if more exist.
5. **Status code handling** — `urllib.request.urlopen` raises `urllib.error.HTTPError` on any non-2xx response. The `HTTPError` object is file-like, so you can still call `.read()` on it to get the response body (Scryfall returns useful JSON error details in 4xx responses). Catch it and dispatch:
    - `200` → parse and continue.
    - `404` → return `{"query": query, "total_cards": 0, "pages_fetched": 0, "has_more": False, "data": []}` without raising. This is Scryfall's "no cards matched" signal, not an error.
    - `422` → raise `ScryfallError` with the `details` field from the response body. This is a malformed query — surface it cleanly.
    - `429` → raise `ScryfallError("Rate limited by Scryfall — wait 30s before retrying")`. Do NOT auto-retry; Scryfall extends the lockout if you hammer them.
    - `5xx` → one retry after 1 second, then raise.
    - Network/timeout errors (`URLError`, `TimeoutError`) → wrap in `ScryfallError` with a clear message.
6. **Custom exception** — `class ScryfallError(Exception)`. Use it for anything API-related.
7. **No caching** — keep it stateless for v1. Note in a comment that a future version could add a TTL cache.

### 3.3 `references/query_syntax.md`

A condensed Scryfall query-syntax cheatsheet for Claude to consult. Build it by reading https://scryfall.com/docs/syntax and producing a markdown file that covers, at minimum:

- Colors and color identity (`c:`, `id:`, including comparison operators `>=`, `<=`)
- Types and subtypes (`t:`)
- Oracle text (`o:`)
- Mana cost and value (`m:`, `mv:` / `cmc:`)
- Power, toughness, loyalty, defense (`pow:`, `tou:`, `loy:`, `def:`) with comparators
- Rarity (`r:`)
- Sets and blocks (`s:`, `e:`, `b:`)
- Format legality (`f:`, `legal:`, `banned:`, `restricted:`)
- The `is:` predicate (commander, split, dfc, etc.) — list the most common values
- Price (`usd:`, `eur:`, `tix:`)
- Year / date (`year:`, `date:`)
- Artist, flavor text, watermark (`a:`, `ft:`, `wm:`)
- Boolean operators: `AND` (implicit), `OR`, `-` for negation, parentheses for grouping
- Exact match with quotes
- Useful tags like `game:paper`, `lang:en`

Each section: the operator, 1–2 line description, 2–3 concrete examples. Aim for ~200–300 lines total. Include a table of contents at the top.

### 3.4 `references/translation_examples.md`

15–25 worked examples of NL → Scryfall query, grouped by difficulty. Format each as:

```markdown
**Prompt:** Cheap red burn spells legal in Modern
**Query:** `t:instant OR t:sorcery c:r o:damage cmc<=2 f:modern`
**Notes:** "Burn" maps to oracle text matching "damage". "Cheap" is subjective — defaulting to CMC ≤ 2.
```

Cover ranges:
- Simple: single-attribute filters
- Compound: multiple operators
- Color identity for Commander questions
- Price and format constraints
- Tricky cases: "tribal" cards, "ETB effects", "tutors", "wraths" — where the NL term doesn't map to a single operator and requires creative oracle-text matching

The `Notes` field is the most valuable part. It teaches Claude how to think about ambiguous prompts.

### 3.5 `README.md`

GitHub-facing. Should include:
- One-paragraph project summary (skill for natural-language MTG card search)
- Demo: 2–3 example prompts and the resulting queries
- Installation: clone the repo, point Claude at the directory — no `pip install` needed (the helper uses only Python stdlib)
- Standalone CLI usage: `python scripts/scryfall_search.py "..."` with example output
- How the skill format works (one paragraph + link to Anthropic Skills docs)
- Project structure (the tree from section 2)
- Attribution: Scryfall API + Wizards of the Coast Fan Content Policy notice
- License

### 3.6 `.gitignore`

Standard Python: `__pycache__/`, `*.pyc`, `.venv/`, `venv/`, `.env`, `.pytest_cache/`, `*.egg-info/`.

### 3.7 `evals/evals.json` (optional but recommended for portfolio polish)

A small test suite of NL prompts with notes on what a correct query should look like. Don't write assertion code yet — just the prompts. Schema:

```json
{
  "skill_name": "scryfall-search",
  "evals": [
    {
      "id": 1,
      "prompt": "Find me all the legendary creatures with deathtouch that cost 3 or less.",
      "expected_query_contains": ["t:legendary", "t:creature", "o:deathtouch", "cmc<=3"],
      "notes": "Order of operators doesn't matter; case doesn't matter."
    }
  ]
}
```

Include 8–12 evals spanning easy / medium / hard.

---

## 4. Acceptance criteria

The build is done when:

- [ ] `python scripts/scryfall_search.py "t:dragon c:r"` runs and prints pretty-printed Scryfall JSON to stdout.
- [ ] `python scripts/scryfall_search.py "t:dragon c:r" --json-output | jq '.total_cards'` works (compact JSON pipes cleanly into `jq`).
- [ ] The script imports nothing outside the Python stdlib — `python -c "import ast; ast.parse(open('scripts/scryfall_search.py').read())"` and a manual scan of imports both confirm zero third-party deps.
- [ ] The same script handles 404 (no matches) without raising, and 422 (bad query) with a clean error message.
- [ ] Paginating with `--max-pages 3` on a broad query (e.g. `t:creature c:r`) returns more than one page's worth of data and respects the 100ms interval (verifiable by timing).
- [ ] Every API request carries an explicit non-default `User-Agent` and an `Accept` header (verify by inspecting the `Request` object or with a local mock).
- [ ] `SKILL.md` has the YAML frontmatter described in section 3.1, references both files in `references/`, and tells Claude to invoke the helper.
- [ ] `references/query_syntax.md` covers all the operator categories listed in section 3.3.
- [ ] `references/translation_examples.md` has at least 15 worked examples with `Notes`.
- [ ] `README.md` is portfolio-quality: clear demo, install steps, attribution.
- [ ] All code passes `python -m py_compile` and has type hints on public functions.

---

## 5. Out of scope (don't build)

- Other Scryfall endpoints (`/cards/named`, `/cards/autocomplete`, `/cards/random`, `/sets`, bulk data). Search only.
- Result summarization / curation — return the raw JSON.
- Caching, persistent storage, databases.
- A web UI or hosted demo.
- Tests beyond the eval prompts JSON. No pytest suite for v1.
- Image downloading or rendering.

---

## 6. Notes on tone and code style

- Python 3.10+, type hints on all public functions, docstrings on the module and the `search` function.
- Stdlib only — no third-party dependencies. Don't add `requests` "because it'd be cleaner." The minor verbosity of `urllib` is a deliberate trade for zero-install portability, and the boilerplate (one helper function for `urlopen` + headers) is small.
- Keep `scryfall_search.py` under ~250 lines. If it's growing past that, you're over-engineering.
- Error messages should be useful to a human reading them in a terminal, not stack traces.
- Comments only where the *why* isn't obvious — Scryfall's quirks (the 30-second 429 lockout, the heavy-tier rate limit on search) are worth a comment.
