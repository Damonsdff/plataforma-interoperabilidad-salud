#!/bin/bash
# Resumen de los 57 campos en las bases: pacientes, atenciones y registros clínicos por sede
for b in 1 2 3; do
  echo "== historia_clinica_sede$b =="
  docker exec pg_ips psql -U ips_admin -d historia_clinica_sede$b -c \
   "SELECT (SELECT COUNT(*) FROM pacientes) pacientes, (SELECT COUNT(*) FROM atenciones) atenciones,
           (SELECT COUNT(*) FROM tecnologia_salud) medicamentos, (SELECT COUNT(*) FROM diagnostico) diagnosticos,
           (SELECT COUNT(*) FROM egreso) egresos, (SELECT COUNT(*) FROM atenciones WHERE fhir_encounter_id IS NOT NULL) enviadas_fhir;"
done
