"""
migrar_a_fhir.py — ESQUELETO PROVISTO / COMPLETAR POR EL ESTUDIANTE.

Orquesta la migración de una sede: lee pacientes pendientes
(fhir_patient_id NULL), los mapea a FHIR con su implementación de
HL7v2ToFhirMapper, los envía al servidor HAPI FHIR, intenta resolver
identidad federada con su MPIService, y publica el evento resultante
en el HealthServiceBus.

Uso esperado (a completar):
    python migrar_a_fhir.py --sede historia_clinica_sede1

Este archivo NO debe quedar como está: los TODO marcan exactamente
dónde va la lógica de negocio. La orquestación general (orden de
pasos) sí se las entregamos para que no tengan que diseñarla desde cero.
"""
import argparse
import os

import psycopg2

import datos_clinicos
import esquema57
from interoperabilidad.models import Paciente, Sede
from interoperabilidad.service_bus import HealthServiceBus
from interoperabilidad.terminology_service import TerminologyService
from solucion import historia57_fhir
from solucion.mapper_estudiante import MapperEstudiante
from solucion.mpi_estudiante import MPIEstudiante

FHIR_BASE_URL = os.environ.get("FHIR_BASE_URL", "http://localhost:8080/fhir")

SEDES = {
    "historia_clinica_sede1": Sede(1, "Sincelejo", "Meditech", "OpenMRS", "Appliance dedicado"),
    "historia_clinica_sede2": Sede(2, "Cartagena", "Cerner", "Vendor propio", "Appliance imagenología"),
    "historia_clinica_sede3": Sede(3, "Corozal", "SIHOS", "Historia Clinica Propia", "PACS local"),
}


def _conectar(nombre_bd: str):
    return esquema57.conectar(nombre_bd)


CAMPOS_EXTRA = ["pais_nacionalidad", "edad", "unidad_edad", "genero", "ocupacion", "voluntad_anticipada",
                "categoria_discapacidad", "pais_residencia", "municipio_residencia", "etnia", "comunidad_etnica",
                "zona_residencia", "direccion_residencia", "telefono", "correo", "nombre_responsable",
                "parentesco_responsable", "telefono_responsable"]


def obtener_pacientes_pendientes(nombre_bd: str):
    sede = SEDES[nombre_bd]
    conn = _conectar(nombre_bd)
    cur = conn.cursor()
    esquema57.asegurar_esquema(conn)
    cur.execute("""
        SELECT id_paciente, documento_identidad, tipo_documento,
               nombre_completo, fecha_nacimiento, sexo, """ + ", ".join(CAMPOS_EXTRA) + """
        FROM pacientes WHERE fhir_patient_id IS NULL
    """)
    filas = cur.fetchall()
    conn.close()

    pacientes = []
    for fila in filas:
        pacientes.append(Paciente(
            id_paciente=fila[0],
            documento_identidad=fila[1],
            tipo_documento=fila[2],
            nombre_completo=fila[3],
            fecha_nacimiento=fila[4],
            sexo=fila[5],
            sede_origen=sede,
            extra=dict(zip(CAMPOS_EXTRA, fila[6:])),
        ))
    return pacientes


def actualizar_fhir_patient_id(nombre_bd: str, id_paciente, fhir_id: str) -> None:
    conn = _conectar(nombre_bd)
    cur = conn.cursor()
    cur.execute(
        "UPDATE pacientes SET fhir_patient_id = %s WHERE id_paciente = %s",
        (fhir_id, str(id_paciente)),
    )
    conn.commit()
    conn.close()


def obtener_candidatos_otras_sedes(paciente, sedes_restantes):
    candidatos = []
    for nombre_bd in sedes_restantes:
        sede = SEDES[nombre_bd]
        conn = _conectar(nombre_bd)
        cur = conn.cursor()
        cur.execute("""
            SELECT id_paciente, documento_identidad, tipo_documento,
                   nombre_completo, fecha_nacimiento, sexo
            FROM pacientes
        """)
        filas = cur.fetchall()
        conn.close()

        for fila in filas:
            candidatos.append(Paciente(
                id_paciente=fila[0],
                documento_identidad=fila[1],
                tipo_documento=fila[2],
                nombre_completo=fila[3],
                fecha_nacimiento=fila[4],
                sexo=fila[5],
                sede_origen=sede,
            ))
    return candidatos


