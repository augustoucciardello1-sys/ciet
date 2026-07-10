#!/usr/bin/env python3
"""
Detector de duplicados por IMAGEN (herramienta de análisis, se corre a demanda).

Descarga la foto de cada producto del buscador, calcula un hash perceptual, y
busca pares de productos de cadenas distintas con la MISMA foto que hoy no están
agrupados (por nombre distinto). La salida es una lista de candidatos para revisar
y cargar en ALIAS_CADENAS de fetch_buscador.py. No modifica nada.

Uso: python3 scripts/detectar_duplicados.py [buscador.json] [--umbral 10]
"""
import argparse
import concurrent.futures
import io
import json
import re
import sys
import unicodedata
import urllib.request
from collections import defaultdict

from PIL import Image

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126 Safari/537.36")


def dhash(data, size=8):
    im = Image.open(io.BytesIO(data)).convert("L").resize((size + 1, size))
    px = list(im.getdata())
    bits = 0
    for r in range(size):
        for c in range(size):
            bits = (bits << 1) | (1 if px[r * (size + 1) + c] > px[r * (size + 1) + c + 1] else 0)
    return bits


def ham(a, b):
    return bin(a ^ b).count("1")


def _norm(s):
    return "".join(c for c in unicodedata.normalize("NFD", (s or "").lower())
                   if unicodedata.category(c) != "Mn")


def tamano(nombre):
    """Token de tamaño para agrupar (ej. '473', '1.5l', '900')."""
    s = _norm(nombre).replace(",", ".")
    m = re.search(r"(\d+(?:\.\d+)?)\s*(l|lt|lts|litro|cc|ml|cm3|kg|g|gr|grs)\b", s)
    return (m.group(1) + m.group(2)) if m else "?"


def marca_tok(nombre, marca):
    s = _norm(marca or nombre)
    return s.split()[0] if s.split() else "?"


def bajar_hash(prod):
    url = prod.get("i")
    if not url:
        return None
    try:
        data = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=15).read()
        return dhash(data)
    except Exception:
        return None


STOP_N = {"de", "el", "la", "x", "un", "ml", "cc", "g", "gr", "grs", "kg", "l",
          "lt", "lts", "en", "con", "para", "sabor"}


def tokens_nombre(n):
    s = _norm(n)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return {t for t in s.split() if t not in STOP_N and len(t) > 1}


def jaccard(a, b):
    A, B = tokens_nombre(a), tokens_nombre(b)
    return len(A & B) / len(A | B) if (A | B) else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("archivo", nargs="?", default="data/buscador.json")
    ap.add_argument("--umbral", type=int, default=10, help="distancia máxima de hash")
    ap.add_argument("--workers", type=int, default=16)
    args = ap.parse_args()

    import os
    cache_path = os.path.expanduser("~/.detector-hashes.json")
    cache = {}
    if os.path.exists(cache_path):
        cache = json.load(open(cache_path))

    prods = json.load(open(args.archivo, encoding="utf-8"))["productos"]
    prods = [p for p in prods if p.get("i")]
    faltan = [p for p in prods if p["i"] not in cache]
    print(f"Hasheando {len(faltan)} imágenes nuevas ({len(prods)-len(faltan)} en caché)…", file=sys.stderr)
    if faltan:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
            for p, h in zip(faltan, ex.map(bajar_hash, faltan)):
                cache[p["i"]] = h
        json.dump(cache, open(cache_path, "w"))
    for p in prods:
        p["_h"] = cache.get(p["i"])
    prods = [p for p in prods if p.get("_h") is not None]
    print(f"  {len(prods)} con hash válido", file=sys.stderr)

    # bucket por (marca, tamaño) para no comparar todo contra todo
    buckets = defaultdict(list)
    for p in prods:
        buckets[(marca_tok(p["n"], p.get("m")), tamano(p["n"]))].append(p)

    seguros, revisar = [], []
    for (mk, tm), grupo in buckets.items():
        if len(grupo) < 2 or tm == "?":
            continue
        for i in range(len(grupo)):
            for j in range(i + 1, len(grupo)):
                a, b = grupo[i], grupo[j]
                if set(a["pr"]) & set(b["pr"]):          # comparten cadena = distintos
                    continue
                d = ham(a["_h"], b["_h"])
                if d > args.umbral:
                    continue
                jac = jaccard(a["n"], b["n"])
                # ALTA CONFIANZA: foto casi igual + nombres muy parecidos (mismo
                # producto mal escrito). BAJA: revisar a ojo (puede ser variante).
                (seguros if (d <= 6 and jac >= 0.6) else revisar).append((d, round(jac, 2), a, b))
    seguros.sort(key=lambda x: (-x[1], x[0]))
    revisar.sort(key=lambda x: (-x[1], x[0]))

    print(f"\n===== ALTA CONFIANZA: {len(seguros)} (foto igual + nombres compatibles) =====")
    for d, jac, a, b in seguros:
        print(f"[d{d} j{jac}] {a['n'][:42]} ({'/'.join(a['pr'])})")
        print(f"           {b['n'][:42]} ({'/'.join(b['pr'])})")
    print(f"\n===== A REVISAR: {len(revisar)} (foto parecida, nombre distinto) =====")
    for d, jac, a, b in revisar[:60]:
        print(f"[d{d} j{jac}] {a['n'][:42]} ({'/'.join(a['pr'])})")
        print(f"           {b['n'][:42]} ({'/'.join(b['pr'])})")


if __name__ == "__main__":
    main()
