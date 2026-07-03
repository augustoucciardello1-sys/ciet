# CIET — Centro de Investigación Económica de Tucumán

Sitio del CIET, centro independiente de investigación y divulgación económica centrado en Tucumán. Publicado en https://augustoucciardello1-sys.github.io/ciet/

## Producto insignia: Índice de Precios de Supermercados de Tucumán (IPS)

Seguimiento de precios de supermercados con sucursales en Tucumán a partir del dataset abierto **SEPA** (Sistema Electrónico de Publicidad de Precios Argentinos, Secretaría de Comercio):

1. Descarga diaria del dump SEPA (datos oficiales informados por las cadenas, por sucursal).
2. Filtro de sucursales de la provincia de Tucumán.
3. Canasta fija de productos idénticos (mismo EAN) presentes en todas las cadenas.
4. Cálculo del índice (evolución temporal) y comparativa de canasta entre cadenas.

El pipeline vive en `scripts/` y los datos procesados en `data/` (los dumps crudos de SEPA no se versionan).

## Estructura

- `index.html` — portada del sitio.
- `ips/` — página del índice (metodología + visualizaciones).
- `scripts/` — pipeline de datos en Python.
- `data/` — series procesadas (JSON/CSV chicos) que consume la página.

## Publicar cambios

```bash
git add -A && git commit -m "..." && git push
```

GitHub Pages sirve la rama `main` (raíz) automáticamente en ~1 minuto.
