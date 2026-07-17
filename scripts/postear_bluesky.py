#!/usr/bin/env python3
"""
Publica en Bluesky la placa + caption de las ofertas del día.

Bluesky tiene API abierta y gratis: alcanza con el handle de la cuenta y una
"App Password" (Configuración → App Passwords), que NO es la contraseña real.
Se leen de variables de entorno (en GitHub Actions vienen de los Secrets):
    BSKY_HANDLE          ej: ofertastuchoy.bsky.social
    BSKY_APP_PASSWORD    ej: xxxx-xxxx-xxxx-xxxx

Uso:
    python3 postear_bluesky.py --img placa.png --caption caption.txt [--dry-run]
"""
import argparse
import os
import sys
from pathlib import Path

LIMITE = 300  # Bluesky permite hasta 300 caracteres
ALT = ("Placa con las principales bajas de precio del día en "
       "supermercados de Tucumán.")


def credenciales():
    h = os.environ.get("BSKY_HANDLE")
    p = os.environ.get("BSKY_APP_PASSWORD")
    if not h or not p:
        sys.exit("ERROR: faltan BSKY_HANDLE o BSKY_APP_PASSWORD")
    return h, p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--img", required=True)
    ap.add_argument("--caption", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    texto = Path(args.caption).read_text().strip()
    if len(texto) > LIMITE:
        texto = texto[:LIMITE - 1].rstrip() + "…"
    if not Path(args.img).exists():
        sys.exit(f"ERROR: no existe la imagen {args.img}")

    handle, app_pw = credenciales()

    if args.dry_run:
        print("[dry-run] credenciales OK. Publicaría en Bluesky:")
        print(f"  imagen : {args.img}")
        print(f"  texto  ({len(texto)} car.):\n{texto}")
        return

    from atproto import Client  # se instala en el runner
    client = Client()
    client.login(handle, app_pw)
    with open(args.img, "rb") as f:
        img_bytes = f.read()
    post = client.send_image(text=texto, image=img_bytes, image_alt=ALT)
    # uri tipo at://did/app.bsky.feed.post/xxxx -> arma el link web
    rkey = post.uri.rsplit("/", 1)[-1]
    print(f"publicado en Bluesky: https://bsky.app/profile/{handle}/post/{rkey}")


if __name__ == "__main__":
    main()
