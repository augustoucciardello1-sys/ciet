#!/usr/bin/env python3
"""
Genera la placa diaria de mega ofertas (PNG 1080x1080) + el caption para X,
a partir del ofertas.json que produce build_mega_ofertas.py.

Se hace con Pillow (no SVG) para que corra idéntico en la laptop y en el
runner Ubuntu de GitHub Actions, sin depender de conversores ni de fuentes
del sistema puntuales.

Uso:
    python3 generar_placa_ofertas.py --ofertas ofertas.json \
        --out-img placa.png --out-caption caption.txt [--top 5]
"""
import argparse
import io
import json
import urllib.request
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

LINK_TXT = "cietucuman.github.io/ciet"
LINK_URL = "https://cietucuman.github.io/ciet/"

# --- paleta (misma que el avatar / banner) ---
VERDE = (4, 120, 87)
VERDE_TXT = (15, 61, 51)
AMBAR = (245, 158, 11)
FONDO = (244, 247, 245)
BLANCO = (255, 255, 255)
GRIS = (91, 107, 102)
LINEA = (219, 228, 224)
AMBAR_CLARO = (247, 183, 51)

W = H = 1080
DIAS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]

# rutas de fuentes candidatas (mac primero, luego ubuntu / liberation / dejavu)
FUENTES_REG = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]
FUENTES_BOLD = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def _fuente(candidatas, size):
    for ruta in candidatas:
        if Path(ruta).exists():
            return ImageFont.truetype(ruta, size)
    return ImageFont.load_default()


def bold(size):
    return _fuente(FUENTES_BOLD, size)


def reg(size):
    return _fuente(FUENTES_REG, size)


def pesos(v):
    return "$" + f"{int(round(v)):,}".replace(",", ".")


def fecha_es(iso):
    d = date.fromisoformat(iso)
    return f"{DIAS[d.weekday()]} {d.day:02d}/{d.month:02d}"


