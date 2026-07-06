#!/usr/bin/env python3
"""
IPS Web — índice de precios a partir de las tiendas online (CIET).

A diferencia del IPS-SEPA (lo que las cadenas declaran al Estado), este índice
usa el precio que se paga comprando online. Incluye cadenas que no reportan bien
a SEPA (Comodín, ChangoMás). Consulta las APIs de catálogo VTEX por código EAN,
geolocalizado en Tucumán donde la tienda lo permite.

Uso:
    python3 fetch_web_index.py [--muestra N] [--catalogo data/productos.json]

Relevamiento de baja intensidad (una consulta por producto y cadena, con pausa)
sobre endpoints públicos. Sin uso comercial.
"""
import argparse
import json
import statistics
import sys
import time
import urllib.request
import urllib.parse
from collections import defaultdict
from pathlib import Path

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126 Safari/537.36")
CP_TUCUMAN = "4000"

# nombre para mostrar -> dominio de la tienda online (todas VTEX)
TIENDAS = {
    "Carrefour": "www.carrefour.com.ar",
    "Vea": "www.vea.com.ar",
    "Jumbo": "www.jumbo.com.ar",
    "Comodín": "www.comodinencasa.com.ar",
    "ChangoMás": "www.masonline.com.ar",
}
# cadenas que forman el índice (canasta = intersección de estas)
PRINCIPALES = ["Carrefour", "Vea", "Jumbo", "Comodín", "ChangoMás"]


def get(url, intentos=2):
    for i in range(intentos):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.load(r)
        except Exception:
            if i == intentos - 1:
                return None
            time.sleep(0.8)
    return None


def region_id(dominio):
    d = get(f"https://{dominio}/api/checkout/pub/regions/?country=ARG&postalCode={CP_TUCUMAN}")
    if isinstance(d, list) and d:
        return d[0].get("id")
    return None


def precio_por_ean(dominio, ean, region):
    q = urllib.parse.quote(f"alternateIds_Ean:{ean}")
    url = f"https://{dominio}/api/catalog_system/pub/products/search?fq={q}"
    if region:
        url += f"&regionId={urllib.parse.quote(region)}"
    d = get(url)
    if not isinstance(d, list) or not d:
        return None
    prod = d[0]
    item = next((it for it in prod.get("items", []) if it.get("ean") == ean),
                (prod.get("items") or [None])[0])
    if not item:
        return None
    ofertas = [s.get("commertialOffer", {}) for s in item.get("sellers", [])]
    ofertas = [o for o in ofertas if o.get("Price")]
    if not ofertas:
        return None
    mejor = min(ofertas, key=lambda o: o["Price"])
    return {"precio": round(mejor["Price"], 2), "link": prod.get("link")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--muestra", type=int, default=400)
    ap.add_argument("--catalogo", default="data/productos.json")
    ap.add_argument("-o", "--salida", default="data/web_index.json")
    args = ap.parse_args()

    cat = json.loads(Path(args.catalogo).read_text(encoding="utf-8"))
    productos = cat["productos"]
    if args.muestra and args.muestra < len(productos):
        paso = len(productos) / args.muestra
        idx = sorted({int(i * paso) for i in range(args.muestra)})
        muestra = [productos[i] for i in idx]
    else:
        muestra = productos

    print("Resolviendo regiones (Tucumán)…", file=sys.stderr)
    regiones, geoloc = {}, {}
    for n, dom in TIENDAS.items():
        r = region_id(dom)
        regiones[n] = r
        geoloc[n] = bool(r)
        print(f"  {n}: {'Tucumán' if r else 'precio online nacional'}", file=sys.stderr)

    # precios por cadena por EAN
    precios = defaultdict(dict)   # cadena -> ean -> precio
    links = defaultdict(dict)
    desc = {}
    total = len(muestra)
    for i, p in enumerate(muestra, 1):
        ean = p["ean"]
        desc[ean] = p["descripcion"]
        for n, dom in TIENDAS.items():
            res = precio_por_ean(dom, ean, regiones[n])
            if res:
                precios[n][ean] = res["precio"]
                links[n][ean] = res["link"]
            time.sleep(0.18)
        if i % 25 == 0 or i == total:
            hall = {n: len(precios[n]) for n in TIENDAS}
            print(f"  {i}/{total} · hallados {hall}", file=sys.stderr)

    # canasta: intersección de las cadenas con buena cobertura (>=25% de la
    # muestra). Las de cobertura parcial se muestran igual, sin costo de canasta.
    umbral = max(15, int(0.25 * total))
    presentes = [n for n in PRINCIPALES if len(precios[n]) >= umbral]
    if len(presentes) < 2:
        # fallback: las 2 con más cobertura
        presentes = sorted(PRINCIPALES, key=lambda n: -len(precios[n]))[:2]
    canasta = set(precios[presentes[0]])
    for n in presentes[1:]:
        canasta &= set(precios[n])
    canasta = sorted(canasta)

    resumen = []
    for n in TIENDAS:
        en_canasta = [e for e in canasta if e in precios[n]]
        costo = round(sum(precios[n][e] for e in en_canasta), 2) if n in presentes and en_canasta else None
        resumen.append({
            "cadena": n,
            "geolocalizado": geoloc[n],
            "productos_hallados": len(precios[n]),
            "en_indice": n in presentes,
            "canasta_costo": costo,
        })
    resumen.sort(key=lambda x: (x["canasta_costo"] is None, x["canasta_costo"] or 0))

    def brecha(ean):
        ps = [precios[n][ean] for n in presentes if ean in precios[n]]
        return round(max(ps) / min(ps), 3) if len(ps) >= 2 else 1

    prod_out = []
    for ean in sorted(canasta, key=brecha, reverse=True):
        pr = {n: precios[n][ean] for n in presentes if ean in precios[n]}
        lk = {n: links[n].get(ean) for n in presentes if ean in precios[n]}
        vals = list(pr.values())
        prod_out.append({
            "ean": ean, "descripcion": desc.get(ean, ean)[:80],
            "precios": pr, "links": lk,
            "min": min(vals), "max": max(vals), "brecha": round(max(vals) / min(vals), 3),
        })

    out = {
        "fecha": time.strftime("%Y-%m-%d"),
        "fuente": "Tiendas online (VTEX) de supermercados con venta en Tucumán.",
        "cadenas": PRINCIPALES,
        "geolocalizado": geoloc,
        "canasta_n": len(canasta),
        "muestra": total,
        "resumen": resumen,
        "productos": prod_out,
    }
    Path(args.salida).write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"OK → {args.salida} ({len(canasta)} en canasta, {len(presentes)} cadenas)",
          file=sys.stderr)


if __name__ == "__main__":
    main()
