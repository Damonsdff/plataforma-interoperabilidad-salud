# Plataforma de Interoperabilidad en Salud — Red de IPS Tres Sedes
## Parcial Final — Sistemas Distribuidos

  
**Integrantes:** santiago andres fuentes ·  María Lucia Sotelo 
**Curso:** Sistemas Distribuidos  
**Versión:** v1.0

---

## Descripción

Plataforma distribuida de interoperabilidad clínica que integra tres sedes IPS (Sincelejo, Cartagena y Corozal). Unifica la historia clínica fraccionada sin reemplazar los sistemas legados, usando:

- **FHIR R4** (HAPI FHIR) como estándar de intercambio
- **HSB** (Health Service Bus) con cola, reintentos e idempotencia
- **PostgreSQL** con 3 bases independientes por sede
- **JWT** para autenticación por roles (admisionista, médico, auditor, paciente)
- **Auditoría encadenada por hash** para trazabilidad e integridad

---

## Requisitos previos (Kali Linux / VirtualBox)

- RAM mínima: 4 GB para la VM
- Docker + Docker Compose instalados (ver sección A)
- Puertos libres: 5000, 8000, 8080, 5432

---

## A. Instalación (una sola vez)

```bash
# 1. Descomprimir el proyecto
cd ~/Downloads
unzip ENTREGA_PARCIAL_INTEROPERABILIDAD_con_HSB.zip -d ~/Desktop
cd ~/Desktop/ENTREGA/codigo-fuente-proyecto/lab5-starter-kit

# 2. Instalar dependencias del sistema
bash scripts/instalar_kali.sh
# → pedirá la contraseña de sudo; instala Docker, Python venv y PlantUML

# 3. IMPORTANTE: cerrar sesión y volver a entrar (o reiniciar la VM)
# para que el permiso de Docker se active

# 4. Verificar
docker ps          # debe responder sin "permission denied"
git log --oneline  # debe mostrar commits
```

---

## B. Levantar todo con un solo comando

```bash
cd ~/Desktop/ENTREGA/codigo-fuente-proyecto/lab5-starter-kit
docker compose down -v     # limpia estado anterior (demo desde cero)
docker compose up --build  # primera vez: descarga imágenes (5-10 min)
```

**Servicios disponibles tras el arranque:**

| Servicio | URL |
|---|---|
| Vista unificada (4 vistas) | http://localhost:5000 |
| HSB (Health Service Bus) | http://localhost:8000 |
| HAPI FHIR | http://localhost:8080/fhir |
| Health check vista | http://localhost:5000/health |
| Health check HSB | http://localhost:8000/health |
| Métricas vista | http://localhost:5000/metrics |
| Métricas HSB | http://localhost:8000/metrics |

---

## C. Usuarios de prueba (autenticación por rol)

| Usuario | Contraseña | Rol | Permisos |
|---|---|---|---|
| `admin_sincelejo` | kali | Admisionista | Buscar/registrar pacientes en sede 1 |
| `admin_cartagena` | kali | Admisionista | Buscar/registrar pacientes en sede 2 |
| `admin_corozal` | kali | Admisionista | Buscar/registrar pacientes en sede 3 |
| `medico_perez` | kali | Médico | Historia completa + diagnósticos |
| `medico_garcia` | kali | Médico | Historia completa + diagnósticos |
| `auditor` | kali | Auditor | Lectura total + auditoría + reporte HC |
| `paciente_1007654321` | kali | Paciente | Solo su propia historia |
| `paciente_1007654322` | kali | Paciente | Solo su propia historia |

**Login por formulario:** http://localhost:5000/login  
**Login por API:** `POST http://localhost:5000/auth/login` con `{"usuario":"...", "password":"..."}`

---

## D. Guión de la demo (Fase 5)

### Paso 1 — Verificar estado inicial (0% cobertura)
```bash
# Abrir http://localhost:5000/reportes → debe mostrar 0% en las 3 sedes
curl http://localhost:5000/api/cobertura
```

### Paso 2 — Enviar un mensaje HL7 v2 ADT (admisión)
```bash
curl -s -X POST http://localhost:8000/hsb/hl7 \
  --data-binary @ejemplos/adt_a01_valido_sede1.hl7
# → {"estado": "entregado", ...}
```

