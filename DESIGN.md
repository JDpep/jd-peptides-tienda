# JD Peptides — Design System

## Color

Warm dark with gold accent. Inspired by aged bourbon glass + lab amber. All neutrals tinted toward the gold hue (h ≈ 50, low chroma).

### Tokens (CSS variables in `style.css`)

| Token | Hex | Use |
|---|---|---|
| `--bg`   | `#0a0906` | Primary surface (warm near-black) |
| `--bg2`  | `#100e09` | Secondary surface (sections) |
| `--bg3`  | `#17140f` | Cards, inputs |
| `--bg4`  | `#1e1b14` | Elevated cards |
| `--border` | `#2c281e` | All hairlines |
| `--gold` | `#c79a3a` | Brand accent — buttons, highlights, gold text |
| `--gold-light` | `#e8c873` | Hover state for gold |
| `--gold-dark` | `#8c6a1f` | Pressed state, deep gold band |
| `--champagne` | `#f4e4b5` | Light-mode about section, paper backgrounds |
| `--text` | `#ede9e0` | Primary text (warm off-white) |
| `--text2` | `#9a9080` | Secondary text |
| `--text3` | `#524d3e` | Tertiary (dates, metadata) |
| `--green` `--red` `--orange` | functional | Stock states, errors |

### Category accents

Used only on category badges, never as primary surface tint:
- Recuperación → `--cat-recuperacion` (navy `#0a2540`)
- Performance → `--cat-performance` (steel `#1f4f6b`)
- Anti-aging → `--cat-antiaging` (lab green `#2f5d3a`)
- Pérdida de Peso → `--cat-perdida` (gold `#c79a3a`)
- Bienestar → `--cat-bienestar` (purple `#5b3570`)

### Strategy

**Restrained** on product/admin surfaces (catalog, checkout, dashboard). Gold ≤10% of viewport.
**Committed** on home hero + category landings. Gold can carry 30% via headline, CTA, and accents.
Never **drenched** — would cheapen.

## Typography

### Fonts (loaded from Google Fonts)

- **Display**: `Space Grotesk` (400, 500, 600, 700). Used for h1–h5 and logo wordmark.
- **Body**: `Inter` (400, 500, 600). Used for paragraphs, UI labels, buttons.
- **Tabular**: Inter with `font-variant-numeric: tabular-nums` (must add) for prices.

### Scale (clamp-based for fluid responsive)

| Level | Range | Use |
|---|---|---|
| h1 | `clamp(2rem, 5vw, 3.5rem)` | Page titles, hero |
| h2 | `clamp(1.5rem, 3vw, 2.2rem)` | Section headers |
| h3 | 1.25rem | Card titles |
| h4 | 0.8rem uppercase tracked | Eyebrow labels |
| body | 0.95rem (15px base) | Paragraphs |
| small | 0.82rem | Metadata, captions |
| micro | 0.7rem uppercase tracked | Badges, tags |

Min ratio 1.25 between adjacent steps.

### Body line length

Cap at 65–75ch on prose-heavy pages (FAQ, Privacy, Terms, Info center).

## Elevation

Two levels only.
- **Surface**: `var(--shadow)` = `0 4px 24px rgba(0,0,0,0.55)`
- **Glow**: `var(--shadow-gold)` = `0 0 24px rgba(199,154,58,0.3)` — used on gold buttons hover, never on cards (too disco).

No glassmorphism. The marquee bar and navbar use `backdrop-filter: blur(16px)` over near-opaque backgrounds — legitimate sticky-bar usage.

## Border radius

- `--radius` = 8px — buttons, inputs
- `--radius-lg` = 14px — cards, modals

Pills/badges use 4px or 999px. Never mix radii within a single component.

## Motion

- Transitions: 200–250ms ease-out (default `var(--transition)` = 0.25s).
- Reveal-on-scroll: y-translate 16px + opacity, ease-out-quart.
- No bounce, no elastic, no layout property animation.
- Card hover: 1px translateY lift + border color shift, no scale.

## Component library

The store has a working component vocabulary in `static/css/style.css`. Use it instead of reinventing:

- `.btn` + variants (`-gold`, `-outline`, `-ghost`, `-sm`, `-lg`, `-block`, `-danger`)
- `.badge` + variants (`-gold`, `-green`, `-red`, `-orange`, `-gray`)
- `.product-card` — the canonical product unit (visual + body + footer)
- `.pillar-card` — feature/value-prop cards
- `.flash` — toast notifications (top-right slide-in)
- `.cq-*` — calidad section composition pieces
- `.tag-chip` `.stock-badge` `.ruo-badge` — inline metadata

## Critical conventions

1. **Vial photos are 320×533** (aspect 3:5) in cards. PNG with transparent background.
2. **Prices**: `${{price}} <span class="price-currency">MXN</span>` — currency in small, muted.
3. **RUO disclaimer**: must appear on every product detail page + checkout + footer.
4. **Stock badges**: ok/low/out — colored dot + label, never just color.
5. **`fetchpriority="high"`** on first 3 above-the-fold product images.
6. **`loading="lazy" decoding="async"`** below the fold.

## Don'ts

- No emoji as iconography in the main UI surface (✓ in inline copy is fine, decorative emoji in pillar cards is not).
- No side-stripe (`border-left: 3px`) accents on cards/alerts. Use full borders or background tints.
- No gradient text. Solid color, emphasis by weight or size.
- No identical pillar-of-three card grids without rhythm variation.
- No "ONLY 2 LEFT!" pseudo-scarcity.
