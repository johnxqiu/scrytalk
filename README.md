# scrytalk — Scryfall Search Skill

An agentic [Skill](https://www.anthropic.com/news/skills) for *Magic: The 
Gathering* card search. Lets an AI agent — such as Claude Code or 
opencode — search the [Scryfall](https://scryfall.com) card database from
plain-English prompts. The user describes the cards they want; the agent
translates that into a Scryfall query, runs a bundled helper script to run the
query, and returns both the query and the raw API results.

## How it works

```
"red dragons with flying that cost 5 or less"
        │
        ▼  the agent translates (using references/query_syntax.md)
   t:dragon c:r o:flying mv<=5
        │
        ▼  scripts/scryfall_search.py  →  api.scryfall.com/cards/search
   raw Scryfall JSON  (returned to the user alongside the query)
```

## Installation

No `pip install` is needed — the helper uses only the Python standard library
(Python 3.10+).

Both Claude Code and opencode discover skills in `~/.claude/skills/`. Clone the
repository and symlink it in:

```console
$ git clone <repo-url> ~/git/scrytalk
$ ln -s ~/git/scrytalk ~/.claude/skills/scryfall-search
```

Then ask your agent about Magic cards in plain language from any project — the
skill triggers on its own.

For a project-scoped install instead, place the skill under
`.claude/skills/scryfall-search/` inside a repository; both tools read that
path too. opencode additionally discovers skills in `~/.config/opencode/skills/`
and `.opencode/skills/`, if you prefer a tool-specific location.

The skill is model-agnostic, but it needs a tool-calling-capable model: the
agent invokes the skill and runs the helper script through tool calls, so the
model (any provider) must support function calling and be capable enough to do
it reliably. Smaller local models may handle this poorly.

## Standalone CLI usage

The helper also works as a plain command-line tool:

```console
$ python3 scripts/scryfall_search.py "t:dragon c:r mv<=4"
{
  "query": "t:dragon c:r mv<=4",
  "total_cards": 66,
  "pages_fetched": 1,
  "has_more": false,
  "data": [
    { "object": "card", "name": "Dragon Whelp", ... },
    ...
  ]
}
```

Compact output pipes cleanly into `jq`:

```console
$ python3 scripts/scryfall_search.py "t:dragon c:r" --json-output | jq '.total_cards'
```

Flags: `--order`, `--dir`, `--unique`, `--include-extras`, `--max-pages`,
`--json-output`. Run with `--help` for details.

## How the skill format works

An Anthropic Skill is a directory with a `SKILL.md` file: YAML frontmatter
(name + a description that tells the agent when to trigger the skill) followed
by markdown instructions. When the skill is loaded, the agent reads `SKILL.md`,
consults the bundled `references/` material as needed, and invokes the helper
script. The format is supported by both Claude Code and opencode; see the
[Anthropic Skills documentation](https://www.anthropic.com/news/skills) for the
full format.

## Project structure

```
scrytalk/
├── SKILL.md                      # skill entrypoint (the agent reads this)
├── README.md                     # this file
├── LICENSE                       # MIT
├── pyproject.toml                # project metadata + dev dependencies
├── scripts/
│   └── scryfall_search.py        # the helper — CLI + importable, stdlib only
├── references/
│   ├── query_syntax.md           # Scryfall query-syntax cheatsheet
│   └── translation_examples.md   # natural-language → query worked examples
├── tests/
│   ├── conftest.py               # local mock-server fixture
│   └── test_scryfall_search.py   # helper test suite
└── evals/
    └── evals.json                # natural-language eval prompts
```

## Development

The shipped skill has zero runtime dependencies. The test suite needs `pytest`;
[uv](https://docs.astral.sh/uv/) manages the dev environment:

```console
$ uv sync
$ uv run pytest --cov
```

Tests run against a local stand-in HTTP server (`tests/conftest.py`) and never
touch the real Scryfall API.

## Attribution

This project queries the [Scryfall API](https://scryfall.com/docs/api). Please
respect [Scryfall's API guidelines](https://scryfall.com/docs/api), including
its rate limits.

Portions of this project use unofficial Fan Content permitted under the
[Wizards of the Coast Fan Content Policy](https://company.wizards.com/en/legal/fancontentpolicy).
*Magic: The Gathering* is copyright Wizards of the Coast, LLC. This project is
not produced by, endorsed by, or affiliated with Wizards of the Coast or
Scryfall.

## License

[MIT](LICENSE).
