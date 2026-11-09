"""hl7.py — Lector mínimo de mensajes HL7 v2 (ADT^A01 y ORU^R01) y del CSV legado de la sede.

No valida: solo extrae los campos a un diccionario común ("solicitud") que luego
validan `validacion.py` y transforma `normalizador.py`. Si el texto no es HL7 lanza HL7Error.
"""
import csv
import io
import re
from datetime import datetime


class HL7Error(ValueError):
    pass


def _campo(partes, n):
    """Campo n (1-based) de un segmento ya separado por '|'. En MSH el separador cuenta como MSH-1."""
    i = n - 1 if partes[0] == "MSH" else n
    return partes[i] if i < len(partes) else ""


def _comp(valor, k):
    """Componente k (1-based) de un campo separado por '^'."""
    c = valor.split("^")
    return c[k - 1].strip() if k - 1 < len(c) else ""


def fecha_hl7(v):
    """'20261107101500' | '202611071015' | '20261107' -> '2026-11-07T10:15:00' (o '2026-11-07'). '' si no aplica."""
    v = (v or "").strip()
    if not re.fullmatch(r"\d{8}(\d{4}(\d{2})?)?", v):
        return ""
    try:
        if len(v) == 8:
            return datetime.strptime(v, "%Y%m%d").date().isoformat()
        return datetime.strptime(v.ljust(14, "0"), "%Y%m%d%H%M%S").isoformat()
    except ValueError:
        return ""


def parsear_hl7(texto):
    segs = [s for s in re.split(r"[\r\n]+", (texto or "").strip()) if s]
    if not segs or not segs[0].startswith("MSH|"):
        raise HL7Error("El mensaje no empieza con un segmento MSH")
    seg = {}
    for s in segs:
        seg.setdefault(s[:3], []).append(s.split("|"))
    msh = seg["MSH"][0]
    tipo = _comp(_campo(msh, 9), 1)
    sede_txt = _campo(msh, 4)
    m = re.search(r"(\d+)\s*$", sede_txt)
    pid = seg.get("PID", [[""]])[0]
    pv1 = seg.get("PV1", [[""]])[0]
    dg1 = seg.get("DG1", [[""]])[0]
    sol = {
        "formato": "HL7", "tipo": tipo, "id_mensaje": _campo(msh, 10).strip(),
        "sede_texto": sede_txt, "sede": int(m.group(1)) if m else 0,
        "fecha_mensaje": fecha_hl7(_campo(msh, 7)),
        "tipo_documento": "CC",
        "documento": _comp(_campo(pid, 3), 1),
        "apellido": _comp(_campo(pid, 5), 1), "nombres": _comp(_campo(pid, 5), 2),
        "nacimiento": fecha_hl7(_campo(pid, 7)) if _campo(pid, 7) else "", "nacimiento_raw": _campo(pid, 7),
        "sexo": _campo(pid, 8).strip(),
        "clase": _campo(pv1, 2).strip(),
        "medico_id": _comp(_campo(pv1, 7), 1), "medico_apellido": _comp(_campo(pv1, 7), 2),
        "medico_nombre": _comp(_campo(pv1, 7), 3),
        "visita": _campo(pv1, 19).strip(),
        "fecha_atencion": fecha_hl7(_campo(pv1, 44)) or fecha_hl7(_campo(msh, 7)),
        "triage": "", "dx_local": "",
        "cie10": "", "cie10_desc": "", "dx_sistema": "",
        "obx": [],
    }
    if dg1 != [""] and len(dg1) > 3:
        sol["cie10"] = _comp(_campo(dg1, 3), 1)
        sol["cie10_desc"] = _comp(_campo(dg1, 3), 2)
        sol["dx_sistema"] = _comp(_campo(dg1, 3), 3)
    for o in seg.get("OBX", []):
        sol["obx"].append({"tipo_valor": _campo(o, 2).strip(), "codigo": _comp(_campo(o, 3), 1),
                           "descripcion": _comp(_campo(o, 3), 2), "sistema": _comp(_campo(o, 3), 3),
                           "valor": _campo(o, 5).strip(), "unidad": _campo(o, 6).strip()})
    return sol


COLUMNAS_CSV = ["documento", "nombre", "sexo", "nacimiento", "dx_local", "fecha", "triage", "profesional"]


def parsear_csv(texto, sede):
    """Devuelve una lista de (fila_original_texto, solicitud) una por fila de datos."""
    lector = csv.DictReader(io.StringIO((texto or "").lstrip("\ufeff")), delimiter=";")
    if not lector.fieldnames or [c.strip() for c in lector.fieldnames] != COLUMNAS_CSV:
        raise HL7Error("Encabezado CSV inesperado; se esperaba: " + ";".join(COLUMNAS_CSV))
    salida = []
    for fila in lector:
        f = {k.strip(): (v or "").strip() for k, v in fila.items() if k}
        partes = f["nombre"].split()
        mitad = len(partes) // 2
        salida.append((";".join(f[c] for c in COLUMNAS_CSV), {
            "formato": "CSV", "tipo": "CSV", "id_mensaje": "", "sede_texto": str(sede), "sede": sede,
            "tipo_documento": "CC", "documento": f["documento"],
            "apellido": " ".join(partes[mitad:]), "nombres": " ".join(partes[:mitad]), "nombre_completo": f["nombre"],
            "nacimiento": f["nacimiento"], "nacimiento_raw": f["nacimiento"], "sexo": f["sexo"],
            "clase": "O", "medico_id": f["profesional"], "medico_apellido": "", "medico_nombre": "",
            "visita": "", "fecha_atencion": f["fecha"], "triage": f["triage"], "dx_local": f["dx_local"],
            "cie10": "", "cie10_desc": "", "dx_sistema": "", "obx": []}))
    return salida
