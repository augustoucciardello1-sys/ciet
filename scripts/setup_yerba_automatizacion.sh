#!/bin/bash
# =============================================================================
# SETUP (una sola vez) de la automatización del Índice de Yerba — CIET
# =============================================================================
# NO se corre solo. Revisalo y ejecutalo VOS cuando quieras activar la serie.
# Crea la rama `yerba-datos` (huérfana, ACUMULA histórico — a diferencia de
# `datos`, que es force-push), monta un worktree en ~/.ciet-yerba, la siembra
# con el día 1 ya capturado y la publica. Al final te imprime el bloque que
# tenés que pegar en ~/.ciet-run.sh para la captura diaria.
#
# Requisitos: el código nuevo (build_indice_yerba.py, etc.) ya tiene que estar
# pusheado a main y traído por ~/.ciet (git pull).
# =============================================================================
set -e

REPO="$HOME/.ciet"                 # clon de main (tiene los scripts)
YERBA="$HOME/.ciet-yerba"          # worktree nuevo, rama yerba-datos
BRANCH="yerba-datos"
# día 1 ya capturado en el repo del Escritorio (para no perder el arranque real)
SEED="$HOME/Desktop/republica_proyecto/modelos-interactivos/data/yerba/crudo/2026-07-14.json"

echo "· Actualizando el clon de main…"
git -C "$REPO" pull --quiet
test -f "$REPO/scripts/build_indice_yerba.py" || { echo "FALTA build_indice_yerba.py en $REPO — pusheá main primero"; exit 1; }

echo "· Creando la rama huérfana $BRANCH y el worktree $YERBA…"
if git -C "$REPO" show-ref --verify --quiet "refs/remotes/origin/$BRANCH"; then
  # ya existe en el remoto: sólo enganchamos el worktree
  git -C "$REPO" fetch --quiet origin "$BRANCH"
  git -C "$REPO" worktree add "$YERBA" "$BRANCH"
else
  # no existe: worktree con rama huérfana vacía
  git -C "$REPO" worktree add --detach "$YERBA"
  cd "$YERBA"
  git checkout --orphan "$BRANCH"
  git rm -rf . >/dev/null 2>&1 || true
  mkdir -p crudo
  # sembrar con el día 1 real (si está); si no, se capturará fresco en la 1ra corrida
  if [ -f "$SEED" ]; then cp "$SEED" "crudo/2026-07-14.json"; echo "  · sembrado con el día 1 ($SEED)"; fi
  python3 "$REPO/scripts/build_indice_yerba.py" --crudo "$YERBA/crudo" -o "$YERBA/indice.json"
  git add -A
  git commit -q -m "Yerba: inicio de la serie"
  git push -q -u origin "$BRANCH"
  echo "  · rama $BRANCH publicada."
fi

cat <<'BLOQUE'

=============================================================================
LISTO. Falta UN paso manual: pegá este bloque en ~/.ciet-run.sh
(justo ANTES del `trap`/final, dentro del mismo lock que ya tiene el script).
Corre 1×/día: sólo actúa en la primera corrida del día (~10 h), porque
saltea si el crudo de hoy ya existe.
=============================================================================

# --- Índice de yerba: 1×/día (sólo en la 1ra corrida del día ~10 h) ---
YERBA="$HOME/.ciet-yerba"; HOY=$(date +%F)
if [ -d "$YERBA" ] && [ ! -f "$YERBA/crudo/$HOY.json" ]; then
  echo "----- yerba $HOY -----" >> "$LOG"
  git -C "$YERBA" pull --quiet >> "$LOG" 2>&1
  if python3 "$REPO/scripts/fetch_buscador.py" --terminos yerba --tope 200 -o "$YERBA/crudo/$HOY.json" >> "$LOG" 2>&1 \
     && python3 "$REPO/scripts/build_indice_yerba.py" --crudo "$YERBA/crudo" -o "$YERBA/indice.json" >> "$LOG" 2>&1; then
    git -C "$YERBA" add -A
    git -C "$YERBA" commit -q -m "Yerba: captura $HOY" >> "$LOG" 2>&1
    git -C "$YERBA" push -q origin yerba-datos >> "$LOG" 2>&1 && echo "yerba OK" >> "$LOG" || echo "fallo push yerba" >> "$LOG"
  else
    echo "fallo captura yerba" >> "$LOG"
  fi
fi
# --- fin índice de yerba ---

=============================================================================
BLOQUE
