#!/usr/bin/env python3
"""
Buscador de precios (CIET) — catálogo amplio de las tiendas online de Tucumán.

Recorre una lista amplia de términos de búsqueda en cada cadena (VTEX) y baja
los productos (nombre, marca, precio, link), geolocalizado en Tucumán donde se
puede. Produce data/buscador.json, que el sitio busca del lado del navegador.

Uso:
    python3 fetch_buscador.py [--tope 150] [-o data/buscador.json]
"""
import argparse
import json
import sys
import time
import urllib.request
import urllib.parse
from pathlib import Path

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126 Safari/537.36")
CP = "4000"
TIENDAS = {
    "Carrefour": "www.carrefour.com.ar",
    "Vea": "www.vea.com.ar",
    "Jumbo": "www.jumbo.com.ar",
    "Comodín": "www.comodinencasa.com.ar",
    "ChangoMás": "www.masonline.com.ar",
}

TERMINOS = [
    # almacén
    "arroz", "fideos", "aceite", "aceite de oliva", "harina", "harina leudante",
    "azucar", "sal", "yerba", "mate cocido", "cafe", "cafe instantaneo", "te",
    "cacao", "mermelada", "dulce de leche", "miel", "polenta", "pure de papas",
    "lentejas", "porotos", "garbanzos", "arvejas", "choclo", "tomate perita",
    "salsa de tomate", "pure de tomate", "atun", "caballa", "sardina",
    "aceitunas", "mayonesa", "ketchup", "mostaza", "vinagre", "caldo", "sopa",
    "gelatina", "flan", "postre", "galletitas", "galletitas dulces",
    "galletitas de agua", "tostadas", "pan lactal", "budin", "alfajor",
    "chocolate", "caramelos", "chicles", "papas fritas", "palitos", "mani",
    "frutos secos", "cereales", "avena", "granola", "barritas de cereal",
    "arroz integral", "salvado", "condimentos", "oregano", "pimienta",
    "aderezos", "escabeche", "picadillo", "leche condensada",
    # lácteos
    "leche", "leche descremada", "leche en polvo", "yogur", "yogur bebible",
    "queso", "queso cremoso", "queso rallado", "queso untable", "manteca",
    "margarina", "crema de leche", "ricota", "postre lacteo",
    # bebidas
    "gaseosa", "coca cola", "agua mineral", "agua saborizada", "jugo",
    "jugo en polvo", "cerveza", "vino", "vino tinto", "fernet", "aperitivo",
    "energizante", "isotonica", "soda", "gaseosa lima limon", "amargo",
    "whisky", "vodka", "gin", "sidra", "champagne",
    # congelados
    "helado", "hamburguesa", "milanesa de soja", "nuggets", "papas congeladas",
    "verduras congeladas", "pizza congelada", "medallon",
    # frescos / carnes / fiambres
    "pollo", "carne picada", "milanesa", "jamon", "jamon cocido", "salame",
    "mortadela", "salchicha", "chorizo", "queso de maquina", "huevos",
    "pan", "prepizza", "tapa empanada", "tapa tarta", "ravioles", "ñoquis",
    # frutas y verduras
    "banana", "manzana", "naranja", "papa", "cebolla", "tomate", "lechuga",
    "zanahoria", "limon", "zapallo", "morron",
    # limpieza
    "detergente", "lavandina", "jabon en polvo", "jabon liquido ropa",
    "suavizante", "limpiador", "limpiador de piso", "lustramuebles",
    "desodorante de ambiente", "insecticida", "papel higienico",
    "rollo de cocina", "servilletas", "esponja", "bolsas de residuo",
    "film", "papel aluminio", "trapo de piso", "escoba", "cif", "desengrasante",
    # perfumería / higiene
    "shampoo", "acondicionador", "jabon de tocador", "crema corporal",
    "desodorante", "pasta dental", "cepillo dental", "enjuague bucal",
    "espuma de afeitar", "maquina de afeitar", "toallitas femeninas",
    "protectores diarios", "algodon", "hisopos", "alcohol en gel",
    "crema de enjuague", "gel de ducha",
    # bebé
    "pañales", "toallitas humedas", "leche infantil", "papilla", "oleo calcareo",
    # mascotas
    "alimento perro", "alimento gato", "arena para gatos",
    # otros
    "pilas", "encendedor", "velas", "fosforos", "servilletas de papel",
]


def get(url, intentos=2):
    for i in range(intentos):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.load(r)
        except Exception:
            if i == intentos - 1:
                return None
            time.sleep(0.6)
    return None


