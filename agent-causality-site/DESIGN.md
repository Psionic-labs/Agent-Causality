# Agent-Causality — Site Design Notes

## Concept

A retro-futurist **causal monitor**, rebuilt as a causal debugger for AI agents.

The supplied reference stills (kept outside this repo and never shipped) show a curved CRT
monitor with a bright trunk line, fine gold offshoots, orange horizontal thresholds, small
yellow square markers, and a warm sepia-on-brown palette with a deep crimson screen well and
a menu chrome strip above and below the picture. The site borrows that visual language only:
CRT bezels, menu bars, event log tables, phosphor glow, HUD type, threshold lines, and
branching traces.
All artwork is original CSS, SVG, and canvas. No stills, logos, quotes, or show terminology
are used. The single permitted reference to the source of the visual style lives in the
footer credit line.

The monitor metaphor maps directly onto the product:

| Monitor | Agent-Causality |
| --- | --- |
| Silver trunk | Intended agent run |
| Gold branch | Divergent agent path |
| Orange threshold line | Decision baseline |
| Red pruned branch | Root cause attributed and cut |
| Yellow square node | Captured event |

## Palette

| Token | Hex | Role |
| --- | --- | --- |
| `--bg` | `#0e0905` | Page base, near-black warm brown |
| `--bg-deep` | `#090503` | Footer, terminal wells |
| `--panel` | `#171009` | Panels and cards |
| `--panel-2` | `#1f160d` | Raised panels, node buttons |
| `--panel-3` | `#2a1c11` | Hover / selected surface |
| `--text` | `#f3e8d4` | Primary copy, high contrast |
| `--text-soft` | `#d6c7b0` | Body copy |
| `--muted` | `#b6a589` | Secondary copy |
| `--faint` | `#97866e` | Metadata, disabled, credits (raised to clear AA on raised panels) |
| `--amber` | `#f0a63c` | HUD labels, controls, accent |
| `--amber-bright` | `#ffcb78` | Hover, highlighted values |
| `--orange` | `#ff5c26` | Threshold lines, primary CTA |
| `--gold` | `#d9a847` | Divergent branches |
| `--silver` | `#f5eeda` | Intended trunk |
| `--node` | `#ffd35f` | Event square markers |
| `--red` | `#ef4130` | Prune, fault, failure |
| `--line` | `rgba(230, 183, 106, .16)` | Hairline borders |
| `--line-strong` | `rgba(230, 183, 106, .34)` | Active borders |
| `--bezel-1` | `#ddcba5` | Monitor bezel highlight |
| `--bezel-2` | `#b39b6f` | Bezel midtone |
| `--bezel-3` | `#786342` | Bezel shadow |
| Screen crimson | `#221009 → #0b0402` | Monitor screen gradient (canvas) |
| Glass hairline | `rgba(152, 206, 197, .34)` | Teal CRT glass edge line |
| Bar strip | `#45120b → #240905` | Monitor menu/status strips |

Motion, layout, and text tokens: `--ease-out cubic-bezier(.23, 1, .32, 1)`,
`--ease-in-out cubic-bezier(.77, 0, .175, 1)`, `--gutter-page clamp(22px, 5vw, 64px)`,
`--text-body 1.0625rem`.

Contrast: primary and body copy stay at or above WCAG AA on the dark surfaces. Amber is
never used for long-form body copy. Red and gold are paired with text labels or icons, so
meaning is not carried by color alone. Functional UI text has a 13px floor (HUD micro-labels
inside the monitors are the deliberate exception, and they are never load-bearing). Text
opacity is avoided where it costs contrast: terminal output now sits at full opacity, and
`--faint` was raised from `#8c7c65` to `#97866e`.

## Type

- **HUD and headings:** IBM Plex Mono (400 / 500 / 600) — the only webfont. Mono is reserved
  for the hero H1, section H2s, the brand, monitor chrome, and data. Uppercase micro-labels
  use 10–11px with 0.08–0.12em tracking. Headings are sentence case with tight negative
  tracking (`-0.045em` on the H1) and 1.02–1.08 leading.
- **Body:** the native system UI stack, including every card heading. 17px (1.0625rem) at 1.62
  line height, no glow, no tracking, no all-caps, measures capped at 62–66ch.
- **Code:** IBM Plex Mono, 13–14px.

Type scale (fluid where useful):

| Role | Size |
| --- | --- |
| Hero H1 | `clamp(1.95rem, 5.6vw, 5.2rem)` |
| Section H2 | `clamp(1.6rem, 3.4vw, 3rem)` at 27ch |
| Card H3 | `1.0625rem`, system sans |
| Lede | `clamp(1.06rem, 1.35vw, 1.19rem)` at 62ch |
| Body | `1.0625rem` at 1.62 |
| HUD label | `0.625–0.6875rem` |
| Small print | `0.8125rem` (13px floor) |

## Layout

- Max content width: 1180px; page gutter `--gutter-page clamp(22px, 5vw, 64px)`.
- Sections are separated by space, not rules or eyebrows: `padding: clamp(84px, 9.5vw, 152px)`
  and `border-top: 0`. Eyebrows and section numbering were removed in the revamp.
- Hero: two columns above 980px (`minmax(0, 1.06fr) minmax(0, .94fr)`); the H1 spans both
  columns so the sub, CTAs, and meta read as one intro block before the monitor. Mobile order
  is H1, sub, CTAs, meta, monitor.
- Solution: `.instruments` — four `.instrument` blocks in a 2×2 grid above 720px, one column
  below. Each header is a single `.instrument-head` line rather than a nested card head.
