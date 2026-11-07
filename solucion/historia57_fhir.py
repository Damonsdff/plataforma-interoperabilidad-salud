"""
historia57_fhir.py — Mapeo de los 57 campos (Res. 866/2021) a recursos FHIR R4.

Funciones puras (sin red ni base de datos): reciben diccionarios y devuelven diccionarios FHIR.
La orquestación (qué se envía a HAPI y en qué orden) está en `enviar_atencion`.

Las extensiones que no existen en el núcleo de FHIR R4 usan el espacio de nombres propio
http://uajs.edu.co/fhir/StructureDefinition/ (decisión documentada en el informe).
"""
import re
from datetime import date, datetime

import campos57

EXT = "http://uajs.edu.co/fhir/StructureDefinition/"
CS = "http://uajs.edu.co/fhir/CodeSystem/"
UCUM = "http://unitsofmeasure.org"
CLASE_ENCUENTRO = {"01": "EMER", "02": "AMB", "03": "IMP", "04": "IMP", "05": "AMB", "06": "AMB"}
ROL_DX = {"AD": "Admission diagnosis", "DD": "Discharge diagnosis", "CM": "Comorbidity diagnosis"}
GENERO_FHIR = {"M": "male", "F": "female", "I": "other"}


ZONA_COLOMBIA = "-05:00"   # los datos de las sedes están en hora local de Colombia (UTC-5)


def _iso(v):
    """FHIR exige zona horaria en dateTime con hora: se agrega la de Colombia si la fecha es 'ingenua'."""
    if isinstance(v, datetime):
        texto = v.isoformat(timespec="seconds")
        return texto if v.tzinfo else texto + ZONA_COLOMBIA
    return v.isoformat() if isinstance(v, date) else str(v)


def _coding(sistema, catalogo, codigo):
    return {"system": CS + sistema, "code": str(codigo), "display": campos57.nombre_catalogo(catalogo, codigo)}


def _hay(v):
    return v is not None and str(v).strip() != ""


# ───────────────────────── Patient (campos 1-15, 24, 51-57) ─────────────────────────
def extensiones_paciente(p: dict) -> list:
    ext = []
    if _hay(p.get("pais_nacionalidad")):
        ext.append({"url": "http://hl7.org/fhir/StructureDefinition/patient-nationality", "extension": [
            {"url": "code", "valueCodeableConcept": {"coding": [{"system": "urn:iso:std:iso:3166", "code": p["pais_nacionalidad"]}]}}]})
    if _hay(p.get("edad")):
        unidad = {"1": ("años", "a"), "2": ("meses", "mo"), "3": ("días", "d")}.get(str(p.get("unidad_edad") or "1"), ("años", "a"))
        ext.append({"url": EXT + "edad", "valueQuantity": {"value": int(p["edad"]), "unit": unidad[0], "system": UCUM, "code": unidad[1]}})
    if _hay(p.get("genero")):
        ext.append({"url": "http://hl7.org/fhir/StructureDefinition/patient-genderIdentity",
                    "valueCodeableConcept": {"text": p["genero"]}})
    if _hay(p.get("ocupacion")):
        ext.append({"url": EXT + "ocupacion", "valueString": p["ocupacion"]})
    if p.get("voluntad_anticipada") is not None:
        ext.append({"url": EXT + "voluntad-anticipada", "valueBoolean": bool(p["voluntad_anticipada"])})
    if _hay(p.get("categoria_discapacidad")):
        ext.append({"url": EXT + "discapacidad", "valueCodeableConcept": {"text": p["categoria_discapacidad"]}})
    if _hay(p.get("etnia")):
        ext.append({"url": EXT + "etnia", "valueCodeableConcept": {"text": p["etnia"]}})
    if _hay(p.get("comunidad_etnica")):
        ext.append({"url": EXT + "comunidad-etnica", "valueString": p["comunidad_etnica"]})
    return ext


