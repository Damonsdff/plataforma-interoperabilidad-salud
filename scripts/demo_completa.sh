#!/bin/bash
# demo_completa.sh — Guión automatizado de la demo del parcial (Fase 5)
# Ejecutar desde la raíz del proyecto: bash scripts/demo_completa.sh
# Requiere: docker compose levantado y jq instalado (sudo apt install -y jq)

set -e
FHIR="http://localhost:8080/fhir"
HSB="http://localhost:8000"
APP="http://localhost:5000"
EJ="$(dirname "$0")/../ejemplos"

echo "============================================================"
echo " DEMO PARCIAL — Plataforma de Interoperabilidad en Salud"
echo "============================================================"
echo

# ── Paso 1: estado inicial
echo "▶ PASO 1: Cobertura inicial (debe ser 0 %)"
curl -s "$APP/api/cobertura" | python3 -c "
import sys,json
for s in json.load(sys.stdin): print(f\"  {s['ciudad']}: {s['cobertura_pct']:.0f}%\")
"
echo

# ── Paso 2: mensaje HL7 ADT (sede 1)
echo "▶ PASO 2: Enviar HL7 ADT^A01 (admisión en Sincelejo)"
R=$(curl -s -X POST "$HSB/hsb/hl7" --data-binary @"$EJ/adt_a01_valido_sede1.hl7")
echo "  Respuesta: $R"
echo

# ── Paso 3: mensaje ORU R01 (sede 2)
echo "▶ PASO 3: Enviar HL7 ORU^R01 (resultados Cartagena)"
R=$(curl -s -X POST "$HSB/hsb/hl7" --data-binary @"$EJ/oru_r01_valido_sede2.hl7")
echo "  Respuesta: $R"
echo

# ── Paso 4: CSV legado (sede 3)
echo "▶ PASO 4: Enviar CSV legado (sede 3 Corozal)"
R=$(curl -s -X POST "$HSB/hsb/csv?sede=3" --data-binary @"$EJ/legado_corozal_sede3.csv")
echo "  Respuesta: $R"
echo

# ── Paso 5: idempotencia
echo "▶ PASO 5: Reenviar el mismo mensaje HL7 → debe ser DUPLICADO"
R=$(curl -s -X POST "$HSB/hsb/hl7" --data-binary @"$EJ/adt_a01_valido_sede1.hl7")
echo "  Estado: $(echo $R | python3 -c 'import sys,json; print(json.load(sys.stdin)[\"estado\"])')"
echo

# ── Paso 6: mensaje inválido
echo "▶ PASO 6: Enviar mensaje inválido → debe ser RECHAZADO"
R=$(curl -s -X POST "$HSB/hsb/hl7" --data-binary @"$EJ/adt_invalido_sede0.hl7")
echo "  Estado: $(echo $R | python3 -c 'import sys,json; print(json.load(sys.stdin)[\"estado\"])')"
echo "  Motivos: $(echo $R | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get(\"motivos\",[]))' 2>/dev/null)"
echo

# ── Paso 7: métricas
echo "▶ PASO 7: Métricas del HSB"
curl -s "$HSB/metrics" | python3 -c "
import sys,json; m=json.load(sys.stdin)
print(f'  Total mensajes: {m[\"mensajes_total\"]}')
print(f'  Por estado: {m[\"por_estado\"]}')
print(f'  Duplicados: {m[\"duplicados_detectados\"]}')
print(f'  % fallidos: {m[\"porcentaje_fallidos\"]}')
"
echo

# ── Paso 8: estado de sedes
echo "▶ PASO 8: Estado de sedes"
curl -s "$APP/api/sedes/estado" | python3 -c "
import sys,json; d=json.load(sys.stdin)
for s in d['sedes']: print(f\"  {s['ciudad']}: {s['estado']} {s.get('latencia_ms','')}\")
print(f\"  Sedes operativas: {d['sedes_operativas']}/3\")
"
echo

# ── Paso 9: seguridad
echo "▶ PASO 9: Prueba de seguridad"
echo "  Login como auditor..."
TOKEN=$(curl -s -X POST "$APP/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"usuario":"auditor","password":"kali"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('token','ERROR'))")
echo "  Token obtenido: ${TOKEN:0:40}..."

echo "  Verificar auditoría (como auditor → debe dar 200):"
R=$(curl -s -w "\n%{http_code}" -H "Authorization: Bearer $TOKEN" "$APP/auditoria/verificar")
HTTP=$(echo "$R" | tail -1)
BODY=$(echo "$R" | head -1)
echo "  HTTP: $HTTP"
echo "  Respuesta: $BODY"

echo "  Intentar sin token (→ 401):"
HTTP=$(curl -s -o /dev/null -w "%{http_code}" "$APP/auditoria")
echo "  HTTP: $HTTP"

echo "  Login como admisionista e intentar acceso a auditoría (→ 403):"
TOKEN_ADM=$(curl -s -X POST "$APP/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"usuario":"admin_sincelejo","password":"kali"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('token','ERROR'))")
HTTP=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOKEN_ADM" "$APP/auditoria/verificar")
echo "  HTTP: $HTTP (esperado: 403)"
echo

echo "============================================================"
echo " ✅ Demo completada. Abrir http://localhost:5000 en el navegador."
echo "============================================================"
