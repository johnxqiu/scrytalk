# Scryfall Query Syntax Cheatsheet

A condensed reference for translating natural-language card requests into
Scryfall query strings. Condensed from <https://scryfall.com/docs/syntax>.

Search terms are **combined with implicit AND** — every term must match. Use
`OR` for alternatives and `-` to negate. Comparison operators `>`, `<`, `>=`,
`<=`, `=`, `!=` work on most numeric/quantity keywords.

## Contents

- [Colors and color identity](#colors-and-color-identity)
- [Card types](#card-types)
- [Card text (oracle / keywords)](#card-text)
- [Mana cost and mana value](#mana-cost-and-mana-value)
- [Power, toughness, loyalty](#power-toughness-loyalty)
- [Rarity](#rarity)
- [Sets and blocks](#sets-and-blocks)
- [Format legality](#format-legality)
- [The `is:` / `not:` predicate](#the-is--not-predicate)
- [Prices](#prices)
- [Artist, flavor text, watermark](#artist-flavor-text-watermark)
- [Year and date](#year-and-date)
- [Languages and games](#languages-and-games)
- [Boolean logic and grouping](#boolean-logic-and-grouping)
- [Exact names and regex](#exact-names-and-regex)
- [Display and uniqueness keywords](#display-and-uniqueness-keywords)

## Colors and color identity

- `c:` / `color:` — the card's color. `id:` / `identity:` — color identity
  (use this for Commander questions).
- Accepts letters `w u b r g`, full names (`blue`), and `c`/`colorless`,
  `m`/`multicolor`. Nicknames work too: guild names (`azorius`), shard names
  (`bant`), wedge names (`abzan`), college names (`quandrix`).
- Comparisons treat colors as sets: `>=uw` = at least white and blue. Numbers
  match color count: `c=2` = exactly two colors.
- **Devoid trap:** Devoid cards (the Eldrazi) are printed colorless, so `c:c`
  matches them, but they keep a *colored* color identity. For "colorless" in
  any deckbuilding or Commander sense, use `id:c`. `is:devoid` matches Devoid
  specifically.

```
c:rg                     red AND green cards
color>=uw -c:red         at least W and U, but not red
id<=esper t:instant      instants playable under an Esper commander
id:c t:land              colorless-identity lands
```

## Card types

- `t:` / `type:` — any supertype, card type, or subtype. Partial words allowed.

```
t:merfolk t:legend       legendary merfolk
t:goblin -t:creature     goblin cards that aren't creatures
t:legendary t:dragon     legendary dragons
```

## Card text

- `o:` / `oracle:` — current Oracle text. Quote phrases with spaces/punctuation.
  `~` is a placeholder for the card's own name.
- `fo:` / `fulloracle:` — full Oracle text including reminder text.
- `kw:` / `keyword:` — a specific keyword ability.

```
o:draw t:creature        creatures that care about drawing cards
o:"~ enters tapped"      cards that enter tapped
kw:flying -t:creature    noncreatures with the flying keyword
o:"deals" o:"damage"     cards mentioning dealing damage (burn)
```

## Mana cost and mana value

- `m:` / `mana:` — symbols in the mana cost. Shorthand `G` = `{G}`; wrap
  complex symbols like `{2/G}` or `{R/P}` in braces. Comparisons treat costs as
  symbol sets.
- `mv:` / `cmc:` / `manavalue:` — mana value, numeric comparisons. Also
  `mv:even` / `mv:odd`.
- `devotion:` — devotion contribution. `produces:` — colors of mana produced.
- `is:hybrid`, `is:phyrexian` — costs containing those symbol kinds.

```
mv<=3 c:r                red cards with mana value 3 or less
m:{R/P}                  cards with a Phyrexian red symbol
mv=5 c:u                 blue cards with mana value exactly 5
produces=wu              cards that produce white and blue mana
```

## Power, toughness, loyalty

- `pow:` / `power:`, `tou:` / `toughness:`, `pt:` / `powtou:` (total),
  `loy:` / `loyalty:`, `def:` / `defense:`. All take numeric comparisons and
  can be compared against each other.

```
pow>=8                   8 or more power
pow>tou t:creature c:w   top-heavy white creatures
t:planeswalker loy=3     planeswalkers starting at 3 loyalty
```

## Rarity

- `r:` / `rarity:` — `common`, `uncommon`, `rare`, `special`, `mythic`,
  `bonus`. Comparisons work (`r>=rare`).
- `in:rare` — ever printed at that rarity. `new:rarity` — first time at a new
  rarity.

```
r:common t:artifact      common artifacts
r>=rare t:creature       rares and mythics
```

## Sets and blocks

- `s:` / `e:` / `set:` / `edition:` — set code. `cn:` / `number:` — collector
  number (ranges allowed). `b:` / `block:` — block, by any set code in it.
- `in:` — cards that ever "passed through" a set code.
- `st:` — product type (`st:core`, `st:expansion`, `st:masters`,
  `st:commander`, `st:funny`, ...).

```
e:war                    cards from War of the Spark
b:wwk                    cards in the Zendikar block
in:lea                   cards ever printed in Alpha
```

## Format legality

- `f:` / `format:` — legal in a format. `banned:`, `restricted:` — banned or
  restricted in a format.
- Formats: `standard`, `pioneer`, `modern`, `legacy`, `vintage`, `pauper`,
  `commander`, `brawl`, `historic`, `timeless`, `alchemy`, `penny`,
  `oathbreaker`, `duel`, `premodern`, `oldschool`, and more.

```
c:g t:creature f:pauper  green creatures legal in Pauper
banned:legacy            cards banned in Legacy
f:modern f:standard      cards legal in both Modern and Standard
```

## The `is:` / `not:` predicate

`is:VALUE` matches a category; `not:VALUE` is the same as `-is:VALUE`. Common
values:

- **Commander:** `is:commander`, `is:brawler`, `is:companion`,
  `is:duelcommander`, `is:oathbreaker`, `is:partner`, `is:gamechanger`.
- **Faces:** `is:split`, `is:flip`, `is:transform` (`is:tdfc`), `is:meld`,
  `is:dfc`, `is:mdfc`, `is:leveler`.
- **Effects:** `is:spell`, `is:permanent`, `is:historic`, `is:modal`,
  `is:vanilla`, `is:frenchvanilla`, `is:bear`, `is:party`, `is:outlaw`.
- **Lands:** `is:dual`, `is:fetchland`, `is:shockland`, `is:painland`,
  `is:checkland`, `is:fastland`, `is:manland` / `is:creatureland`, `is:triome`.
- **Misc:** `is:reprint`, `is:reserved`, `is:funny`, `is:promo`, `is:digital`,
  `is:foil`, `is:fullart` / `is:full`, `is:hires`, `is:unique`.

```
is:commander id:bant     legendary creatures playable as a Bant commander
is:fetchland             all fetchlands
is:spell c>=br f:duel    black-red multicolor spells in Duel Commander
```

## Prices

- `usd:`, `eur:`, `tix:` — price with numeric comparisons.
- `cheapest:usd` / `cheapest:eur` / `cheapest:tix` — the cheapest print.

```
usd<1 f:modern           Modern-legal cards under $1
tix>15 t:planeswalker    planeswalkers over 15 TIX on MTGO
```

## Artist, flavor text, watermark

- `a:` / `artist:` — illustrator. `artists>1` — multiple artists.
- `ft:` / `flavor:` — flavor text. `wm:` / `watermark:` — watermark;
  `has:watermark` matches any.

```
a:"avon"                 cards illustrated by John Avon
ft:mishra                cards mentioning Mishra in flavor text
wm:orzhov                cards with the Orzhov watermark
```

## Year and date

- `year:` — release year, numeric comparison. `date:` — `yyyy-mm-dd`, a set
  code, or `now` / `today`.

```
year<=1994               cards from 1994 and earlier
year>=2023 t:dragon      recent dragons
date>=2015-08-18         cards printed on or after that date
```

## Languages and games

- `lang:` / `language:` — printing language; `lang:any` widens the search.
- `game:` — `paper`, `mtgo`, `arena`. `in:` also accepts these.

```
lang:japanese t:goblin   Japanese goblin printings
game:paper -in:mtgo      paper cards never on MTGO
```

## Boolean logic and grouping

- Terms are **AND** by default. `OR` (or `or`) offers alternatives.
- `-` negates any keyword (`-t:creature`). `not:` inverts `is:`.
- Parentheses `( )` group conditions — most useful with `OR`.

```
t:fish or t:bird                     fish or birds
t:legendary (t:goblin or t:elf)      legendary goblins or elves
o:flying -t:creature                 noncreatures granting flying
```

## Exact names and regex

- `!name` or `!"exact phrase"` — match a card by exact name (case-insensitive).
- `/regex/` may replace quotes for `name:`, `t:`, `o:`, `ft:` — supports `.*?`,
  `(a|b)`, `[ab]`, `\d`, `\w`, `\b`, `^`, `$`. Escape literal `/` as `\/`.

```
!"lightning bolt"        the card Lightning Bolt exactly
o:/^{T}:/ t:creature     creatures that tap with no other cost
```

## Display and uniqueness keywords

- `unique:cards` (default) / `unique:prints` / `unique:art` — duplicate
  handling.
- `order:` — `name`, `cmc`, `power`, `toughness`, `usd`, `eur`, `tix`,
  `rarity`, `color`, `released`, `edhrec`, `artist`, `set`, ...
- `direction:asc` / `direction:desc` — sort direction.

```
!"Lightning Bolt" unique:prints           every printing of Lightning Bolt
f:modern order:rarity direction:asc        Modern cards, commons first
t:dragon order:cmc                         dragons sorted by mana value
```

> **Tip:** the helper script's `--order` and `--dir` flags map to `order:` and
> `direction:`. Prefer passing sort options as flags rather than embedding them
> in the query string.
