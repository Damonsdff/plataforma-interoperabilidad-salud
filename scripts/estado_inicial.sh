#!/bin/bash
# Deja las 3 sedes en 0 %: columna fhir_patient_id a texto, pacientes y atenciones pendientes de migrar
for b in 1 2 3; do
  docker exec pg_ips psql -U ips_admin -d historia_clinica_sede$b \
    -c "ALTER TABLE pacientes ALTER COLUMN fhir_patient_id TYPE VARCHAR(64) USING fhir_patient_id::text;" \
    -c "UPDATE pacientes SET fhir_patient_id = NULL;"
  # la tabla atenciones la crea la app (o python esquema57.py); si aún no existe se omite
  docker exec pg_ips psql -U ips_admin -d historia_clinica_sede$b \
    -c "UPDATE atenciones SET fhir_encounter_id = NULL;" 2>/dev/null || true
done
echo "Sedes en estado inicial (0 %)."
