# CIET — Centro de Investigación Económica de Tucumán

Sitio del CIET, centro independiente de investigación y divulgación económica centrado en Tucumán. Publicado en https://cietucuman.github.io/ciet/

Trabaja con precios **públicos** de las tiendas online de los supermercados de Tucumán (Carrefour, Vea, Jumbo, Comodín, ChangoMás y Tuchanguito), con metodología abierta. No requiere cuentas ni credenciales.

## Productos

### 1. Buscador de precios — `buscador.html`

Escribís un producto y ves dónde está más barato online en Tucumán, con el link para comprarlo. `scripts/fetch_buscador.py` recorre una lista amplia de términos en cada cadena (VTEX + Tuchanguito), geolocaliza en Tucumán donde se puede (simulación de checkout) y agrupa el mismo producto entre cadenas (por EAN y por similitud de nombre). Produce `buscador.json`, que la página busca del lado del navegador.

### 2. Índice de Precios de Yerbas — `yerba.html`

Índice temporal del precio de la **yerba mate de 1 kg** (todas las marcas) en los súper de Tucumán, con desglose total (cada yerba, cada cadena, cada día).

- `scripts/build_indice_yerba.py` — lee las capturas crudas diarias y calcula un índice de **Jevons encadenado** (media geométrica de las variaciones de cada yerba en cada cadena, sobre items presentes en dos días consecutivos). Base 100 el primer día. Emite `indice.json` con el índice, la serie por producto×cadena y stats diarias.
- `scripts/actualizar_yerba.sh` — captura del día (reusa `fetch_buscador.py --terminos yerba`) + recálculo. Para correr a mano.
- La serie **arranca desde el primer día de medición** y se acumula (no hay histórico previo).

## Estructura

- `index.html` — portada (hub de acceso a los productos).
- `buscador.html`, `yerba.html` — las páginas de cada producto.
- `scripts/` — pipeline de datos en Python + scripts de automatización.
- `data/` — salidas locales de los scripts. **No se versionan en `main`** (ver más abajo).

## Datos y ramas

El código y las páginas viven en `main` (que es lo que sirve GitHub Pages). Los **datos** viven en ramas aparte y las páginas los leen vía `raw.githubusercontent.com`:

- Rama **`datos`** — huérfana, se **force-pushea** (siempre 1 commit, sin historia). Contiene `buscador.json`.
- Rama **`yerba-datos`** — **acumula** (commits normales, para no perder el histórico). Contiene `crudo/AAAA-MM-DD.json` (captura diaria) e `indice.json`.

## Automatización

Corre **local** (los servidores de datos oficiales bloquean IPs de datacenter, así que no se puede en la nube). Una tarea `launchd` (`com.ciet.serie`) ejecuta `~/.ciet-run.sh` varias veces al día: scrapea y publica el buscador, y **1×/día** captura la yerba y la publica en `yerba-datos`. Setup de la parte de yerba: `scripts/setup_yerba_automatizacion.sh` (una vez).

## Publicar cambios

```bash
git add -A && git commit -m "..." && git push
```

GitHub Pages sirve la rama `main` (raíz) automáticamente en ~1 minuto.