- How-it-works: `.moments` — three `.moment` editorial rows (tag, heading, copy) instead of
  numbered cards. On desktop the timeline is a 4-column grid with the head/foot chrome hidden,
  so no horizontal scrolling is required; 2 columns at 700–1019px, 1 column below.
- Demo: graph plus event inspector above 1020px; graph can scroll horizontally on narrow
  screens, inspector stacks underneath. Nodes are real `<button>` elements.
- Video: 16:9 screen inside the same monitor family as the hero, with a local raster poster
  (`media/explorer-poster.png`, 1280×720) instead of a drawn SVG facade.

## Component rules

### Monitor
- Warm beige bezel with a curved silhouette: large asymmetric radii, inset top highlight,
  bottom shadow, small feet, vent dots, status lamp, and a maker plate.
- Menu chrome: a dark red strip on top of the bezel with a red unit chip, desk label, and a
  blinking REC dot; a matching strip below the screen with the unit chip and generic terminal
  menu words (FILE EDIT VIEW MODE HELP). The menu words are period chrome, not navigation.
- Screen: deep crimson brown, strong inner vignette, curved edge radius, subtle glass glare,
  and a 1px teal glass line tracing the screen edge.
- Screen is split: the timeline window on top, an event log table below. The log replays the
  same eight-event demo trace as the explorer section, newest row flashing, oldest rolling
  off. Columns: Events / Time / Node / Event.
- Scanlines: 2–3px repeating gradient at low opacity, only on screens and only behind text
  overlays. A slow refresh sweep may run on the hero; disabled for reduced motion.
- HUD overlays sit at screen corners in mono caps. They are decorative (`aria-hidden`) and
  never overlap important graphics.

### Branch graphics
- Trunk: 3–4 concentric strokes (wide low-alpha glow, narrow silver core) for phosphor bloom.
- Branches: thin gold strokes; crossing an orange threshold promotes the stroke to red.
- Pruned branch: strokes clip back with a short fray and dim before respawning.
- Nodes: small axis-aligned yellow squares, gently pulsing. No circles as event markers.
- Thresholds: horizontal orange lines at fixed screen percentages.

### Cards and panels
- Two card families, both on dark warm surfaces with a 1px hairline border and 2–4px radius
  (never pill-shaped): `.instruments`/`.instrument` for the solution grid and
  `.moments`/`.moment` for the editorial rows. No section numbers, no nested card heads.
- One amber top edge or inset line. Hover raises the border brightness, not the element.
- Mini-visuals are decorative SVG/CSS and may glow; explanatory paragraphs never do.
- Live monitor fragments carry `data-ui` (hero monitor, video monitor, trace figure, explorer,
  terminal). Everything inside them is illustrative chrome and exempt from prose checks.

### Buttons
- System sans, sentence case, 15px, flat 2px radius, no glow, minimum 44px hit area.
- Primary: orange fill with dark text. Ghost: transparent with amber hairline. Tertiary: text
  link with an arrow.
- `:active` scales to .97 for press feedback. Hover styling is gated behind
  `@media (hover: hover) and (pointer: fine)` so touch devices never keep a stuck hover state.
- Focus: visible 2px amber outline with 3px offset, never removed.

### Interactive graph
- Edges drawn beneath HTML node buttons; center points match percentage positions.
- Default edges are low-contrast silver/gold. Selected ancestry is bright amber.
  Non-ancestors dim to 35% opacity.
- Fault nodes carry a literal `FAULT INJECTED` label plus red styling.
- The inspector always names agent, event, inputs, provenance, and parents. Attribution is a
  separate labeled block so it never reads as a raw field.

### Terminal
- Deep well inside a panel, title bar with status, `$` prompts in amber, commands in body
  mono, output notes in muted gold. Copy button stays outside the scrolling code area.

## Motion

- Motion is confined to the hero monitor, the small live LED, and scroll-triggered state.
- Hero loop: ~12s. Branch growth 45%, threshold crossing, red prune, rest, respawn.
- Event log advances one row per ~0.92s so a full eight-event trace cycles in ~7.4s, in step
  with the branch animation cycle.
- Motion must communicate state: growth = capture, red = prune, pulse = active event,
  a new log row = a captured event.
- Section entrance: `.reveal` — blocks start at `opacity: 0` and rise 18px into place over
  620ms on `--ease-out`, staggered `min(index, 3) × 70ms`, fired once by an IntersectionObserver
  (threshold .15). Skipped entirely under reduced motion.
- `prefers-reduced-motion: reduce` keeps the hero monitor animating (it is the product's
  signature explanation), but disables the refresh sweep and other decorative CSS motion.
  Interactive state changes remain instant and fully usable.
- Mobile simplifies the canvas: fewer branches, lower DPR cap, no soft glow layers.

## Content and accessibility rules

- Plain English first. The hero pitch is under 15 words; every explanation is readable
  without theme knowledge.
- Feature claims come from the project README and docs only. No invented capabilities.
- HUD vocabulary stays inside the real system's terms (events, causal parents, baselines,
  provenance, replays, adapters) — no invented metrics or instrument names.
- Semantic landmarks, one H1, ordered headings, skip link, descriptive labels, alt/role text
  for figures, and keyboard-operable demo nodes and timeline controls.
- External requests: one Google Fonts stylesheet, and the YouTube iframe only after the user
  presses play. The facade and OG image are local original artwork.
- No show names, terminology, or branding anywhere except the exact footer credit line.
