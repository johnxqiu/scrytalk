---
name: scryfall-search
description: Search the Scryfall Magic: The Gathering card database from a natural-language description. Use this skill whenever the user asks about MTG cards — finding cards by color, type, mana cost, set, format legality, oracle text, power/toughness, rarity, price, or any combination thereof. Trigger even when the user doesn't explicitly say "Scryfall" — phrases like "find me MTG cards that…", "what red instants exist with…", or "list commanders with…" should activate this skill.
---

# Scryfall Search

Translate a natural-language request for Magic: The Gathering cards into a
[Scryfall](https://scryfall.com) search query, run it through the bundled
helper script, and return both the query and the raw JSON results.

## When to use

Use this skill whenever the user wants to find Magic cards by any criteria —
color, card type, mana cost or value, oracle text, power/toughness, rarity,
set, format legality, color identity for Commander, price, artist, or any
combination. Trigger even if the user never says the word "Scryfall."

Do **not** use it for other Scryfall endpoints (random cards, autocomplete,
named-card lookup, set lists, bulk data) — this skill covers card search only.

## How to use

1. **Translate** the user's request into a Scryfall query string. Consult
   `references/query_syntax.md` for the operator reference and
   `references/translation_examples.md` for worked NL→query examples — read
   them for any non-trivial query.

2. **Run the helper.** `${CLAUDE_SKILL_DIR}` expands to this skill's directory,
   so the command works regardless of the current working directory:
   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/scryfall_search.py "<query string>"
   ```
   Optional flags:
   - `--order <field>` — sort field (`name`, `cmc`, `released`, `usd`, ...).
   - `--dir <auto|asc|desc>` — sort direction.
   - `--unique <cards|art|prints>` — how to collapse duplicates.
   - `--include-extras` — include tokens, oversized, and funny cards.
   - `--include-multilingual` — include non-English printings.
   - `--include-variations` — include rare print variations.
   - `--max-pages <N>` — fetch up to N pages (~175 cards each); default 1.
   - `--json-output` — compact single-line JSON for piping into tools.

3. **Return both** the translated query and the raw JSON response to the user.
   Do not summarize, filter, or curate the JSON unless the user explicitly asks
   for that — the raw response is the deliverable. Briefly state any
   assumptions you made while translating (e.g. how you interpreted "cheap").

## Translation guidelines

- Prefer short operators: `c:` over `color:`, `t:` over `type:`, `mv:` over
  `manavalue:`.
- "Cost N" almost always means mana value (`mv:`), not the literal mana cost.
- Commander / "can be my commander" questions want color **identity** (`id:`),
  not color (`c:`). `is:commander` already implies a legal commander.
- "Colorless" almost always means color **identity** (`id:c`), not printed
  color (`c:c`). `c:c` also matches Devoid cards (the Eldrazi), which are
  printed colorless but carry a *colored* identity — they can't go in a
  colorless or off-color deck. Likewise "<color> or colorless" describes a
  card pool: use identity (`id<=g` for "green or colorless"), not `c<=g`. Reach
  for `c:c` only when the user explicitly asks about a card's printed color.
- Subjective words ("cheap", "big", "efficient") have no operator — pick a
  sensible threshold and tell the user what you chose.
- Concepts with no operator ("wrath", "tutor", "ETB effect") map to oracle
  text — see the tricky examples in `references/translation_examples.md`.
- Pass sorting via the `--order` / `--dir` flags rather than embedding
  `order:` / `direction:` in the query string.

## Error handling

- If the script exits non-zero, show the user the stderr message **verbatim**
  and do not retry automatically.
- **HTTP 400 / 422** (malformed query): the query didn't parse — the script
  reports it as "Scryfall rejected the query". Relay the error, then try once
  with a corrected query.
- **HTTP 404** (no matches): not an error. Tell the user the search ran
  successfully but matched zero cards, and show the query so they can refine.
- **HTTP 429** (rate limited): do not retry. Tell the user to wait ~30 seconds;
  retrying immediately extends the lockout.
