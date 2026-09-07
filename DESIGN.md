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

1. **La caja de foto de la tarjeta es 2:3**, que es la proporción exacta de
   las fotos reales (733×1100): `object-fit: cover` no recorta nada. En
   teléfono baja a 4:5 para que quepan más productos por pantallazo. Las
   cuatro fotos apaisadas (BBKG80, Cagrilintide, RT10, TB-500) sí se
   recortan, y está bien: el vial está centrado y el recorte lo deja al
   mismo tamaño aparente que los verticales.
2. **Prices**: `${{price}} <span class="price-currency">MXN</span>` — currency in small, muted.
3. **RUO disclaimer**: must appear on every product detail page + checkout + footer.
4. **El estado de stock solo se pinta cuando dice algo**: quedan pocas, o
   agotado. "En stock" en las 24 tarjetas eran 24 pastillas verdes idénticas
   que no informaban de nada. Y va **sobre la foto**, no en el cuerpo: dentro
   del cuerpo solo lo llevan algunas tarjetas, y esa fila de más subía su
   precio respecto al de las vecinas de la misma hilera. En una rejilla los
   precios tienen que leerse en línea. Punto de color + etiqueta, nunca solo
   color.
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


## `[hidden]` tiene que ganar

`display: none` viene de la hoja del navegador, así que **cualquier** regla
propia con `display: flex/grid/block` lo pisa por especificidad. Pasó de
verdad: `.catalog-active-chips` se pintaba como una barra vacía de 852×23 con
borde dorado encima de la rejilla del catálogo, en cada carga, con el atributo
puesto. Hay una guarda global `[hidden] { display: none !important }` al
principio de `style.css`. No la quites.

## `var(--gold)` dentro de `.paper` es para TEXTO, no para rellenos

`.paper` remapea `--gold` a `--gold-on-light` (#8c6a1f) para que el dorado sea
legible sobre crema. Un componente que use `var(--gold)` como **fondo** en esa
superficie acaba con el mismo color en fondo y en texto, porque `.paper a`
también pinta `--gold-on-light`. Le pasó a `.about-cta-primary`: un rectángulo
bronce vacío, 1.00:1, en la home. Todo componente que pinte fondo dorado sobre
superficie clara tiene que fijar sus **dos** colores a la vez.

## Barra de compra fija (ficha, teléfono)

`.pdp-buybar` aparece cuando el botón de la ficha sale de vista y desaparece
cuando vuelve, vía `IntersectionObserver`: nunca hay dos botones de compra en
pantalla a la vez. Sin JS se queda oculta — la ficha ya tiene el suyo. Sube el
botón de WhatsApp y añade `padding-bottom` al `body` para no tapar el pie.

## Errores de formulario

El aviso flotante de arriba a la derecha (`.flash`) se borra solo a los 4
segundos y no dice qué campo falla: sirve para confirmaciones, no para
validación. El checkout devuelve `{field, message}` desde
`_validate_checkout_fields` y pinta el error **anclado al campo**
(`.field-error` + `aria-invalid` + `aria-describedby`), lleva el foco ahí y
conserva lo que ya estaba escrito. Cualquier formulario nuevo va igual.

## Áreas táctiles

44px mínimo en los controles principales, medido con emulación táctil a 390px
(no a ojo: el menú era de 35×27). Donde el icono no debe crecer —los botones
sobre la foto de la tarjeta, que a 165px de ancho taparían el vial— se deja el
tamaño visible y se agranda solo la zona sensible con `::after { inset: -7px }`.