def completar_paciente_fhir(recurso: dict, p: dict) -> dict:
    """Agrega a un Patient básico (id, identifier, name, birthDate, gender) los campos 3, 6-15, 24 y 51-57."""
    if p.get("sexo") in GENERO_FHIR:
        recurso["gender"] = GENERO_FHIR[p["sexo"]]
    if p.get("tipo_documento"):
        recurso["identifier"][0]["type"] = {"coding": [{"system": CS + "tipo-documento", "code": p["tipo_documento"],
                                                          "display": campos57.nombre_catalogo("tipo_documento", p["tipo_documento"])}]}
    if recurso.get("name") and p.get("nombre_completo"):
        recurso["name"][0]["text"] = p["nombre_completo"]
    ext = extensiones_paciente(p)
    if ext:
        recurso["extension"] = ext
    direccion = {"use": "home"}
    if _hay(p.get("pais_residencia")):
        direccion["country"] = p["pais_residencia"]
    if _hay(p.get("municipio_residencia")):
        direccion["city"] = campos57.nombre_catalogo("municipio_residencia", p["municipio_residencia"])
        direccion["_city"] = {"extension": [{"url": EXT + "divipola",
                                              "valueCoding": {"system": "https://www.dane.gov.co/divipola", "code": p["municipio_residencia"]}}]}
    if _hay(p.get("direccion_residencia")):
        direccion["line"] = [p["direccion_residencia"]]
        direccion["text"] = p["direccion_residencia"]
    if _hay(p.get("zona_residencia")):
        direccion["extension"] = [{"url": EXT + "zona-residencia",
                                   "valueCoding": _coding("zona-residencia", "zona_residencia", p["zona_residencia"])}]
    if len(direccion) > 1:
        recurso["address"] = [direccion]
    telecom = []
    if _hay(p.get("telefono")):
        telecom.append({"system": "phone", "value": p["telefono"], "use": "mobile"})
    if _hay(p.get("correo")):
        telecom.append({"system": "email", "value": p["correo"]})
    if telecom:
        recurso["telecom"] = telecom
    if _hay(p.get("nombre_responsable")) or _hay(p.get("telefono_responsable")):
        contacto = {}
        if _hay(p.get("parentesco_responsable")):
            contacto["relationship"] = [{"coding": [_coding("parentesco", "parentesco_responsable", p["parentesco_responsable"])],
                                         "text": campos57.nombre_catalogo("parentesco_responsable", p["parentesco_responsable"])}]
        if _hay(p.get("nombre_responsable")):
            contacto["name"] = {"text": p["nombre_responsable"]}
        if _hay(p.get("telefono_responsable")):
            contacto["telecom"] = [{"system": "phone", "value": p["telefono_responsable"]}]
        recurso["contact"] = [contacto]
    return recurso


# ───────────────────────── recursos de apoyo ─────────────────────────
def mapear_practitioner(identificacion: str, nombre: str) -> dict:
    partes = (nombre or identificacion).split()
    return {"resourceType": "Practitioner",
            "identifier": [{"system": CS + "personal-salud", "value": identificacion}],
            "name": [{"text": nombre or identificacion, "family": partes[-1], "given": partes[:-1]}]}


def mapear_organizacion_prestador(codigo_prestador: str, nombre: str) -> dict:
    return {"resourceType": "Organization", "name": nombre,
            "identifier": [{"system": "https://prestadores.minsalud.gov.co/codigo-habilitacion", "value": codigo_prestador}]}


