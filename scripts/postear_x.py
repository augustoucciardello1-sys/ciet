#!/usr/bin/env python3
"""
Publica en X (Twitter) la placa + caption de las ofertas del día.

Autenticación OAuth 1.0a (user context) — necesaria para postear y subir
imágenes. Las 4 credenciales se leen de variables de entorno (en GitHub Actions
vienen de los Secrets):
    X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET

Uso:
    python3 postear_x.py --img placa.png --caption caption.txt [--dry-run]

--dry-run: valida credenciales y muestra qué publicaría, sin postear.
"""
import argparse
import os
import sys
from pathlib import Path

import tweepy


def credenciales():
    faltan = [k for k in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN",
                          "X_ACCESS_SECRET") if not os.environ.get(k)]
    if faltan:
        sys.exit(f"ERROR: faltan credenciales: {', '.join(faltan)}")
    return (os.environ["X_API_KEY"], os.environ["X_API_SECRET"],
            os.environ["X_ACCESS_TOKEN"], os.environ["X_ACCESS_SECRET"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--img", required=True)
    ap.add_argument("--caption", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    texto = Path(args.caption).read_text().strip()
    if not Path(args.img).exists():
        sys.exit(f"ERROR: no existe la imagen {args.img}")

    ck, cs, at, ats = credenciales()

    if args.dry_run:
        print("[dry-run] credenciales OK. Publicaría:")
        print(f"  imagen : {args.img}")
        print(f"  texto  :\n{texto}")
        return

    # media_upload sigue siendo API v1.1; el tweet se crea con API v2
    api = tweepy.API(tweepy.OAuth1UserHandler(ck, cs, at, ats))
    media = api.media_upload(filename=args.img)
    client = tweepy.Client(consumer_key=ck, consumer_secret=cs,
                           access_token=at, access_token_secret=ats)
    resp = client.create_tweet(text=texto, media_ids=[media.media_id])
    tid = resp.data["id"]
    print(f"publicado: https://x.com/ofertastuchoy/status/{tid}")


if __name__ == "__main__":
    main()