### Paso 3 — Enviar un ORU R01 (resultados de laboratorio)
```bash
curl -s -X POST http://localhost:8000/hsb/hl7 \
  --data-binary @ejemplos/oru_r01_valido_sede2.hl7
# → {"estado": "entregado", ...}
```

### Paso 4 — Enviar CSV legado (sede 3 Corozal)
```bash
curl -s -X POST "http://localhost:8000/hsb/csv?sede=3" \
  --data-binary @ejemplos/legado_corozal_sede3.csv
# → {"total": 3, "por_estado": {"entregado": 3}}
```

### Paso 5 — Verificar cobertura subió
```bash
curl http://localhost:5000/api/cobertura
# Abrir http://localhost:5000/reportes → debe mostrar > 0% en sedes con datos
```

### Paso 6 — Comprobar idempotencia (reenvío no duplica)
```bash
curl -s -X POST http://localhost:8000/hsb/hl7 \
  --data-binary @ejemplos/adt_a01_valido_sede1.hl7
# → {"estado": "duplicado", "estado_original": "entregado"}
```

### Paso 7 — Consulta unificada del paciente Juan Pérez (en 3 sedes)
```bash
# En el navegador: http://localhost:5000/paciente?documento=1007654321
# O via API FHIR:
curl "http://localhost:8080/fhir/Patient?identifier=1007654321"
```

### Paso 8 — Probar caída de una sede
```bash
# En otra terminal, pausar el contenedor de la BD (simula caída)
docker compose pause pg_ips

# La vista debe seguir respondiendo con degradación graceful:
curl http://localhost:5000/api/sedes/estado
# → muestra sedes caídas pero vista_disponible: false (si pg_ips baja todas)

# Restaurar:
docker compose unpause pg_ips
```

### Paso 9 — Verificar seguridad (acceso denegado)
```bash
# Sin token: 401
curl -s http://localhost:5000/auditoria | python3 -c "import sys,json; print(json.load(sys.stdin))"

# Con token de admisionista: 403 en ruta de auditor
TOKEN=$(curl -s -X POST http://localhost:5000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"usuario":"admin_sincelejo","password":"kali"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

curl -s -H "Authorization: Bearer $TOKEN" http://localhost:5000/auditoria/verificar
# → 403 Acceso denegado

# Con token de auditor: 200
TOKEN_AUD=$(curl -s -X POST http://localhost:5000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"usuario":"auditor","password":"kali"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

curl -s -H "Authorization: Bearer $TOKEN_AUD" http://localhost:5000/auditoria/verificar
# → {"ok": true, "total": N}
```

### Paso 10 — Verificar integridad de auditoría
```bash
# El auditor verifica la cadena (debe estar íntegra):
curl -s -H "Authorization: Bearer $TOKEN_AUD" http://localhost:5000/auditoria/verificar

# Simular alteración de un evento (en SQLite del volumen):
docker exec -it hsb python3 -c "
import sqlite3; con=sqlite3.connect('/data/auditoria.db')
con.execute(\"UPDATE evento_auditoria SET resultado='denegado' WHERE id=1\")
con.commit(); print('Evento alterado')
"

# Verificar de nuevo → debe detectar la alteración:
curl -s -H "Authorization: Bearer $TOKEN_AUD" http://localhost:5000/auditoria/verificar
# → {"ok": false, "errores": [...]}
```

---

## E. Ejecutar las pruebas

```bash
cd ~/Desktop/ENTREGA/codigo-fuente-proyecto/lab5-starter-kit
source .venv/bin/activate      # activar entorno Python
pip install -r requirements.txt
pytest -v tests/               # todos los tests en verde
```

---

## F. Capturas requeridas

| # | Dónde | Qué capturar |
|---|---|---|
| 1 | /reportes | 0% cobertura en las 3 sedes |
| 2 | /admision | formulario con campos y lista de pacientes |
| 3 | Respuesta del curl al enviar HL7 | `"estado": "entregado"` |
| 4 | Respuesta del curl al reenviar | `"estado": "duplicado"` |
| 5 | /reportes | cobertura > 0% tras migrar |
| 6 | /paciente?documento=1007654321 | historia unificada multi-sede |
| 7 | /medico | formulario completar atención |
| 8 | /auditoria/verificar con token auditor | `"ok": true` |
| 9 | /auditoria/verificar tras alterar | `"ok": false, "errores":[...]` |
| 10 | pytest -v | todos en verde |
| 11 | docker ps | contenedores corriendo |
| 12 | /api/sedes/estado | estado de las 3 sedes |