# ───────────────────────── Encounter (campos 16-23, 40-46, 50) ─────────────────────────
def mapear_encuentro(a: dict, patient_id: str, org_id: str | None = None, practitioner_id: str | None = None) -> dict:
    e = a.get("egreso") or {}
    enc = {"resourceType": "Encounter",
           "status": "finished" if e.get("fecha_salida") else "in-progress",
           "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
                     "code": CLASE_ENCUENTRO.get(a.get("entorno_atencion"), "AMB")},
           "type": [{"coding": [_coding("modalidad-entrega", "modalidad_entrega", a["modalidad_entrega"])]},
                    {"coding": [_coding("entorno-atencion", "entorno_atencion", a["entorno_atencion"])]}],
           "subject": {"reference": f"Patient/{patient_id}"},
           "period": {"start": _iso(a["fecha_ingreso"])},
           "reasonCode": [{"text": a["causa_atencion"]}],
           "hospitalization": {"admitSource": {"coding": [_coding("via-ingreso", "via_ingreso", a["via_ingreso"])]}},
           "extension": [{"url": EXT + "entidad-salud", "valueString": a["entidad_salud"]}]}
    if _hay(a.get("fecha_triage")):
        enc["extension"].append({"url": EXT + "triage-fecha", "valueDateTime": _iso(a["fecha_triage"])})
    if _hay(a.get("clasificacion_triage")):
        enc["priority"] = {"coding": [_coding("triage", "clasificacion_triage", a["clasificacion_triage"])],
                           "text": campos57.nombre_catalogo("clasificacion_triage", a["clasificacion_triage"])}
    if e.get("fecha_salida"):
        enc["period"]["end"] = _iso(e["fecha_salida"])
    if e.get("condicion_salida"):
        vivo = e["condicion_salida"] == "01"
        enc["hospitalization"]["dischargeDisposition"] = {
            "coding": [{"system": "http://terminology.hl7.org/CodeSystem/discharge-disposition",
                        "code": "home" if vivo else "exp", "display": "Home" if vivo else "Expired"},
                       _coding("condicion-salida", "condicion_salida", e["condicion_salida"])]}
    if _hay(e.get("tipo_incapacidad")):
        enc["extension"].append({"url": EXT + "incapacidad-tipo",
                                 "valueCoding": _coding("tipo-incapacidad", "tipo_incapacidad", e["tipo_incapacidad"])})
    if e.get("dias_incapacidad") is not None:
        enc["extension"].append({"url": EXT + "incapacidad-dias", "valueInteger": int(e["dias_incapacidad"])})
    if e.get("dias_lic_maternidad") is not None:
        enc["extension"].append({"url": EXT + "licencia-maternidad-dias", "valueInteger": int(e["dias_lic_maternidad"])})
    if org_id:
        enc["serviceProvider"] = {"reference": f"Organization/{org_id}"}
    if practitioner_id:
        enc["participant"] = [{"type": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/v3-ParticipationType",
                                                      "code": "DIS", "display": "discharger"}]}],
                               "individual": {"reference": f"Practitioner/{practitioner_id}"}}]
    return enc


# ───────────────────────── Condition (campos 33-39, 42) ─────────────────────────
def mapear_condicion_cie10(codigo: str, patient_id: str, encounter_id: str | None, rol: str,
                           tipo_codigo: str | None = None, causa_muerte: bool = False) -> dict:
    cond = {"resourceType": "Condition",
            "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "active"}]},
            "verificationStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-ver-status", "code": "confirmed"}]},
            "code": {"coding": [{"system": "http://hl7.org/fhir/sid/icd-10", "code": codigo,
                                 "display": campos57.CIE10.get(codigo, codigo)}]},
            "subject": {"reference": f"Patient/{patient_id}"}}
    if causa_muerte:
        cond["category"] = [{"text": "Diagnóstico de muerte (causa de la defunción)"}]
    else:
        cond["category"] = [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-category",
                                         "code": "encounter-diagnosis"}], "text": ROL_DX.get(rol, rol)}]
    if encounter_id:
        cond["encounter"] = {"reference": f"Encounter/{encounter_id}"}
    if tipo_codigo:
        cond["extension"] = [{"url": EXT + "tipo-diagnostico",
                              "valueCoding": _coding("tipo-diagnostico", "tipo_diagnostico", tipo_codigo)}]
    return cond