def cargar_thumb(url, size=112):
    """Baja la foto del producto y la deja como cuadrado `size` con fondo blanco
    y esquinas redondeadas. Devuelve (imagen, mask) o None si falla la descarga."""
    if not url:
        return None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        data = urllib.request.urlopen(req, timeout=8).read()
        im = Image.open(io.BytesIO(data))
    except Exception:
        return None
    if im.mode != "RGB":
        fondo = Image.new("RGB", im.size, BLANCO)
        im = im.convert("RGBA")
        fondo.paste(im, mask=im.split()[-1])
        im = fondo
    lienzo = Image.new("RGB", (size, size), BLANCO)
    im.thumbnail((size - 12, size - 12))
    lienzo.paste(im, ((size - im.width) // 2, (size - im.height) // 2))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size, size], radius=18, fill=255)
    return lienzo, mask


def _catkey(nombre):
    """Primera palabra significativa, para no repetir categoría (3 mieles, etc.)."""
    for w in (nombre or "").lower().split():
        w = "".join(c for c in w if c.isalpha())
        if len(w) >= 3:
            return w
    return (nombre or "").lower()[:4]


def seleccionar_variado(ofertas, top, max_por_cadena=2):
    """Del ranking por score, arma un top variado: <=2 por cadena y sin repetir
    categoría de producto. Si no alcanza, relaja las restricciones."""
    elegidas, conteo, cats = [], {}, set()
    for o in ofertas:
        c = o["cadena"]
        k = _catkey(o["n"])
        if conteo.get(c, 0) >= max_por_cadena or k in cats:
            continue
        elegidas.append(o)
        conteo[c] = conteo.get(c, 0) + 1
        cats.add(k)
        if len(elegidas) >= top:
            return elegidas
    for o in ofertas:  # relajar: completar si faltan
        if o not in elegidas:
            elegidas.append(o)
            if len(elegidas) >= top:
                break
    return elegidas


def truncar(draw, texto, font, max_w):
    if draw.textlength(texto, font=font) <= max_w:
        return texto
    while texto and draw.textlength(texto + "…", font=font) > max_w:
        texto = texto[:-1]
    return texto.rstrip() + "…"


def pill(draw, x, y, texto, font, h=46):
    w = draw.textlength(texto, font=font) + 40
    draw.rounded_rectangle([x, y, x + w, y + h], radius=h // 2, fill=AMBAR)
    tb = draw.textbbox((0, 0), texto, font=font)
    ty = y + (h - (tb[3] - tb[1])) / 2 - tb[1]
    draw.text((x + 20, ty), texto, font=font, fill=BLANCO)
    return w


def flecha_abajo(draw, cx, cy, r):
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=AMBAR)
    lw = max(10, r // 5)
    draw.line([(cx, cy - r * 0.48), (cx, cy + r * 0.42)], fill=BLANCO, width=lw)
    draw.line([(cx - r * 0.42, cy), (cx, cy + r * 0.42)], fill=BLANCO, width=lw)
    draw.line([(cx + r * 0.42, cy), (cx, cy + r * 0.42)], fill=BLANCO, width=lw)


def generar_placa(datos, top, out_img):
    img = Image.new("RGB", (W, H), FONDO)
    d = ImageDraw.Draw(img)

    # --- header ---
    d.rectangle([0, 0, W, 212], fill=VERDE)
    d.text((60, 44), "OFERTAS DEL DÍA", font=bold(62), fill=BLANCO)
    d.text((60, 132), f"Súper de Tucumán · {fecha_es(datos['fecha'])}",
           font=reg(34), fill=(220, 235, 229))
    flecha_abajo(d, 972, 106, 66)

    ofertas = seleccionar_variado(datos["ofertas"], top)
    pie_y = 988
    y0, alto = 232, (pie_y - 232) // max(len(ofertas), 1)
    thumb = 112
    f_nombre, f_precio, f_pill, f_det = bold(36), bold(46), bold(28), reg(28)

    for i, o in enumerate(ofertas):
        top_y = y0 + i * alto
        cy = top_y + (alto - 16) // 2  # centro vertical de la fila

        th = cargar_thumb(o.get("i"), thumb)
        if th:
            ty = cy - thumb // 2
            img.paste(th[0], (60, ty), th[1])
            d.rounded_rectangle([60, ty, 60 + thumb, ty + thumb],
                                radius=18, outline=LINEA, width=2)
            tx = 60 + thumb + 26
        else:
            tx = 60

        precio_txt = pesos(o["precio"])
        pw = d.textlength(precio_txt, font=f_precio)
        d.text((W - 60 - pw, cy - 46), precio_txt, font=f_precio, fill=VERDE)

        nombre = truncar(d, o["n"], f_nombre, (W - 60 - pw - 30) - tx)
        d.text((tx, cy - 44), nombre, font=f_nombre, fill=VERDE_TXT)

        baja = f"−{round(o['baja_pct'])}%"
        pill_w = pill(d, tx, cy + 6, baja, f_pill)
        det = f"en {o['cadena']} · vs. su precio de la semana"
        det = truncar(d, det, f_det, W - (tx + pill_w + 16) - 60)
        d.text((tx + pill_w + 16, cy + 12), det, font=f_det, fill=GRIS)

        if i < len(ofertas) - 1:
            ly = top_y + alto - 8
            d.line([(60, ly), (W - 60, ly)], fill=LINEA, width=2)

    # --- footer con link ---
    d.rectangle([0, pie_y, W, H], fill=VERDE)
    d.text((60, pie_y + 14), "Bajas verificadas con datos · no promos infladas",
           font=reg(24), fill=(210, 231, 223))
    d.text((60, pie_y + 50), LINK_TXT, font=bold(31), fill=AMBAR_CLARO)
    handle = "@ofertastuchoy"
    hw = d.textlength(handle, font=bold(29))
    d.text((W - 60 - hw, pie_y + 52), handle, font=bold(29), fill=BLANCO)

    img.save(out_img)
    return ofertas


def generar_caption(datos, ofertas):
    top = ofertas[0]
    gancho = (f"🔥 {top['m'] or top['n'][:28]} −{round(top['baja_pct'])}% "
              f"en {top['cadena']}" + (f", y {len(ofertas)-1} más" if len(ofertas) > 1 else ""))
    return (
        "🛒 Las mejores ofertas de hoy en los súper de Tucumán 👇\n\n"
        f"{gancho}\n\n"
        "Bajas de precio reales, verificadas con datos. No promos infladas.\n\n"
        f"📲 Todos los precios: {LINK_TXT}\n\n"
        "#Tucumán #Ofertas #Supermercados #Precios"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ofertas", required=True)
    ap.add_argument("--out-img", default="placa.png")
    ap.add_argument("--out-caption", default="caption.txt")
    ap.add_argument("--top", type=int, default=5)
    args = ap.parse_args()

    datos = json.loads(Path(args.ofertas).read_text())
    if not datos.get("ofertas"):
        print("sin ofertas: no se genera placa")
        return 1

    ofertas = generar_placa(datos, args.top, args.out_img)
    Path(args.out_caption).write_text(generar_caption(datos, ofertas))
    print(f"placa -> {args.out_img} ({len(ofertas)} ofertas)")
    print(f"caption -> {args.out_caption}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
