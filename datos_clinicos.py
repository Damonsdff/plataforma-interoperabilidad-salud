"""
datos_clinicos.py — Genera la historia clínica (Encounter + Condition +
Observation) de cada paciente que ya está en HAPI FHIR.

Cumple el TODO(estudiante) paso 3 de migrar_a_fhir.py: asociar
encuentros, condiciones y observaciones a cada paciente migrado.

Uso desde terminal (carga datos para TODOS los pacientes sin historia):
    python datos_clinicos.py
"""
import os
import sys
from datetime import datetime, timezone

import requests

FHIR_BASE_URL = os.environ.get("FHIR_BASE_URL", "http://localhost:8080/fhir")
CABECERAS = {"Content-Type": "application/fhir+json", "Accept": "application/fhir+json"}

# (cie10, descripcion, loinc, nombre_loinc, valor, unidad, codigo_ucum)
PLANTILLAS = [
    ("I10", "Hipertensión esencial (primaria)", "8480-6", "Systolic blood pressure", 150, "mmHg", "mm[Hg]"),
    ("E11.9", "Diabetes mellitus tipo 2 sin complicaciones", "2339-0", "Glucose [Mass/volume] in Blood", 135, "mg/dL", "mg/dL"),
    ("J45.9", "Asma, no especificada", "8867-4", "Heart rate", 92, "lpm", "/min"),
    ("E66.9", "Obesidad, no especificada", "29463-7", "Body weight", 98, "kg", "kg"),
    ("J06.9", "Infección aguda de vías respiratorias superiores", "8310-5", "Body temperature", 38.2, "°C", "Cel"),
]


def _post(base_url, recurso):
    r = requests.post(f"{base_url}/{recurso['resourceType']}", json=recurso,
                      headers=CABECERAS, timeout=30)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"HAPI rechazó {recurso['resourceType']}: {r.status_code} {r.text[:200]}")
    return r.json()["id"]


def post_recurso(recurso, base_url=None):
    """POST de un recurso FHIR a HAPI; devuelve el id asignado."""
    return _post(base_url or os.environ.get("FHIR_BASE_URL", FHIR_BASE_URL), recurso)


def put_recurso(recurso, base_url=None):
    """PUT (actualización) de un recurso FHIR que ya tiene id."""
    base = base_url or os.environ.get("FHIR_BASE_URL", FHIR_BASE_URL)
    r = requests.put(f"{base}/{recurso['resourceType']}/{recurso['id']}", json=recurso, headers=CABECERAS, timeout=30)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"HAPI rechazó PUT {recurso['resourceType']}: {r.status_code} {r.text[:200]}")
    return r.json()["id"]


def crear_encuentro(base_url, patient_id):
    ahora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return _post(base_url, {
        "resourceType": "Encounter", "status": "finished",
        "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "AMB"},
        "subject": {"reference": f"Patient/{patient_id}"},
        "period": {"start": ahora, "end": ahora},
    })


def crear_condicion(base_url, patient_id, encounter_id, codigo, descripcion):
    return _post(base_url, {
        "resourceType": "Condition",
        "subject": {"reference": f"Patient/{patient_id}"},
        "encounter": {"reference": f"Encounter/{encounter_id}"},
        "code": {"coding": [{"system": "http://hl7.org/fhir/sid/icd-10",
                             "code": codigo, "display": descripcion}]},
    })


def crear_observacion(base_url, patient_id, encounter_id, loinc, nombre, valor, unidad, ucum):
    return _post(base_url, {
        "resourceType": "Observation", "status": "final",
        "subject": {"reference": f"Patient/{patient_id}"},
        "encounter": {"reference": f"Encounter/{encounter_id}"},
        "code": {"coding": [{"system": "http://loinc.org", "code": loinc, "display": nombre}]},
        "valueQuantity": {"value": float(valor), "unit": unidad,
                          "system": "http://unitsofmeasure.org", "code": ucum},
    })


def crear_historia_demo(base_url, patient_id):
    """Crea 1 Encounter + 1 Condition + 1 Observation para el paciente."""
    try:
        indice = int(patient_id)
    except ValueError:
        indice = sum(ord(c) for c in str(patient_id))
    cie, desc, loinc, nombre, valor, unidad, ucum = PLANTILLAS[indice % len(PLANTILLAS)]
    enc = crear_encuentro(base_url, patient_id)
    con = crear_condicion(base_url, patient_id, enc, cie, desc)
    obs = crear_observacion(base_url, patient_id, enc, loinc, nombre, valor, unidad, ucum)
    return {"encounter": enc, "condition": con, "observation": obs}


def _total(base_url, tipo, params):
    r = requests.get(f"{base_url}/{tipo}", params={**params, "_summary": "count"},
                     headers=CABECERAS, timeout=30)
    return r.json().get("total", 0)


def cargar_para_todos(base_url=FHIR_BASE_URL):
    url = f"{base_url}/Patient?_count=100"
    creados = omitidos = 0
    while url:
        pagina = requests.get(url, headers=CABECERAS, timeout=30).json()
        for entrada in pagina.get("entry", []):
            pid = entrada["resource"]["id"]
            if _total(base_url, "Condition", {"subject": f"Patient/{pid}"}) > 0:
                omitidos += 1
                continue
            crear_historia_demo(base_url, pid)
            creados += 1
            print(f"  Patient/{pid}: historia creada")
        url = next((l["url"] for l in pagina.get("link", []) if l["relation"] == "next"), None)
    print(f"Listo. Historias creadas: {creados} | pacientes que ya tenían historia: {omitidos}")


if __name__ == "__main__":
    base = sys.argv[1] if len(sys.argv) > 1 else FHIR_BASE_URL
    cargar_para_todos(base)
