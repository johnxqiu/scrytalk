# Natural Language → Scryfall Query: Worked Examples

Worked examples for translating plain-English card requests into Scryfall query
strings. The **Notes** field is the important part — it shows how to reason
about ambiguous prompts. See `query_syntax.md` for the operator reference.

General heuristics:

- Prefer short operators (`c:` over `color:`, `t:` over `type:`).
- Operator order and case never matter.
- "Commander" / "can be my commander" questions usually want color **identity**
  (`id:`), not color (`c:`).
- Subjective words ("cheap", "big", "efficient") have no operator — pick a
  reasonable threshold and **say so in your reply to the user**.
- When a concept has no operator (a "wrath", a "tutor"), match oracle text.

## Simple — single attribute

**Prompt:** All blue instants
**Query:** `c:u t:instant`
**Notes:** Two direct filters, AND-combined by default.

**Prompt:** Cards illustrated by Rebecca Guay
**Query:** `a:"rebecca guay"`
**Notes:** Quote multi-word artist names. `a:` does substring matching, so
`a:guay` would also work.

**Prompt:** Mythic rare planeswalkers
**Query:** `r:mythic t:planeswalker`
**Notes:** `r:` takes the rarity name directly.

**Prompt:** Goblins that aren't creatures
**Query:** `t:goblin -t:creature`
**Notes:** `-` negates the following keyword.

## Compound — several operators

**Prompt:** Red dragons with flying that cost 5 or less
**Query:** `t:dragon c:r o:flying mv<=5`
**Notes:** "Cost 5 or less" means mana value — `mv<=5`. Flying is a keyword;
`o:flying` (oracle text) and `kw:flying` both work, `o:` is the safe default.

**Prompt:** White creatures with power 4 or greater legal in Standard
**Query:** `c:w t:creature pow>=4 f:standard`
**Notes:** `pow` takes numeric comparisons. `f:standard` for format legality.

**Prompt:** Two-color artifact creatures under $2
**Query:** `t:artifact t:creature c=2 usd<2`
**Notes:** "Two-color" → `c=2` (exactly two colors). "Under $2" → `usd<2`.

**Prompt:** Common counterspells in Pauper
**Query:** `r:common o:counter o:"target spell" f:pauper`
**Notes:** No "counterspell" operator. Match oracle text: `o:counter` plus
`o:"target spell"` narrows out unrelated "counter" cards (e.g. +1/+1 counters).

## Color identity — Commander questions

**Prompt:** Cards I can run in a Golgari (black-green) commander deck
**Query:** `id<=bg`
**Notes:** Commander questions use color **identity**. `id<=bg` matches
everything castable under a B/G commander, including colorless cards.

**Prompt:** Legendary creatures that can be my commander in Esper colors
**Query:** `is:commander id<=esper`
**Notes:** `is:commander` already implies a legendary creature (or other legal
commander). `id<=esper` keeps it within white-blue-black.

**Prompt:** Mono-red commanders
**Query:** `is:commander id:r id=1`
**Notes:** `id:r` requires red identity; `id=1` forces exactly one color so
multicolor red commanders are excluded.

**Prompt:** Green or colorless creatures that grant haste
**Query:** `id<=g t:creature o:haste`
**Notes:** "Green or colorless" describes a *card pool* — what fits a green
deck — so it's color **identity**, `id<=g` (identity ⊆ green: mono-green plus
true colorless). The trap is `c<=g` (printed color): that also matches Devoid
cards like the colorless Eldrazi, which are printed colorless but carry a
*colored* identity (`{R}`, `{B}{R}`, ...) from mana symbols in their costs or
abilities — they read "colorless" but can't be played in a colorless or
mono-green deck. Use `c:c` only when the user truly means printed color (the
card frame, "is this card colorless"); `is:devoid` targets Devoid specifically.

## Price and format constraints

**Prompt:** Budget Modern staples under a dollar
**Query:** `f:modern usd<1 order:edhrec`
**Notes:** "Budget" → `usd<1`. "Staples" is subjective; sorting by `edhrec`
popularity surfaces the most-played cards first. Tell the user you sorted by
popularity rather than filtering.

**Prompt:** Expensive Reserved List cards
**Query:** `is:reserved usd>=50`
**Notes:** `is:reserved` for the Reserved List. "Expensive" → a $50 threshold;
note the threshold to the user.

## Tricky — concepts with no direct operator

**Prompt:** Board wipes / "wraths"
**Query:** `o:"destroy all" t:instant or o:"destroy all" t:sorcery`
**Notes:** "Wrath" has no operator. `o:"destroy all"` catches most. Some wipes
say "exile all" or deal damage to all creatures — broaden if the user wants
exhaustive coverage. Restricting to instants/sorceries avoids permanents that
merely mention the phrase.

**Prompt:** Tutors (cards that search your library)
**Query:** `o:"search your library" -t:land`
**Notes:** "Tutor" → the oracle phrase "search your library". Excluding lands
removes fetchlands and basics, which the user almost certainly doesn't mean.

**Prompt:** Creatures with enters-the-battlefield effects
**Query:** `t:creature o:"when ~ enters"`
**Notes:** `~` stands in for the card's own name. "ETB" → "when ~ enters" (the
current Oracle templating; older cards were "enters the battlefield").

**Prompt:** Permanents that trigger when a token enters the battlefield
**Query:** `is:permanent o:/whenever (a|one or more) [^.]*?tokens? enter/`
**Notes:** A *trigger that watches other permanents enter* — not the card's
own ETB, so the `when ~ enters` pattern above doesn't apply. Triggered
abilities read "Whenever a ... enters" / "Whenever one or more ... enter", so
anchor on `whenever` plus the entering noun. A bare `o:"token enters"` is a
trap: it also matches descriptive clauses like "The token enters tapped" on
cards that *make* tokens (e.g. Ochre Jelly, Ghired). The regex avoids that —
`whenever` rules out the descriptive clauses; `[^.]*?` allows adjectives ("a
non-Human creature token enters") but stops at a period so a match can't bleed
into the next sentence; `tokens?` covers singular and plural. Swap the noun
(`creature`, `artifact`, ...) for other "triggers when X enters" requests.

**Prompt:** Cheap red burn spells legal in Modern
**Query:** `(t:instant or t:sorcery) c:r o:damage mv<=2 f:modern`
**Notes:** "Burn" → oracle text "damage". "Cheap" is subjective — defaulting to
`mv<=2`. Parentheses group the instant/sorcery `OR` so the other terms still
apply to both.

**Prompt:** Tribal Elf payoffs — Elves that buff other Elves
**Query:** `t:elf o:"other elf"`
**Notes:** "Tribal payoff" has no operator. `o:"other elf"` finds lords and
anthem effects. Note this misses payoffs phrased differently (e.g. "Elves you
control"); broaden with an `OR` if needed.

**Prompt:** Cards that make Treasure tokens
**Query:** `o:"create" o:"treasure token"`
**Notes:** Token generation is oracle text. Pairing `o:create` with
`o:"treasure token"` avoids cards that merely reference Treasures.

**Prompt:** Big green stompy creatures from the last few years
**Query:** `c:g t:creature pow>=5 year>=2022`
**Notes:** Three subjective terms resolved with thresholds: "big" → `pow>=5`,
"green stompy" → `c:g t:creature`, "last few years" → `year>=2022`. State each
assumption back to the user.
