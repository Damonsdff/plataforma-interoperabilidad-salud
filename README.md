# Parcial final — Interoperabilidad FHIR multi-sede (UAJS)

Starter kit del Laboratorio 5 + implementación del equipo + 4 vistas por rol (Paciente, Médico, Admisionista,
Reportero) + **los 57 campos de la Res. 866/2021** (modelo, formularios, FHIR, matriz y pruebas) + informe.

## Inicio rápido en Kali Linux
```bash
cd lab5-starter-kit
bash scripts/instalar_kali.sh        # SOLO la primera vez; luego CERRAR SESIÓN y volver a entrar
bash scripts/iniciar_todo.sh         # docker compose up: PostgreSQL x3 sedes + HAPI FHIR + vistas
```
Vistas: http://localhost:5000 · HAPI FHIR: http://localhost:8080/fhir · Matriz: http://localhost:5000/matriz

## Los 57 campos (cómo quedaron repartidos)
| Rol | Campos | Dónde |
|---|---|---|
| Admisionista | 1-15, 24, 51-57 (identificación y contacto) y 16-23 (atención) | /admision |
| Médico | 25-35 (tecnología y diagnóstico de ingreso/egreso), 36-39 (diagnósticos), 40-50 (egreso) | /medico |
| Auditor | Matriz de trazabilidad con % real de diligenciamiento por sede | /matriz, /matriz.csv |

Archivos clave: `campos57.py` (registro único), `esquema57.py` (tablas), `solucion/historia57_fhir.py` (mapeo a FHIR),
`rda.py` (Composition + `$document`), `docs/Matriz_Trazabilidad_57_Campos.xlsx`, `docs/57_CAMPOS_HC_docente.md`.

## Demostración 0 % → 100 %
1. `bash scripts/reiniciar_a_cero.sh` deja las 3 sedes en 0 % y HAPI vacío.
2. /reportes → captura del 0 %.
3. /admision → «Migrar pendientes a FHIR» en cada sede (o `python migrar_a_fhir.py --sede historia_clinica_sede1`, sede2, sede3).
4. /reportes → captura del 100 %.
5. /paciente y /medico con el documento `1007654321` (está en Sincelejo y Cartagena → historia unificada).
6. /medico → «Completar atención» (campos 25-50) y el enlace RDA (Composition/$document). Por terminal: `python generar_bundle_document.py <id_patient>`.
7. `bash scripts/detener_todo.sh` (equivale a `docker compose down`).

## Pruebas
```bash
source .venv/bin/activate
pip install -r requirements-dev.txt     # opcional: valida estructura FHIR R4
pytest -v                               # 81 pruebas (la de integración se omite si no hay PostgreSQL en localhost:5432)
```
La prueba de integración crea bases temporales (`hc_test_a/b`) y usa un HAPI simulado (`tests/fake_hapi.py`); no toca las 3 sedes.

## Repositorio Git
Este paquete ya trae el repositorio inicializado (`git log`). Para subirlo a GitHub: `git remote add origin <url> && git push -u origin main`.

## Si algo falla
- «permission denied» con docker: cerrar sesión y volver a entrar tras la instalación.
- Vista Reportero con error de HAPI: HAPI tarda 1-2 min en iniciar; recargar.
- Bases ya existentes: la app crea las tablas de los 57 campos sola al arrancar (o `python esquema57.py`). Columna UUID antigua: `bash scripts/estado_inicial.sh`.
- `bash scripts/ver_campos57.sh` muestra cuántas atenciones/medicamentos/egresos hay por sede.
