"""normalizador.py — Solicitud validada -> Bundle FHIR R4 (transaction con PUT: reenviar es seguro / idempotente).

Recursos: Patient, Practitioner, Encounter, Condition (CIE-10), Observation (LOINC).
Los ids son deterministas (sede + documento / visita) para que un reenvío sobrescriba y no duplique.
"""
import hashlib

CIE10 = "http://hl7.org/fhir/sid/icd-10"
LOINC = "http://loinc.org"
UCUM = "http://unitsofmeasure.org"
SEDE_CS = "http://uajs.edu.co/fhir/CodeSystem/sede"
DOC_SYS = "http://uajs.edu.co/tipo-documento/"
CLASE = {"E": "EMER", "O": "AMB", "I": "IMP"}
GENERO = {"M": "male", "F": "female", "O": "other"}


def _tz(f):
    return f if (not f or "T" not in f or f[-6] in "+-") else f + "-05:00"


def ids(sol):
    pid = f"s{sol['sede']}-{sol['documento']}"
    visita = sol["visita"] or hashlib.sha1(f"{sol['documento']}|{sol['fecha_atencion']}".encode()).hexdigest()[:10]
    return pid, f"enc-s{sol['sede']}-{visita}"


def construir_bundle(sol):
    pid, eid = ids(sol)
    etiqueta = {"tag": [{"system": SEDE_CS, "code": str(sol["sede"])}]}
    entradas = []

    def put(recurso):
        entradas.append({"resource": recurso, "request": {"method": "PUT", "url": f"{recurso['resourceType']}/{recurso['id']}"}})

    nombre = {"family": sol["apellido"], "given": [g for g in sol["nombres"].split() if g]}
    nombre["text"] = (sol.get("nombre_completo") or f"{sol['nombres']} {sol['apellido']}").strip()
    put({"resourceType": "Patient", "id": pid, "meta": etiqueta,
         "identifier": [{"system": DOC_SYS + sol["tipo_documento"], "value": sol["documento"]}],
         "name": [nombre], "birthDate": sol["nacimiento"], "gender": GENERO.get(sol["sexo"], "unknown")})

    enc = {"resourceType": "Encounter", "id": eid, "meta": etiqueta,
           "status": "in-progress" if sol["tipo"] == "ADT" else "finished",
           "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": CLASE.get(sol["clase"], "AMB")},
           "subject": {"reference": f"Patient/{pid}"}}
    if sol["fecha_atencion"]:
        enc["period"] = {"start": _tz(sol["fecha_atencion"])}
    if sol["triage"]:
        enc["priority"] = {"coding": [{"system": "http://uajs.edu.co/fhir/CodeSystem/triage", "code": sol["triage"]}],
                           "text": f"Triage {sol['triage']}"}
    if sol["medico_id"]:
        prac_id = f"prac-{sol['medico_id'].lower()}"
        prac = {"resourceType": "Practitioner", "id": prac_id,
                "identifier": [{"system": "http://uajs.edu.co/profesional", "value": sol["medico_id"]}]}
        if sol["medico_apellido"]:
            prac["name"] = [{"family": sol["medico_apellido"], "given": [sol["medico_nombre"]] if sol["medico_nombre"] else []}]
        put(prac)
        enc["participant"] = [{"individual": {"reference": f"Practitioner/{prac_id}"}}]
    put(enc)

    if sol["cie10"]:
        put({"resourceType": "Condition", "id": f"cond-{eid}", "meta": etiqueta,
             "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "active"}]},
             "code": {"coding": [{"system": CIE10, "code": sol["cie10"], "display": sol["cie10_desc"] or sol["cie10"]}]},
             "subject": {"reference": f"Patient/{pid}"}, "encounter": {"reference": f"Encounter/{eid}"}})
    for i, o in enumerate(sol["obx"], 1):
        obs = {"resourceType": "Observation", "id": f"obs-{eid}-{i}", "meta": etiqueta, "status": "final",
               "code": {"coding": [{"system": LOINC, "code": o["codigo"], "display": o["descripcion"] or o["codigo"]}]},
               "subject": {"reference": f"Patient/{pid}"}, "encounter": {"reference": f"Encounter/{eid}"}}
        if sol["fecha_atencion"]:
            obs["effectiveDateTime"] = _tz(sol["fecha_atencion"])
        if o["tipo_valor"] == "NM":
            obs["valueQuantity"] = {"value": float(o["valor"].replace(",", ".")), "unit": o["unidad"],
                                    "system": UCUM, "code": o["unidad"]}
        else:
            obs["valueString"] = o["valor"]
        put(obs)
    return {"resourceType": "Bundle", "type": "transaction", "entry": entradas}
