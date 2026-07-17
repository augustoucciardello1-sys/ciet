#!/usr/bin/env python3
"""
Publica en un canal de Telegram la placa + caption de las ofertas del día.

Telegram Bot API: 100% gratis e ilimitada. Necesitás:
  1) Un bot creado con @BotFather -> te da el TOKEN.
  2) Un canal (ej. t.me/ofertastuchoy) con el bot agregado como ADMIN.
Se leen de variables de entorno (en GitHub Actions vienen de los Secrets):
    TELEGRAM_BOT_TOKEN   ej: 1234567890:AAE...
    TELEGRAM_CHAT_ID     ej: @ofertastuchoy  (o el id numérico del canal)

Uso:
    python3 postear_telegram.py --img placa.png --caption caption.txt [--dry-run]
"""
import argparse
import os
import sys
from pathlib import Path

import requests

API = "https://api.telegram.org/bot{token}/sendPhoto"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--img", required=True)
    ap.add_argument("--caption", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    texto = Path(args.caption).read_text().strip()[:1024]  # límite de caption
    if not Path(args.img).exists():
        sys.exit(f"ERROR: no existe la imagen {args.img}")

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        sys.exit("ERROR: faltan TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID")

    if args.dry_run:
        print("[dry-run] credenciales OK. Publicaría en Telegram:")
        print(f"  canal  : {chat}")
        print(f"  imagen : {args.img}")
        print(f"  texto  :\n{texto}")
        return

    with open(args.img, "rb") as f:
        r = requests.post(API.format(token=token),
                          data={"chat_id": chat, "caption": texto},
                          files={"photo": f}, timeout=30)
    j = r.json()
    if not j.get("ok"):
        sys.exit(f"ERROR Telegram: {j}")
    mid = j["result"]["message_id"]
    ref = str(chat).lstrip("@")
    print(f"publicado en Telegram: https://t.me/{ref}/{mid}")


if __name__ == "__main__":
    main()