def condiciones_de_atencion(a: dict):
    """[(rol, codigo, tipo, es_muerte)] a partir de diagnostico/egreso de una atención."""
    d, e, salida = a.get("diagnostico") or {}, a.get("egreso") or {}, []
    if _hay(d.get("dx_ingreso")):
        salida.append(("AD", d["dx_ingreso"], d.get("tipo_dx_ingreso"), False))
    if _hay(d.get("dx_egreso")):
        salida.append(("DD", d["dx_egreso"], d.get("tipo_dx_egreso"), False))
    for k in ("dx_rel1", "dx_rel2", "dx_rel3"):
        if _hay(d.get(k)):
            salida.append(("CM", d[k], "02", False))
    if _hay(e.get("dx_muerte")):
        salida.append(("DD", e["dx_muerte"], None, True))
    return salida


# ───────────────────────── MedicationRequest (campos 25-32) ─────────────────────────
def _cantidad(texto):
    m = re.match(r"^\s*([\d.,]+)\s*([A-Za-zµ%/]+)?", texto or "")
    if not m:
        return None
    q = {"value": float(m.group(1).replace(",", "."))}
    if m.group(2):
        q["unit"] = m.group(2)
    return q


def mapear_medicacion(t: dict, patient_id: str, encounter_id: str, practitioner_id: str | None) -> dict:
    dosis = {"text": f"{t.get('dosis') or ''} {t.get('frecuencia') or ''}".strip()}
    q = _cantidad(t.get("dosis")) if _hay(t.get("dosis")) else None
    if q:
        dosis["doseAndRate"] = [{"doseQuantity": q}]
    if _hay(t.get("frecuencia")):
        timing = {"code": {"text": t["frecuencia"]}}
        m = re.search(r"cada\s+(\d+)\s*hora", t["frecuencia"], re.I)
        if m:
            timing["repeat"] = {"frequency": 1, "period": float(m.group(1)), "periodUnit": "h"}
        dosis["timing"] = timing
    if _hay(t.get("via_administracion")):
        dosis["route"] = {"coding": [_coding("via-administracion", "via_administracion", t["via_administracion"])]}
    req = {"resourceType": "MedicationRequest", "status": "completed", "intent": "order",
           "medicationCodeableConcept": {"text": t["descripcion_medicamento"]},
           "subject": {"reference": f"Patient/{patient_id}"}, "encounter": {"reference": f"Encounter/{encounter_id}"},
           "dosageInstruction": [dosis]}
    dispense = {}
    if t.get("dias_tratamiento") is not None:
        dispense["expectedSupplyDuration"] = {"value": int(t["dias_tratamiento"]), "unit": "días", "system": UCUM, "code": "d"}
    if t.get("unidades_aplicadas") is not None:
        dispense["quantity"] = {"value": int(t["unidades_aplicadas"]), "unit": "unidades"}
    if dispense:
        req["dispenseRequest"] = dispense
    if _hay(t.get("finalidad_tecnologia")):
        req["reasonCode"] = [{"coding": [_coding("finalidad-tecnologia", "finalidad_tecnologia", t["finalidad_tecnologia"])],
                              "text": campos57.nombre_catalogo("finalidad_tecnologia", t["finalidad_tecnologia"])}]
    if practitioner_id:
        req["requester"] = {"reference": f"Practitioner/{practitioner_id}"}
    return req


# ───────────────────────── antecedentes (campos 47-49) ─────────────────────────
def mapear_alergia(texto: str, patient_id: str, encounter_id: str) -> dict:
    return {"resourceType": "AllergyIntolerance",
            "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/allergyintolerance-clinical", "code": "active"}]},
            "code": {"text": texto.strip()}, "patient": {"reference": f"Patient/{patient_id}"},
            "encounter": {"reference": f"Encounter/{encounter_id}"}}


