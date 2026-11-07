#!/bin/bash
# Espera hasta que HAPI FHIR responda en el puerto 8080
until curl -sf -o /dev/null localhost:8080/fhir/metadata; do
  echo "esperando HAPI..."; sleep 5
done
echo "HAPI LISTO"
