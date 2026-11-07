# Starter Kit — Laboratorio N.º 5: Arquitectura Distribuida Multi-Ciudad

Este paquete es **andamiaje**, no la solución. Complementa la guía completa
del laboratorio (documento tipo paper) y el checklist de entregables
(Tabla 3 y Tabla 4 de la guía). Lea primero esa guía; este README solo
explica cómo está organizado el código.

## ¿Qué archivos NO debe tocar (ya resueltos)?

| Archivo | Por qué ya está resuelto |
|---|---|
| `interoperabilidad/models.py` | Es el modelo de datos de referencia (Figura 1 de la guía). Puede extenderlo si lo justifica en el paper, pero no es obligatorio. |
| `interoperabilidad/service_bus.py` | Mensajería en memoria funcional. No es el objetivo de aprendizaje de este laboratorio. |
| `interoperabilidad/terminology_service.py` | Base funcional mínima; extenderla es mérito opcional, no obligatorio. |
| `init-db/01-init-databases.sh` | Crea las 3 bases y la tabla `pacientes` con `fhir_patient_id` nulo (estado inicial 0%). |
| `tests/conftest.py`, `tests/test_service_bus.py` | Fixtures y test de infraestructura ya provista. |

## ¿Qué archivos SÍ debe completar?

| Archivo | Qué debe hacer |
|---|---|
| `solucion/mapper_estudiante.py` | Implementar los 5 métodos de `HL7v2ToFhirMapper` (ver contrato comentado en `interoperabilidad/mappers.py`). |
| `solucion/mpi_estudiante.py` | Implementar `calcular_score` y `resolver_identidad` (ver contrato en `interoperabilidad/mpi_service.py`). |
| `migrar_a_fhir.py` | Completar las funciones marcadas con `TODO(estudiante)` y la instanciación de sus clases al final del archivo. |
| `vista_unificada/app.py` y `templates/index.html` | Completar `calcular_cobertura()` y el refresco del dashboard en el navegador. |
| `docker-compose.yml` | Reemplazar `CAMBIAR_ESTA_CLAVE` por credenciales propias y crear `vista_unificada/Dockerfile`. |

## Flujo de trabajo sugerido (estilo TDD)

1. Instale dependencias: `pip install -r requirements.txt`
2. Ejecute los tests **antes** de programar, para ver su lista de tareas como fallas explícitas:
   ```bash
   pytest -v
   ```
   Es normal y esperado que al inicio casi todo falle con mensajes como
   `NotImplementedError: mapear_paciente: pendiente de implementar`.
   Esa lista de fallas **es** su lista de pendientes.
3. Implemente un método a la vez en `solucion/mapper_estudiante.py` o
   `solucion/mpi_estudiante.py`, y vuelva a correr `pytest -v` hasta
   que el test correspondiente pase.
4. Una vez todos los tests unitarios pasen, complete `migrar_a_fhir.py`
   y `vista_unificada/app.py` para la integración real contra Postgres
   y HAPI FHIR (los tests unitarios no cubren esta parte porque
   depende de sus propias credenciales y datos).
5. Levante el entorno completo: `docker compose up`, y verifique
   manualmente la transición de 0% a 100% de cobertura (Hito 3 del
   cronograma de la guía).

## Relación con el checklist de la guía (Tabla 4)

Pasar `pytest -v` en verde cubre parcialmente los ítems "Resolución de
identidad federada (MPI)" y aporta evidencia técnica para "Diagrama de
clases propio" (su implementación real debe reflejarse en ese
diagrama). No reemplaza las evidencias de ejecución en Docker
(capturas de 0% → 100%), que siguen siendo obligatorias.

## Importante sobre autoría

Los archivos de `interoperabilidad/` que se listan como "ya resueltos"
arriba pueden citarse en el paper como *"provisto por el docente"*. El
código que usted escriba en `solucion/`, `migrar_a_fhir.py` y
`vista_unificada/` es el que se evalúa como producción propia del
equipo (ver criterio de cierre, sección 12.4 de la guía).