def enviar_atenciones_pendientes(nombre_bd: str, id_paciente, fhir_id: str, cache: dict) -> int:
    """Envía a FHIR las atenciones (campos 16-50) aún no migradas de un paciente. Devuelve cuántas envió."""
    conn = _conectar(nombre_bd)
    try:
        atenciones = esquema57.leer_atenciones(conn, id_paciente, solo_pendientes=True)
        enviadas = 0
        for a in atenciones:
            if a["diagnostico"] is None or a["egreso"] is None:
                continue  # el médico aún no completa diagnóstico y egreso
            creados = historia57_fhir.enviar_atencion(a, fhir_id, datos_clinicos.post_recurso, datos_clinicos.put_recurso, cache)
            esquema57.marcar_atencion_migrada(conn, a["id_atencion"], creados["Encounter"][0])
            enviadas += 1
        return enviadas
    finally:
        conn.close()


def sincronizar_pacientes_migrados(nombre_bd: str, cache: dict | None = None) -> int:
    """Atenciones nuevas de pacientes que ya estaban migrados (p. ej. registradas luego por el médico)."""
    cache = {} if cache is None else cache
    conn = _conectar(nombre_bd)
    cur = conn.cursor()
    esquema57.asegurar_esquema(conn)
    cur.execute("SELECT id_paciente, fhir_patient_id FROM pacientes WHERE fhir_patient_id IS NOT NULL")
    migrados = cur.fetchall()
    conn.close()
    return sum(enviar_atenciones_pendientes(nombre_bd, pid, fid, cache) for pid, fid in migrados)


def migrar_sede(nombre_bd: str, mapper, mpi, bus: HealthServiceBus) -> None:
    pendientes = obtener_pacientes_pendientes(nombre_bd)
    cache = {}  # Organization/Practitioner ya creados en esta corrida

    for paciente in pendientes:
        # 1) Mapear y enviar el recurso Patient
        recurso_patient = mapper.mapear_paciente(paciente)
        respuesta = mapper.enviar_a_servidor_fhir(recurso_patient, FHIR_BASE_URL)
        fhir_id = respuesta.get("id")

        # 2) Actualizar el marcador de migración en la base de origen
        actualizar_fhir_patient_id(nombre_bd, paciente.id_paciente, fhir_id)

        # 3) Historia clínica asociada (campos 16-50 de la Res. 866/2021): Encounter, Condition,
        #    MedicationRequest, AllergyIntolerance, etc. Si el paciente aún no tiene atenciones
        #    completas, se crea la historia mínima de demostración (Encounter+Condition+Observation).
        try:
            enviadas = enviar_atenciones_pendientes(nombre_bd, paciente.id_paciente, fhir_id, cache)
            if enviadas == 0:
                datos_clinicos.crear_historia_demo(FHIR_BASE_URL, fhir_id)
        except Exception as error:
            print(f"  Aviso: no se pudo crear la historia de Patient/{fhir_id}: {error}")

        # 4) Intentar resolver identidad federada contra otras sedes
        sedes_restantes = [s for s in SEDES if s != nombre_bd]
        candidatos = obtener_candidatos_otras_sedes(paciente, sedes_restantes)
        identidad = mpi.resolver_identidad(paciente, candidatos)

        # 5) Publicar evento para que la vista unificada se refresque
        bus.publicar("paciente.federado", {
            "sede": nombre_bd,
            "id_paciente": str(paciente.id_paciente),
            "fhir_id": fhir_id,
            "identidad_federada": identidad is not None,
        })

    # 6) Atenciones nuevas de pacientes ya migrados antes
    try:
        sincronizar_pacientes_migrados(nombre_bd, cache)
    except Exception as error:
        print(f"  Aviso: no se pudieron sincronizar atenciones pendientes: {error}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sede", required=True, help="p. ej. historia_clinica_sede1")
    args = parser.parse_args()

    # TODO(estudiante): instanciar aquí SU implementación concreta de
    # HL7v2ToFhirMapper y MPIService (subclases de las interfaces en
    # interoperabilidad/mappers.py y mpi_service.py).
    mi_mapper = MapperEstudiante()
    mi_mpi = MPIEstudiante()
    bus = HealthServiceBus()

    if mi_mapper is None or mi_mpi is None:
        raise SystemExit(
            "Complete la instanciación de mi_mapper y mi_mpi en migrar_a_fhir.py "
            "antes de ejecutar la migración."
        )

    migrar_sede(args.sede, mi_mapper, mi_mpi, bus)
    print(f"Migración de {args.sede} terminada.")
