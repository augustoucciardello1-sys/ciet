#!/bin/bash
# Actualiza la serie del IPS y la publica. Pensado para correr a diario
# desde la máquina del usuario (launchd), porque los servidores de SEPA
# bloquean las IPs de datacenter (no sirve GitHub Actions ni un VPS).
# Como build_series.py baja los últimos 7 días y acumula, con que corra
# al menos una vez por semana no se pierde ningún dato.

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
REPO="/Users/augustoucciardello/Desktop/republica_proyecto/modelos-interactivos"
LOG="/tmp/ciet_serie.log"

echo "===== $(date) =====" >> "$LOG"
cd "$REPO" || { echo "no existe el repo" >> "$LOG"; exit 1; }

git pull --quiet >> "$LOG" 2>&1
python3 scripts/build_series.py --dias 7 >> "$LOG" 2>&1 || { echo "fallo build_series" >> "$LOG"; exit 1; }

git add data/serie.json data/cobertura.json
if git diff --cached --quiet; then
  echo "sin cambios" >> "$LOG"
else
  git commit -m "Serie: actualización automática $(date +%Y-%m-%d)" >> "$LOG" 2>&1
  git push >> "$LOG" 2>&1 && echo "publicado OK" >> "$LOG"
fi
