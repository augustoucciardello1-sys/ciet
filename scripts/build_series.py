#!/usr/bin/env python3
"""
Serie temporal del IPS (CIET) — índice encadenado con canasta dinámica.

Baja los dumps diarios recientes de SEPA, calcula para cada día la canasta
(intersección de EANs de las 3 cadenas objetivo en Tucumán) y encadena las
variaciones día a día (índice de Jevons por tramo). La canasta puede cambiar:
entran EANs nuevos y salen los que desaparecen; el encadenamiento mantiene la
serie continua. Acumula en data/serie.json, de modo que la historia persiste
aunque SEPA borre los días viejos (guarda solo ~7).

Uso:
    python3 build_series.py [--dias 7] [--salida data/serie.json]
"""
import argparse
import io
import json
import math
import shutil
import sys
import tempfile
import time
import urllib.request
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_index import procesar_dia, CADENAS_OBJETIVO, MIN_PRODUCTOS, PROVINCIA, leer_csv

CKAN = "https://datos.produccion.gob.ar/api/3/action/package_show?id=sepa-precios"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120"


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.load(r)


def daily_urls():
    """URLs de los recursos zip diarios (sepa_lunes.zip … sepa_domingo.zip)."""
    dias = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
    pkg = get_json(CKAN)["result"]
    urls = []
    for res in pkg["resources"]:
        nombre = (res.get("name") or "").lower()
        url = res.get("url", "")
        if any(f"sepa_{d}" in nombre or f"sepa_{d}" in url.lower() for d in dias):
            urls.append(url)
    return urls


def descargar_y_extraer(url, destino):
    """Baja el zip diario y lo extrae; devuelve la carpeta-fecha interna."""
    zpath = destino / "dump.zip"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=180) as r, open(zpath, "wb") as f:
        shutil.copyfileobj(r, f)
    with zipfile.ZipFile(zpath) as z:
        z.extractall(destino)
    zpath.unlink()
    # la carpeta con forma AAAA-MM-DD contiene los zips por comercio
    for p in sorted(destino.iterdir()):
        if p.is_dir() and len(p.name) == 10 and p.name[4] == "-":
            return p
    return None


def canasta_dia(dir_dia):
    """{fecha, precios:{cadena:{ean:precio}}} para las cadenas objetivo."""
    hoy = procesar_dia(dir_dia)
    principales = [n for n, d in hoy.items()
                   if len(d["precios"]) >= MIN_PRODUCTOS and n in CADENAS_OBJETIVO]
    return {n: hoy[n]["precios"] for n in principales}


def auditar_cobertura(dir_dia, salida):
    """Para responder por qué faltan cadenas: lista todas las banderas y sus
    sucursales por provincia, marcando las de Tucumán."""
    filas = []
    for z in sorted(Path(dir_dia).glob("*.zip")):
        try:
            zf = zipfile.ZipFile(z)
        except zipfile.BadZipFile:
            continue
        nombres = {Path(n).name: n for n in zf.namelist()}
        if "sucursales.csv" not in nombres:
            continue
        banderas = {}
        if "comercio.csv" in nombres:
            for f in leer_csv(zf, nombres["comercio.csv"]):
                banderas[(f.get("id_bandera") or "").strip()] = (f.get("comercio_bandera_nombre") or "").strip()
        prov = defaultdict(Counter)
        for f in leer_csv(zf, nombres["sucursales.csv"]):
            b = (f.get("id_bandera") or "").strip()
            prov[b][(f.get("sucursales_provincia") or "?").strip()] += 1
        for b, c in prov.items():
            filas.append({"cadena": banderas.get(b, z.stem), "tucuman": c.get(PROVINCIA, 0),
                          "total_sucursales": sum(c.values())})
    filas.sort(key=lambda x: -x["total_sucursales"])
    Path(salida).write_text(json.dumps(filas, ensure_ascii=False, indent=1), encoding="utf-8")
    return filas


def jevons(a, b):
    rs = [math.log(a[k] / b[k]) for k in a.keys() & b.keys() if a[k] > 0 and b[k] > 0]
    return (math.exp(sum(rs) / len(rs)), len(rs)) if rs else (None, 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dias", type=int, default=7)
    ap.add_argument("--salida", default="data/serie.json")
    ap.add_argument("--audit", default="data/cobertura.json")
    args = ap.parse_args()

    urls = daily_urls()
    print(f"{len(urls)} recursos diarios en SEPA", file=sys.stderr)

    dias = {}  # fecha -> {cadena: {ean: precio}}
    audit_hecho = False
    for i, url in enumerate(urls[: args.dias], 1):
        tmp = Path(tempfile.mkdtemp(prefix="sepa_"))
        try:
            print(f"[{i}/{min(args.dias,len(urls))}] bajando…", file=sys.stderr)
            dir_dia = descargar_y_extraer(url, tmp)
            if not dir_dia:
                print("  sin carpeta-fecha, salteo", file=sys.stderr); continue
            fecha = dir_dia.name
            if not audit_hecho:
                fil = auditar_cobertura(dir_dia, args.audit)
                print("  cobertura (top): " + ", ".join(
                    f"{x['cadena']}={x['tucuman']}T/{x['total_sucursales']}" for x in fil[:8]),
                    file=sys.stderr)
                audit_hecho = True
            dias[fecha] = canasta_dia(dir_dia)
            print(f"  {fecha}: {len(dias[fecha])} cadenas", file=sys.stderr)
        except Exception as e:
            print(f"  error: {e}", file=sys.stderr)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # combinar con serie previa (acumulador)
    prev = {}
    sp = Path(args.salida)
    if sp.exists():
        for r in json.loads(sp.read_text(encoding="utf-8")).get("puntos", []):
            prev[r["fecha"]] = r

    # construir/actualizar índice encadenado sobre las fechas disponibles hoy
    fechas = sorted(dias)
    puntos = dict(prev)
    indice = None
    for j, fecha in enumerate(fechas):
        precios = dias[fecha]
        eans_cadena = {c: set(p) for c, p in precios.items()}
        canasta = set.intersection(*eans_cadena.values()) if len(eans_cadena) >= 2 else set()
        if j == 0:
            base_indice = puntos.get(fecha, {}).get("indice", 100.0)
            indice = base_indice
            var = None
            mant = None
        else:
            prevp = dias[fechas[j - 1]]
            a = {(c, e): precios[c][e] for c in precios for e in precios[c]}
            b = {(c, e): prevp[c][e] for c in prevp for e in prevp[c]}
            ratio, n = jevons(a, b)
            var = round((ratio - 1) * 100, 3) if ratio else None
            if ratio and indice is not None:
                indice = round(indice * ratio, 4)
            cprev = set.intersection(*[set(p) for p in prevp.values()]) if len(prevp) >= 2 else set()
            mant = len(canasta & cprev)
        puntos[fecha] = {
            "fecha": fecha,
            "indice": round(indice, 2) if indice is not None else None,
            "var_pct": var,
            "canasta_n": len(canasta),
            "se_mantienen": mant,
            "pares": n if j > 0 else None,
        }

    serie = {
        "actualizado": time.strftime("%Y-%m-%d"),
        "base": "índice encadenado (Jevons por tramo), base 100 en el primer día registrado",
        "cadenas": sorted(CADENAS_OBJETIVO),
        "puntos": [puntos[f] for f in sorted(puntos)],
    }
    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text(json.dumps(serie, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"OK → {sp} ({len(serie['puntos'])} puntos)", file=sys.stderr)


if __name__ == "__main__":
    main()
