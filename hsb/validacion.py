"""validacion.py — Reglas de validación ANTES de transformar. Devuelve la lista de motivos de rechazo."""
import re
from datetime import date, datetime

from .terminologia import CIE10_RE, LOINC_RE


def _fecha_ok(txt):
    try:
        datetime.fromisoformat(txt)
        return True
    except (ValueError, TypeError):
        return False


def validar(sol, terminologia):
    """Modifica `sol` (rellena cie10/loinc mapeados) y devuelve los motivos de rechazo (lista vacía = válido)."""
    m = []
    if not 1 <= sol["sede"] <= 3:
        m.append(f"sede no válida ('{sol['sede_texto']}'): debe estar entre 1 y 3")
    doc = sol["documento"]
    if not doc.isdigit():
        m.append(f"documento no numérico ('{doc}')")
    elif not 4 <= len(doc) <= 15:
        m.append(f"documento de {len(doc)} dígitos (debe tener entre 4 y 15)")
    if not (sol["apellido"] or sol["nombres"]):
        m.append("nombre vacío")
    if sol["sexo"] not in ("M", "F", "O"):
        m.append(f"sexo no válido ('{sol['sexo']}'): use M, F u O")
    nac = sol["nacimiento"]
    if not nac or "T" in nac or not _fecha_ok(nac):
        m.append(f"fecha de nacimiento no válida ('{sol['nacimiento_raw']}')")
    elif date.fromisoformat(nac) > date.today():
        m.append("fecha de nacimiento en el futuro")
    if sol["fecha_atencion"] and not _fecha_ok(sol["fecha_atencion"]):
        m.append(f"fecha de atención no válida ('{sol['fecha_atencion']}')")
    if sol["triage"] and sol["triage"] not in ("1", "2", "3", "4", "5"):
        m.append(f"triage no válido ('{sol['triage']}'): use 1 a 5")

    # Diagnóstico: CSV trae texto libre (se mapea con ref_terminologia); HL7 debe traer CIE-10 directo.
    if sol["formato"] == "CSV":
        if not sol["dx_local"]:
            m.append("diagnóstico vacío")
        else:
            r = terminologia.dx_a_cie10(sol["dx_local"])
            if r is None:
                m.append(f"diagnóstico '{sol['dx_local']}' sin mapeo a CIE-10")
            else:
                sol["cie10"], sol["cie10_desc"] = r
    elif sol["cie10"]:
        if not CIE10_RE.match(sol["cie10"]) or sol["dx_sistema"] in ("L", "99LOC"):
            m.append(f"diagnóstico '{sol['cie10']}' sin mapeo a CIE-10 (el HL7 debe enviar un código CIE-10)")
        elif not sol["cie10_desc"]:
            sol["cie10_desc"] = terminologia.cie10_desc.get(sol["cie10"], sol["cie10"])

    if sol["tipo"] not in ("ADT", "ORU", "CSV"):
        m.append(f"tipo de mensaje no soportado ('{sol['tipo']}'): use ADT^A01 u ORU^R01")
    if sol["tipo"] == "ORU":
        if not sol["obx"]:
            m.append("ORU sin segmentos OBX")
        for i, o in enumerate(sol["obx"], 1):
            cod = o["codigo"]
            if o["sistema"] not in ("LN", "LOINC"):
                r = terminologia.prueba_a_loinc(cod)
                if r is None:
                    m.append(f"OBX-{i}: prueba '{cod}' sin mapeo a LOINC")
                    continue
                o["codigo"], o["descripcion"] = r[0], r[1]
                o["unidad"] = o["unidad"] or r[2]
            elif not LOINC_RE.match(cod):
                m.append(f"OBX-{i}: código LOINC con formato inválido ('{cod}')")
            if o["tipo_valor"] == "NM" and not re.fullmatch(r"-?\d+([.,]\d+)?", o["valor"]):
                m.append(f"OBX-{i}: valor no numérico ('{o['valor']}')")
    if sol["formato"] == "HL7" and not sol["id_mensaje"]:
        m.append("MSH-10 vacío: no hay clave de idempotencia")
    return m
