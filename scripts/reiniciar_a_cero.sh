#!/bin/bash
# Deja el sistema en 0 % para repetir la demostración: vacía HAPI y marca todos los pacientes como pendientes
cd "$(dirname "$0")/.."
bash scripts/estado_inicial.sh
bash scripts/compose.sh rm -sf hapi-fhir
bash scripts/compose.sh up -d hapi-fhir
bash scripts/esperar_hapi.sh
bash scripts/ver_estado_bd.sh