def region_id(dom):
    d = get(f"https://{dom}/api/checkout/pub/regions/?country=ARG&postalCode={CP}")
    return d[0].get("id") if isinstance(d, list) and d else None


def limpiar_nombre(n):
    """Nombre legible: colapsa espacios y baja el TODO-MAYÚSCULAS a Título."""
    n = " ".join((n or "").split())
    letras = [c for c in n if c.isalpha()]
    if letras and sum(c.isupper() for c in letras) / len(letras) > 0.75:
        n = n.title()
    return n[:90]


def productos_termino(dom, termino, region, tope):
    out, frm = [], 0
    ft = urllib.parse.quote(termino)
    while frm < tope:
        url = (f"https://{dom}/api/catalog_system/pub/products/search"
               f"?ft={ft}&_from={frm}&_to={frm+49}")
        if region:
            url += f"&regionId={urllib.parse.quote(region)}"
        d = get(url)
        if not isinstance(d, list) or not d:
            break
        for p in d:
            try:
                item = p["items"][0]
                o = item["sellers"][0]["commertialOffer"]
                precio = o.get("Price")
                # sólo productos realmente comprables (como los ve un humano)
                disponible = o.get("IsAvailable") and (o.get("AvailableQuantity") or 0) > 0
                if not precio or precio < 100 or not disponible:
                    continue
                prod = {
                    "n": limpiar_nombre(p.get("productName", "")),
                    "m": (p.get("brand") or "")[:28],
                    "e": item.get("ean") or "",
                    "p": round(precio, 2),
                    "l": p.get("link") or "",
                    "i": (item.get("images") or [{}])[0].get("imageUrl") or "",
                }
                # oferta: precio de lista mayor, pero con descuento realista (<=60%)
                lista = o.get("ListPrice") or 0
                if precio * 1.03 < lista <= precio * 2.5:
                    prod["op"] = round(lista, 2)
                out.append(prod)
            except Exception:
                continue
        if len(d) < 50:
            break
        frm += 50
        time.sleep(0.07)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tope", type=int, default=150, help="máx productos por término")
    ap.add_argument("-o", "--salida", default="data/buscador.json")
    args = ap.parse_args()

    # agrupar por producto: clave = código de barras (o link si no tiene).
    # cada grupo junta el precio de todas las cadenas que lo tienen.
    grupos = {}
    geoloc = {}
    for nombre, dom in TIENDAS.items():
        region = region_id(dom)
        geoloc[nombre] = bool(region)
        print(f"{nombre}: geoloc={'sí' if region else 'no'}", file=sys.stderr)
        cuenta = 0
        for i, term in enumerate(TERMINOS, 1):
            for pr in productos_termino(dom, term, region, args.tope):
                clave = pr["e"] or pr["l"]
                if not clave:
                    continue
                g = grupos.get(clave)
                if g is None:
                    g = grupos[clave] = {"n": pr["n"], "m": pr["m"], "i": pr.get("i", ""), "pr": {}}
                if not g["i"] and pr.get("i"):
                    g["i"] = pr["i"]
                oferta = [pr["p"], pr["l"]]
                if "op" in pr:
                    oferta.append(pr["op"])
                g["pr"][nombre] = oferta
            if i % 30 == 0:
                cuenta = sum(1 for gg in grupos.values() if nombre in gg["pr"])
                print(f"  {nombre}: {i}/{len(TERMINOS)} términos · {cuenta} productos", file=sys.stderr)
        cuenta = sum(1 for gg in grupos.values() if nombre in gg["pr"])
        print(f"  {nombre}: {cuenta} productos", file=sys.stderr)

    cadenas_meta = {n: {"geolocalizado": geoloc[n],
                        "productos": sum(1 for g in grupos.values() if n in g["pr"])}
                    for n in TIENDAS}
    productos = [{"n": g["n"], "m": g["m"], "i": g["i"], "pr": g["pr"]} for g in grupos.values()]
    en_varias = sum(1 for g in grupos.values() if len(g["pr"]) > 1)
    out = {
        "fecha": time.strftime("%Y-%m-%d"),
        "cadenas": cadenas_meta,
        "total": len(productos),
        "en_varias_cadenas": en_varias,
        "productos": productos,
    }
    Path(args.salida).write_text(
        json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"OK → {args.salida} ({len(productos)} productos)", file=sys.stderr)


if __name__ == "__main__":
    main()
