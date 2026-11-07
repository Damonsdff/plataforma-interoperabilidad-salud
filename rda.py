"""
rda.py — Resumen Digital de Atención (RDA): Composition + Bundle tipo "document" vía $document.

Cumple el entregable "Generación de Composition/Bundle" del Laboratorio 5 (Res. 1888/2025):
toma un encuentro REAL del paciente en HAPI (con los campos de la Res. 866/2021 ya migrados),
crea la Composition con sus secciones y pide a HAPI el documento con  GET /Composition/{id}/$document.

Uso:  python rda.py <id_patient_fhir> [<id_encounter>]      (guarda bundle_document.json)
"""
import json
import os
import sys

import requests

FHIR = os.environ.get("FHIR_BASE_URL", "http://localhost:8080/fhir")
CAB = {"Accept": "application/fhir+json", "Content-Type": "application/fhir+json"}


def _get(base, ruta, params=None):
    r = requests.get(f"{base}/{ruta}", params=params, headers=CAB, timeout=30)
    r.raise_for_status()
    return r.json()


def _lista(bundle):
    return [e["resource"] for e in bundle.get("entry", [])]


def _del_encuentro(base, tipo, patient_id, encounter_id):
    """Recursos de un tipo del paciente que pertenecen al encuentro (se filtra aquí porque no
    todos los tipos tienen el parámetro de búsqueda 'encounter' en R4)."""
    rs = _lista(_get(base, tipo, {"patient": f"Patient/{patient_id}", "_count": 200}))
    return [r for r in rs if r.get("encounter", {}).get("reference") == f"Encounter/{encounter_id}"]


def generar_rda(base, patient_id, encounter_id=None):
    paciente = _get(base, f"Patient/{patient_id}")
    encuentros = _lista(_get(base, "Encounter", {"subject": f"Patient/{patient_id}", "_count": 200}))
    if not encuentros:
        raise ValueError(f"Patient/{patient_id} no tiene encuentros: migre su historia primero.")
    if encounter_id:
        enc = next(e for e in encuentros if e["id"] == str(encounter_id))
    else:
        enc = max(encuentros, key=lambda e: e.get("period", {}).get("start", ""))
    eid = enc["id"]
    conds = _del_encuentro(base, "Condition", patient_id, eid)
    meds = _del_encuentro(base, "MedicationRequest", patient_id, eid)
    alergias = _del_encuentro(base, "AllergyIntolerance", patient_id, eid)
    obs = _del_encuentro(base, "Observation", patient_id, eid)
    refs = lambda rs: [{"reference": f"{r['resourceType']}/{r['id']}"} for r in rs]  # noqa: E731

    secciones = [{"title": "Motivo de la atención", "text": {
        "status": "generated", "div": "<div xmlns=\"http://www.w3.org/1999/xhtml\">" +
        (enc.get("reasonCode") or [{"text": "—"}])[0].get("text", "—") + "</div>"}}]
    for titulo, rs in (("Diagnósticos (CIE-10)", conds), ("Medicamentos y tecnologías", meds),
                       ("Alergias", alergias), ("Observaciones y riesgos", obs)):
        if rs:
            secciones.append({"title": titulo, "entry": refs(rs)})
    autor = [p["individual"] for p in enc.get("participant", []) if "individual" in p]
    if not autor:
        org = enc.get("serviceProvider")
        autor = [org] if org else []
    if not autor:
        raise ValueError("El encuentro no tiene responsable ni prestador: no se puede indicar el autor del documento.")
    composition = {
        "resourceType": "Composition", "status": "final",
        "type": {"coding": [{"system": "http://loinc.org", "code": "34133-9", "display": "Summarization of episode note"}]},
        "subject": {"reference": f"Patient/{patient_id}"}, "encounter": {"reference": f"Encounter/{eid}"},
        "date": enc.get("period", {}).get("end") or enc.get("period", {}).get("start"),
        "author": autor, "title": "Resumen Digital de Atención (RDA)", "section": secciones}
    r = requests.post(f"{base}/Composition", json=composition, headers=CAB, timeout=30)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"HAPI rechazó la Composition: {r.status_code} {r.text[:300]}")
    cid = r.json()["id"]
    documento = _get(base, f"Composition/{cid}/$document")
    return {"composition_id": cid, "encounter_id": eid, "bundle": documento,
            "paciente": paciente["id"], "tipos": [e["resource"]["resourceType"] for e in documento.get("entry", [])]}


if __name__ == "__main__":
    pid = sys.argv[1] if len(sys.argv) > 1 else "1"
    eid = sys.argv[2] if len(sys.argv) > 2 else None
    res = generar_rda(FHIR, pid, eid)
    b = res["bundle"]
    print(f"Bundle.type      = {b['type']} (esperado: document)")
    print(f"Numero entradas  = {len(b['entry'])}")
    print(f"Recursos         = {res['tipos']}")
    print(f"Primera entrada  = {res['tipos'][0]} (esperado: Composition)")
    with open("bundle_document.json", "w", encoding="utf-8") as f:
        json.dump(b, f, ensure_ascii=False, indent=2)
    print("Guardado en bundle_document.json")
