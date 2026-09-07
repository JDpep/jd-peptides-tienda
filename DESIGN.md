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
| `--gold-rgb` | `199, 154, 58` | El mismo dorado para `rgba(var(--gold-rgb), α)` |
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

### Un solo dorado

Hubo dos golds conviviendo: `#c9a227` (155 usos) y el token `#c79a3a`. Todo
está unificado al token. **Nunca escribas el hex a mano**, con una excepción:
los atributos de presentación de SVG (`fill=`, `stroke=`, `stop-color=`) no
aceptan `var()` — el navegador los descarta en silencio y el icono se pinta
negro. Ahí va `#c79a3a` literal. Lo mismo en `<canvas>` (Chart.js): lee el
token con `getComputedStyle` y pásale el valor ya resuelto.

### Strategy

**Restrained** on product/admin surfaces (catalog, checkout, dashboard). Gold ≤10% of viewport.
**Committed** on home hero + category landings. Gold can carry 30% via headline, CTA, and accents.
Never **drenched** — would cheapen.

## Typography

### Fonts (loaded from Google Fonts)

- **Display**: `Fraunces` — h1–h5 y wordmark. La italic a tamaño grande se
  reserva para énfasis de una palabra (`.serif-italic`), no para párrafos.
- **Body**: `Inter Tight` — párrafos, etiquetas de UI, botones.
- **Mono**: `JetBrains Mono` — dato técnico: SKU, dosis, peso molecular, lote.

Tokens: `--font-display`, `--font-body`, `--font-mono`. No escribas el nombre
de la familia a mano.

> Space Grotesk + Inter fue la pareja original; el sitio ya no las carga.
> Si encuentras `font-family: 'Space Grotesk'` en algún sitio, es código
> muerto que cae a la sans del sistema.

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
- `.prebuy` / `.prebuy-row` — bloque "Antes de comprar" de la home (lista de
  definición asimétrica; sustituyó a la rejilla de tres tarjetas iguales)
- `.detail-coa` — acceso al certificado de análisis en la ficha de producto
- `.about-block` — bloque de lectura de "Sobre nosotros"
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

## Animaciones de entrada y no-JS

Las clases `.reveal`, `.reveal-left`, `.reveal-right` y `.product-card`
arrancan en `opacity: 0` y las enciende un `IntersectionObserver`. **Ese
estado oculto está detrás de `html.js`**, una clase que un script inline en
`<head>` pone antes de pintar. Sin JS no se oculta nada y la página se ve
entera. Si añades una animación de entrada nueva, cuélgala también de `.js`
o dejarás contenido invisible cuando el JS falle.

## Repetir el mensaje

El fallo más caro de este sitio no fue visual: era decir lo mismo a todas las
alturas. "Calidad y trazabilidad por lote" llegó a aparecer seis veces en la
home (marquee, hero, sección de calidad, tira de estadísticas, pilares y
bullets de nosotros) y el aviso RUO tres veces en una ficha de producto.

Regla: **cada afirmación se hace una vez, en el lugar donde decide algo.**
Si hace falta repetirla por motivo legal, se consolida (una visible + el
texto completo en `<details>`), no se duplica. Antes de añadir un bloque,
busca si esa frase ya está en la página.

## Don'ts

- No emoji as iconography. Los iconos son SVG de trazo, 24x24, `stroke-width` 1.7–1.9, `stroke="currentColor"`. (✓ y ✕ dentro del texto están bien.)
- No side-stripe (`border-left: 3px`) accents on cards/alerts. Use full borders or background tints.
- No gradient text. Solid color, emphasis by weight or size.
- No identical pillar-of-three card grids without rhythm variation.
- Nada de QR, sellos o certificados decorativos que aparenten ser verificables sin serlo. En esta marca eso resta confianza en vez de darla.
- No inventes lotes, purezas ni fechas de análisis para rellenar un hueco: la base no guarda ese dato por producto.
- No "ONLY 2 LEFT!" pseudo-scarcity.