---

## G. Estructura del proyecto

```
lab5-starter-kit/
├── docker-compose.yml          # Un solo comando levanta todo
├── seguridad.py                # JWT + control de acceso por rol (Fase 4)
├── auditoria.py                # Cadena de hash + verificador (Fase 4)
├── auth_app.py                 # Endpoints de autenticación (Blueprint Flask)
├── migrar_a_fhir.py            # Orquesta la migración legado → FHIR
├── esquema57.py                # Modelo 57 campos Res. 866/2021
├── campos57.py                 # Catálogos y definiciones de campos
├── datos_clinicos.py           # Crea recursos FHIR por código
├── rda.py                      # Genera Bundle tipo document (RDA)
├── hsb/                        # Health Service Bus (Fase 3)
│   ├── app.py                  # API Flask del bus
│   ├── bus.py                  # Cadena: recepción→validación→transformación→entrega
│   ├── almacen.py              # Persistencia SQLite: idempotencia y cola
│   ├── hl7.py                  # Parser HL7 v2 (ADT^A01, ORU^R01) y CSV
│   ├── normalizador.py         # Solicitud → Bundle FHIR R4
│   ├── validacion.py           # Reglas de validación
│   ├── terminologia.py         # Mapeo CIE-10 y LOINC
│   ├── entrega.py              # HAPI FHIR + base de sede
│   └── data/
│       ├── ref_cie10.csv       # ref_terminología: diagnóstico local → CIE-10
│       └── ref_loinc.csv       # ref_terminología: prueba local → LOINC
├── vista_unificada/            # 4 vistas por rol (Fase 5)
│   ├── app.py                  # Flask: /paciente /medico /admision /reportes
│   └── templates/              # HTML por vista
├── interoperabilidad/          # Interfaces del docente
│   ├── models.py               # Paciente, Encuentro, Condicion, etc.
│   ├── mappers.py              # Interfaz HL7v2ToFhirMapper
│   ├── mpi_service.py          # Interfaz MPIService
│   └── service_bus.py          # HealthServiceBus (pub/sub en memoria)
├── solucion/                   # Implementación del estudiante
│   ├── mapper_estudiante.py    # MapperEstudiante
│   └── mpi_estudiante.py       # MPIEstudiante
├── ejemplos/                   # Mensajes de prueba
│   ├── adt_a01_valido_sede1.hl7
│   ├── oru_r01_valido_sede2.hl7
│   ├── adt_invalido_sede0.hl7
│   └── legado_corozal_sede3.csv
├── tests/                      # Pruebas unitarias e integración
│   ├── test_hsb.py
│   ├── test_seguridad_auditoria.py
│   ├── test_mappers.py
│   ├── test_mpi_service.py
│   └── ...
├── docs/                       # Informe y documentos
└── scripts/                    # Scripts de apoyo para Kali Linux
```

---

## H. Reiniciar a cero (para la demo)

```bash
docker compose down -v         # elimina volúmenes (borra datos)
docker compose up --build      # vuelve a arrancar desde cero
```

---

## I. Preguntas frecuentes de sustentación

**¿Qué garantiza el diseño si la sede 2 cae a mitad de una transacción?**  
El HSB usa PUT idempotente en FHIR y upsert en la base. Si falla, el mensaje queda en estado `reintentando` y el bus lo reintenta con backoff exponencial. Según CAP, sacrificamos **disponibilidad parcial** (esa sede no recibe datos hasta recuperarse) a favor de **consistencia**: no creamos duplicados.

**¿Cómo se garantiza que no se pierden mensajes?**  
El almacén SQLite es persistente (volumen Docker). El bus reintenta hasta `MAX_INTENTOS` veces; los que superan el límite van a la cola de mensajes muertos (estado `muerto`) donde pueden reencolarse manualmente.

**¿Qué es la clave de distribución y por qué se eligió `documento_identidad`?**  
Es la clave por la que se fragmenta horizontalmente la tabla de pacientes. Se elige `documento_identidad` porque todas las consultas de historia clínica unificada se hacen por documento del paciente, minimizando las consultas cross-nodo.