def mapear_antecedente_familiar(texto: str, patient_id: str) -> dict:
    return {"resourceType": "FamilyMemberHistory", "status": "completed", "patient": {"reference": f"Patient/{patient_id}"},
            "relationship": {"text": "Familiar"}, "condition": [{"code": {"text": texto}}]}


def mapear_riesgo_ocupacional(texto: str, patient_id: str, encounter_id: str) -> dict:
    return {"resourceType": "Observation", "status": "final",
            "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "social-history"}]}],
            "code": {"text": "Riesgos ocupacionales"}, "subject": {"reference": f"Patient/{patient_id}"},
            "encounter": {"reference": f"Encounter/{encounter_id}"}, "valueString": texto}


# ───────────────────────── envío orquestado ─────────────────────────
def enviar_atencion(a: dict, patient_id: str, post, put, cache: dict | None = None) -> dict:
    """Envía una atención completa a FHIR. `post(recurso)->id` y `put(recurso)` los provee quien llama
    (permite usar requests, un servidor simulado o pruebas). Orden: apoyo → Encounter → Condition/… → Encounter.diagnosis."""
    e = a.get("egreso") or {}
    cache = {} if cache is None else cache

    def unico(recurso):
        """Organization/Practitioner se crean una sola vez por identificador (evita duplicados en HAPI)."""
        clave = (recurso["resourceType"], recurso["identifier"][0]["value"])
        if clave not in cache:
            cache[clave] = post(recurso)
        return cache[clave]

    org_id = unico(mapear_organizacion_prestador(e["codigo_prestador"], f"Prestador {e['codigo_prestador']}")) \
        if _hay(e.get("codigo_prestador")) else None
    prac_egreso = unico(mapear_practitioner("egreso-" + re.sub(r"\W+", "-", e["responsable_egreso"].lower()), e["responsable_egreso"])) \
        if _hay(e.get("responsable_egreso")) else None
    enc_id = post(mapear_encuentro(a, patient_id, org_id, prac_egreso))
    creados = {"Encounter": [enc_id], "Condition": [], "MedicationRequest": [], "AllergyIntolerance": [],
               "FamilyMemberHistory": [], "Observation": [], "Practitioner": [prac_egreso] if prac_egreso else [],
               "Organization": [org_id] if org_id else []}
    diagnosticos = []
    for rol, codigo, tipo, muerte in condiciones_de_atencion(a):
        cid = post(mapear_condicion_cie10(codigo, patient_id, enc_id, rol, tipo, muerte))
        creados["Condition"].append(cid)
        if not muerte:
            diagnosticos.append({"condition": {"reference": f"Condition/{cid}"},
                                 "use": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/diagnosis-role", "code": rol}]},
                                 "rank": len(diagnosticos) + 1})
    if diagnosticos:
        enc = mapear_encuentro(a, patient_id, org_id, prac_egreso)
        enc["id"], enc["diagnosis"] = enc_id, diagnosticos
        put(enc)
    for t in a.get("tecnologias", []):
        if not _hay(t.get("descripcion_medicamento")):
            continue
        prac = None
        if _hay(t.get("id_personal_salud")):
            prac = unico(mapear_practitioner(t["id_personal_salud"], t.get("nombre_personal_salud") or t["id_personal_salud"]))
            creados["Practitioner"].append(prac)
        creados["MedicationRequest"].append(post(mapear_medicacion(t, patient_id, enc_id, prac)))
    if _hay(e.get("alergias")):
        for alergia in [x for x in re.split(r"[,;]", e["alergias"]) if x.strip()]:
            creados["AllergyIntolerance"].append(post(mapear_alergia(alergia, patient_id, enc_id)))
    if _hay(e.get("antecedente_familiar")):
        creados["FamilyMemberHistory"].append(post(mapear_antecedente_familiar(e["antecedente_familiar"], patient_id)))
    if _hay(e.get("riesgos_ocupacionales")):
        creados["Observation"].append(post(mapear_riesgo_ocupacional(e["riesgos_ocupacionales"], patient_id, enc_id)))
    return creados
