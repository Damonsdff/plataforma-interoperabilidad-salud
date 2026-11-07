#!/bin/bash
# Muestra total y migrados por sede
for b in 1 2 3; do
  echo "--- sede$b ---"
  docker exec pg_ips psql -U ips_admin -d historia_clinica_sede$b \
    -c "SELECT COUNT(*) AS total, COUNT(fhir_patient_id) AS migrados FROM pacientes;"
done
