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
from build_index import (procesar_dia, CADENAS_OBJETIVO, MIN_PRODUCTOS, PROVINCIA,
                         leer_csv, construir, escribir_ips)

CKAN = "https://datos.produccion.gob.ar/api/3/action/package_show?id=sepa-precios"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
HEADERS = {
    "User-Agent": UA,
    "Accept": "application/json,text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
    "Referer": "https://datos.produccion.gob.ar/dataset/sepa-precios",
    "Connection": "keep-alive",
}


def get_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
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
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=300) as r, open(zpath, "wb") as f:
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
    """Devuelve (full, filtrado): `full` es el procesar_dia completo (todas las
    banderas, con descripciones y sucursales, para regenerar ips.json); `filtrado`
    es {cadena: {ean: precio}} sólo de las cadenas objetivo principales (para la serie)."""
    hoy = procesar_dia(dir_dia)
    principales = [n for n, d in hoy.items()
                   if len(d["precios"]) >= MIN_PRODUCTOS and n in CADENAS_OBJETIVO]
    return hoy, {n: hoy[n]["precios"] for n in principales}


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

    dias = {}       # fecha -> {cadena: {ean: precio}}  (sólo cadenas principales)
    dias_full = {}  # fecha -> procesar_dia completo (para regenerar ips.json)
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
            full, filtrado = canasta_dia(dir_dia)
            dias_full[fecha] = full
            dias[fecha] = filtrado
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
    canastas_dia = {}   # fecha -> [eans] de la intersección (persistencia por período)
    indice = None
    for j, fecha in enumerate(fechas):
        precios = dias[fecha]
        eans_cadena = {c: set(p) for c, p in precios.items()}
        canasta = set.intersection(*eans_cadena.values()) if len(eans_cadena) >= 2 else set()
        canastas_dia[fecha] = sorted(canasta)
        prevpt = puntos.get(fecha, {})
        if j == 0:
            indice = prevpt.get("indice", 100.0)
            # el día más viejo de la ventana de hoy no tiene predecesor descargado
            # para recalcular su variación: se CONSERVA lo ya calculado en corridas
            # previas (cuando este día no era el más viejo), no se pisa con null.
            var = prevpt.get("var_pct")
            mant = prevpt.get("se_mantienen")
            pares_val = prevpt.get("pares")
        else:
            prevp = dias[fechas[j - 1]]
            a = {(c, e): precios[c][e] for c in precios for e in precios[c]}
            b = {(c, e): prevp[c][e] for c in prevp for e in prevp[c]}
            ratio, npares = jevons(a, b)
            var = round((ratio - 1) * 100, 3) if ratio else None
            if ratio and indice is not None:
                indice = round(indice * ratio, 4)
            cprev = set.intersection(*[set(p) for p in prevp.values()]) if len(prevp) >= 2 else set()
            mant = len(canasta & cprev)
            pares_val = npares
        puntos[fecha] = {
            "fecha": fecha,
            "indice": round(indice, 2) if indice is not None else None,
            "var_pct": var,
            "canasta_n": len(canasta),
            "se_mantienen": mant,
            "pares": pares_val,
        }

    # rellenar huecos de variación: si un día tiene índice pero var_pct quedó en
    # null (por el deslizamiento de ventana en corridas viejas, cuyo día previo ya
    # no está para recalcular Jevons), se reconstruye del propio índice encadenado:
    # var = índice_hoy / índice_ayer − 1. Deja la serie sin huecos y consistente.
    orden = [puntos[f] for f in sorted(puntos)]
    for k in range(1, len(orden)):
        cur, ant = orden[k], orden[k - 1]
        if cur.get("var_pct") is None and cur.get("indice") and ant.get("indice"):
            cur["var_pct"] = round((cur["indice"] / ant["indice"] - 1) * 100, 3)

    serie = {
        "actualizado": time.strftime("%Y-%m-%d"),
        "base": "índice encadenado (Jevons por tramo), base 100 en el primer día registrado",
        "cadenas": sorted(CADENAS_OBJETIVO),
        "puntos": [puntos[f] for f in sorted(puntos)],
    }
    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text(json.dumps(serie, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"OK → {sp} ({len(serie['puntos'])} puntos)", file=sys.stderr)

    # canastas por día (EANs de la intersección de las 3 cadenas): permiten calcular
    # en el sitio cuántos productos se mantienen respecto del período previo REAL
    # (semana vs semana, mes vs mes). Se acumulan y se podan a los últimos 60 días.
    cpath = sp.parent / "canastas.json"
    canastas = json.loads(cpath.read_text(encoding="utf-8")) if cpath.exists() else {}
    canastas.update(canastas_dia)
    canastas = {f: canastas[f] for f in sorted(canastas)[-60:]}
    cpath.write_text(json.dumps(canastas, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"OK → {cpath} ({len(canastas)} días)", file=sys.stderr)

    # --- ips.json + productos.json (pestañas Resumen/Cadenas/Productos del sitio) ---
    # Se regeneran ACÁ, con los mismos dumps ya descargados, para que no queden
    # congelados. Antes build_index no estaba en la automatización y estos archivos
    # quedaban pegados en una fecha vieja. Comparación "semana previa" = día más
    # antiguo disponible en la ventana (~7 días atrás).
    fechas_full = sorted(dias_full)
    if len(fechas_full) >= 2:
        f_act, f_base = fechas_full[-1], fechas_full[0]
        resumen, catalogo = construir(dias_full[f_act], dias_full[f_base], f_act, f_base)
        if resumen:
            escribir_ips(resumen, catalogo, sp.parent / "ips.json")
            print(f"OK → {sp.parent / 'ips.json'} ({f_base} → {f_act}, "
                  f"{len(catalogo['productos'])} productos)", file=sys.stderr)
        else:
            print("ips.json: sin dos cadenas con canasta, no se regenera", file=sys.stderr)


if __name__ == "__main__":
    main()
