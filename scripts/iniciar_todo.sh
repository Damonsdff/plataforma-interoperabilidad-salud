#!/bin/bash
# Levanta TODO con un comando: PostgreSQL (3 sedes), HAPI FHIR y la app con las 4 vistas
cd "$(dirname "$0")/.."
bash scripts/compose.sh up -d --build
bash scripts/esperar_hapi.sh
echo
echo "Vistas:    http://localhost:5000"
echo "HAPI FHIR: http://localhost:8080"
echo "Estado de las bases:"
bash scripts/ver_estado_bd.sh
