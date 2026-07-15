#!/usr/bin/env bash
# Captura diaria del Índice de Precios de Yerbas (CIET).
# Correr UNA vez por día, a hora fija (recomendado ~09:00 hora Tucumán), para que
# la serie sea comparable día a día.
#
#   1. Baja la yerba del día (reusa el scraper del buscador) → crudo/AAAA-MM-DD.json
#   2. Recalcula el índice sobre todo el histórico          → indice.json
#
# El paso de PUBLICAR (subir crudo + indice.json a la rama `datos`, que es de donde
# lee la página) va aparte, con el mismo mecanismo que el buscador.
set -e
cd "$(dirname "$0")/.."

HOY=$(date +%F)
echo "· Capturando yerba de $HOY…"
python3 scripts/fetch_buscador.py --terminos yerba --tope 200 -o "data/yerba/crudo/$HOY.json"

echo "· Recalculando índice…"
python3 scripts/build_indice_yerba.py

echo "OK · yerba actualizada ($HOY)."
