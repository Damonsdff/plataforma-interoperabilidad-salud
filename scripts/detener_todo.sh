#!/bin/bash
# Detiene el entorno (HU-10: docker compose down). Las bases conservan sus datos.
cd "$(dirname "$0")/.."
bash scripts/compose.sh down
