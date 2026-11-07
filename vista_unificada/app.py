"""
app.py — Vista unificada con 4 vistas por rol + matriz de trazabilidad:
  /paciente   /medico   /admision   /reportes   /matriz
Se ejecuta desde la raíz del proyecto:  python vista_unificada/app.py   (o con docker compose up)

Los 57 campos de la Res. 866/2021 se reparten por rol:
  Admisionista -> identificación (1-15, 24, 51-57) y datos de la atención (16-23)
  Médico       -> tecnologías (25-32), diagnósticos (33-39) y egreso (40-50)
"""
import csv
import io
import os
import sys
from collections import Counter
from datetime import date, datetime
from uuid import uuid4

import requests
from flask import Flask, Response, flash, jsonify, redirect, render_template, request, url_for

# Permite importar interoperabilidad/, solucion/ y migrar_a_fhir.py (carpeta padre)
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

import campos57  # noqa: E402
import esquema57  # noqa: E402

FHIR = os.environ.get("FHIR_BASE_URL", "http://localhost:8080/fhir")
CABECERAS = {"Accept": "application/fhir+json", "Content-Type": "application/fhir+json"}

try:
    import datos_clinicos
    import migrar_a_fhir
    import rda
    from interoperabilidad.mpi_service import UMBRAL_COINCIDENCIA_SUGERIDO
    from interoperabilidad.models import Paciente
    from interoperabilidad.service_bus import HealthServiceBus
    from solucion.mapper_estudiante import MapperEstudiante
    from solucion.mpi_estudiante import MPIEstudiante
    MOTOR = True
    ERROR_MOTOR = ""
except Exception as error:  # p. ej. si faltan las carpetas del motor
    MOTOR = False
    ERROR_MOTOR = str(error)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "cambiar-esta-clave")

SEDES = [
    {"nombre_bd": "historia_clinica_sede1", "ciudad": "Sincelejo"},
    {"nombre_bd": "historia_clinica_sede2", "ciudad": "Cartagena"},
    {"nombre_bd": "historia_clinica_sede3", "ciudad": "Corozal"},
]
CIUDAD_POR_BD = {s["nombre_bd"]: s["ciudad"] for s in SEDES}

CODIGOS_CIE10 = [(c, d) for c, d in campos57.CIE10.items()]
CODIGOS_LOINC = [("8480-6", "Presión sistólica", "mmHg", "mm[Hg]"), ("8462-4", "Presión diastólica", "mmHg", "mm[Hg]"),
                 ("8867-4", "Frecuencia cardiaca", "lpm", "/min"), ("8310-5", "Temperatura corporal", "°C", "Cel"),
                 ("29463-7", "Peso corporal", "kg", "kg"), ("2339-0", "Glucosa en sangre", "mg/dL", "mg/dL")]


# ───────────────────────── utilidades ─────────────────────────
def conectar(nombre_bd):
    return esquema57.conectar(nombre_bd)


def preparar_bases():
    """Crea las tablas de los 57 campos (si faltan) y los datos de demostración. Idempotente."""
    for s in SEDES:
        try:
            esquema57.preparar_sede(s["nombre_bd"])
        except Exception as e:  # la base puede estar arrancando; las vistas lo avisan
            print(f"Aviso: no se pudo preparar {s['nombre_bd']}: {e}")


def calcular_cobertura(nombre_bd: str) -> float:
    conn = conectar(nombre_bd)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM pacientes")
    total = cur.fetchone()[0]
    if total == 0:
        conn.close()
        return 0.0
    cur.execute("SELECT COUNT(*) FROM pacientes WHERE fhir_patient_id IS NOT NULL")
    migrados = cur.fetchone()[0]
    conn.close()
    return (migrados / total) * 100


def fhir_get(ruta, params=None):
    r = requests.get(f"{FHIR}/{ruta}", params=params, headers=CABECERAS, timeout=15)
    r.raise_for_status()
    return r.json()


def recursos(bundle, tipo=None):
    out = [e["resource"] for e in bundle.get("entry", [])]
    return [r for r in out if tipo is None or r["resourceType"] == tipo]


def nombre_de(patient):
    n = (patient.get("name") or [{}])[0]
    return n.get("text") or " ".join(n.get("given", []) + [n.get("family", "")]).strip() or "(sin nombre)"


def sede_por_fhir_id(documento):
    """{fhir_patient_id: ciudad} según las bases de cada sede."""
    mapa = {}
    for s in SEDES:
        try:
            conn = conectar(s["nombre_bd"])
            cur = conn.cursor()
            cur.execute("SELECT fhir_patient_id FROM pacientes WHERE documento_identidad = %s "
                        "AND fhir_patient_id IS NOT NULL", (documento,))
            for (fid,) in cur.fetchall():
                mapa[str(fid)] = s["ciudad"]
            conn.close()
        except Exception:
            pass
    return mapa


def _ext(recurso, sufijo):
    for e in recurso.get("extension", []):
        if e.get("url", "").endswith(sufijo):
            return e
    return {}


def _cc(cc):
    """Texto legible de un CodeableConcept / Coding."""
    if not cc:
        return ""
    if cc.get("text"):
        return cc["text"]
    c = (cc.get("coding") or [cc])[-1]
    return c.get("display") or c.get("code", "")


def vista_clinica(documento):
    """Historia unificada de un documento: junta todos los Patient con ese identifier."""
    pacientes_fhir = recursos(fhir_get("Patient", {"identifier": documento, "_count": 50}), "Patient")
    sedes = sede_por_fhir_id(documento)
    datos = {"pacientes": [], "condiciones": [], "observaciones": [], "encuentros": 0,
             "atenciones": [], "medicamentos": [], "alergias": []}
    for p in pacientes_fhir:
        pid = p["id"]
        ciudad = sedes.get(pid, "—")
        dir_ = (p.get("address") or [{}])[0]
        contacto = (p.get("contact") or [{}])[0]
        datos["pacientes"].append({
            "id": pid, "nombre": nombre_de(p), "genero": p.get("gender", ""), "nacimiento": p.get("birthDate", ""), "sede": ciudad,
            "ocupacion": _ext(p, "ocupacion").get("valueString", ""), "municipio": dir_.get("city", ""),
            "direccion": dir_.get("text", ""), "etnia": _cc(_ext(p, "etnia").get("valueCodeableConcept")),
            "telefono": next((t["value"] for t in p.get("telecom", []) if t.get("system") == "phone"), ""),
            "correo": next((t["value"] for t in p.get("telecom", []) if t.get("system") == "email"), ""),
            "responsable": (contacto.get("name") or {}).get("text", ""),
            "parentesco": _cc((contacto.get("relationship") or [None])[0])})
        todo = recursos(fhir_get(f"Patient/{pid}/$everything", {"_count": 200}))
        condiciones_por_id = {r["id"]: r for r in todo if r["resourceType"] == "Condition"}
        for r in todo:
            fecha = r.get("meta", {}).get("lastUpdated", "")[:10]
            tipo = r["resourceType"]
            if tipo == "Condition":
                c = r["code"]["coding"][0]
                datos["condiciones"].append({"codigo": c.get("code"), "desc": c.get("display", ""), "sede": ciudad,
                                             "fecha": fecha, "paciente": pid, "rol": _cc((r.get("category") or [None])[0])})
            elif tipo == "Observation" and "valueQuantity" in r:
                c = r["code"]["coding"][0]
                v = r.get("valueQuantity", {})
                datos["observaciones"].append({"codigo": c.get("code"), "desc": c.get("display", ""), "valor": v.get("value", ""),
                                               "unidad": v.get("unit", ""), "sede": ciudad, "fecha": fecha, "paciente": pid})
            elif tipo == "Observation" and "valueString" in r:
                datos["observaciones"].append({"codigo": "—", "desc": _cc(r.get("code")), "valor": r["valueString"],
                                               "unidad": "", "sede": ciudad, "fecha": fecha, "paciente": pid})
            elif tipo == "Encounter":
                datos["encuentros"] += 1
                hosp = r.get("hospitalization", {})
                dx = [condiciones_por_id.get(d["condition"]["reference"].split("/")[-1]) for d in r.get("diagnosis", [])]
                dx = [(x["code"]["coding"][0]["code"]) for x in dx if x]
                datos["atenciones"].append({
                    "sede": ciudad, "inicio": r.get("period", {}).get("start", "")[:16].replace("T", " "),
                    "fin": r.get("period", {}).get("end", "")[:16].replace("T", " "),
                    "entorno": _cc((r.get("type") or [{}, {}])[1]) if len(r.get("type", [])) > 1 else "",
                    "modalidad": _cc((r.get("type") or [{}])[0]), "causa": (r.get("reasonCode") or [{}])[0].get("text", ""),
                    "via": _cc(hosp.get("admitSource")), "triage": _cc(r.get("priority")),
                    "entidad": _ext(r, "entidad-salud").get("valueString", ""),
                    "salida": _cc(hosp.get("dischargeDisposition")), "diagnosticos": ", ".join(dx),
                    "incapacidad": _ext(r, "incapacidad-dias").get("valueInteger", "")})
            elif tipo == "MedicationRequest":
                di = (r.get("dosageInstruction") or [{}])[0]
                datos["medicamentos"].append({
                    "nombre": r["medicationCodeableConcept"].get("text", ""), "dosis": di.get("text", ""),
                    "via": _cc(di.get("route")), "dias": r.get("dispenseRequest", {}).get("expectedSupplyDuration", {}).get("value", ""),
                    "unidades": r.get("dispenseRequest", {}).get("quantity", {}).get("value", ""), "sede": ciudad})
            elif tipo == "AllergyIntolerance":
                datos["alergias"].append({"alergia": _cc(r.get("code")), "sede": ciudad})
    return datos


def consultar(documento):
    """Devuelve (datos, error) sin romper la página si algo falla."""
    if not documento:
        return None, None
    try:
        return vista_clinica(documento), None
    except Exception as e:
        return None, f"No se pudo consultar HAPI FHIR ({FHIR}): {e}"


def opciones(catalogo):
    return campos57.CATALOGOS[catalogo]


@app.context_processor
def utilidades_plantillas():
    return {"opciones": opciones, "cat": campos57.nombre_catalogo}


# ───────────────────────── Inicio ─────────────────────────
@app.route("/")
def home():
    return render_template("home.html")


# ───────────────────────── 1. PACIENTE ─────────────────────────
@app.route("/paciente")
def vista_paciente():
    documento = request.args.get("documento", "").strip()
    datos, error = consultar(documento)
    return render_template("paciente.html", documento=documento, datos=datos, error=error)


# ───────────────────────── 2. MÉDICO ─────────────────────────
def atenciones_por_completar(documento):
    """Atenciones registradas por admisión (campos 16-23) a las que el médico aún debe agregar 25-50."""
    salida = []
    for s in SEDES:
        try:
            conn = conectar(s["nombre_bd"])
            for p in esquema57.leer_pacientes_por_documento(conn, documento):
                for a in esquema57.leer_atenciones(conn, p["id_paciente"]):
                    if a["diagnostico"] is None:
                        salida.append({"sede": s["ciudad"], "bd": s["nombre_bd"], "paciente": p["nombre_completo"],
                                       "id_atencion": str(a["id_atencion"]), "ingreso": a["fecha_ingreso"],
                                       "causa": a["causa_atencion"], "entorno": campos57.nombre_catalogo("entorno_atencion", a["entorno_atencion"])})
            conn.close()
        except Exception:
            pass
    return salida


@app.route("/medico")
def vista_medico():
    documento = request.args.get("documento", "").strip()
    datos, error = consultar(documento)
    pendientes = atenciones_por_completar(documento) if documento else []
    return render_template("medico.html", documento=documento, datos=datos, error=error, pendientes=pendientes,
                           cie10=CODIGOS_CIE10, loinc=CODIGOS_LOINC, fhir=FHIR, motor=MOTOR,
                           ahora=datetime.now().strftime("%Y-%m-%dT%H:%M"))


@app.route("/medico/registrar", methods=["POST"])
def medico_registrar():
    f = request.form
    documento, pid, tipo = f.get("documento", ""), f.get("patient_id", ""), f.get("tipo", "")
    try:
        enc = datos_clinicos.crear_encuentro(FHIR, pid)
        if tipo == "condicion":
            datos_clinicos.crear_condicion(FHIR, pid, enc, f["codigo"].strip(), f["descripcion"].strip())
            flash("Diagnóstico registrado en HAPI FHIR.", "ok")
        else:
            datos_clinicos.crear_observacion(FHIR, pid, enc, f["codigo"].strip(), f["descripcion"].strip(),
                                             f["valor"], f["unidad"].strip(), f.get("ucum") or f["unidad"].strip())
            flash("Observación registrada en HAPI FHIR.", "ok")
    except Exception as e:
        flash(f"No se pudo registrar: {e}", "error")
    return redirect(url_for("vista_medico", documento=documento))


@app.route("/medico/completar", methods=["POST"])
def medico_completar():
    """Médico completa una atención: tecnologías (25-32), diagnósticos (33-39) y egreso (40-50)."""
    f = request.form
    documento, bd, id_atencion = f.get("documento", ""), f.get("bd", ""), f.get("id_atencion", "")
    if not MOTOR or bd not in CIUDAD_POR_BD:
        flash("No se puede registrar: motor no disponible o sede inválida.", "error")
        return redirect(url_for("vista_medico", documento=documento))
    try:
        clinica = esquema57.clinica_desde_formulario(f)
        conn = conectar(bd)
        cur = conn.cursor()
        cur.execute("SELECT a.*, p.fhir_patient_id FROM atenciones a JOIN pacientes p USING (id_paciente) "
                    "WHERE a.id_atencion=%s", (id_atencion,))
        fila = cur.fetchone()
        if not fila:
            flash("La atención indicada no existe.", "error")
            return redirect(url_for("vista_medico", documento=documento))
        nombres = [c[0] for c in cur.description]
        atencion = dict(zip(nombres, fila))
        faltan = esquema57.validar_atencion(atencion, clinica)
        if faltan:
            conn.close()
            flash("Faltan o son inválidos: " + "; ".join(faltan), "error")
            return redirect(url_for("vista_medico", documento=documento))
        esquema57.completar_atencion(conn, id_atencion, clinica)
        conn.close()
        mensaje = "Atención completada en la base de " + CIUDAD_POR_BD[bd] + "."
        if atencion["fhir_patient_id"]:
            enviadas = migrar_a_fhir.enviar_atenciones_pendientes(bd, atencion["id_paciente"], atencion["fhir_patient_id"], {})
            mensaje += f" Enviada a HAPI FHIR ({enviadas} atención)."
        else:
            mensaje += " Quedó pendiente: se enviará a FHIR cuando el admisionista migre al paciente."
        flash(mensaje, "ok")
    except Exception as e:
        flash(f"No se pudo registrar la atención: {e}", "error")
    return redirect(url_for("vista_medico", documento=documento))


@app.route("/medico/rda/<patient_id>")
def medico_rda(patient_id):
    """Genera el RDA (Composition + Bundle document vía $document) del último encuentro del paciente."""
    try:
        resultado = rda.generar_rda(FHIR, patient_id, request.args.get("encounter"))
    except Exception as e:
        flash(f"No se pudo generar el RDA: {e}", "error")
        return redirect(request.referrer or url_for("vista_medico"))
    import json
    return Response(json.dumps(resultado["bundle"], ensure_ascii=False, indent=2), mimetype="application/fhir+json",
                    headers={"Content-Disposition": f"inline; filename=rda_patient_{patient_id}.json"})


# ───────────────────────── 3. ADMISIONISTA ─────────────────────────
def pendientes_por_sede():
    filas = []
    for s in SEDES:
        try:
            conn = conectar(s["nombre_bd"])
            cur = conn.cursor()
            cur.execute("""SELECT p.documento_identidad, p.tipo_documento, p.nombre_completo, p.fecha_nacimiento,
                                  p.fhir_patient_id, COUNT(a.id_atencion),
                                  COUNT(a.id_atencion) FILTER (WHERE NOT EXISTS
                                        (SELECT 1 FROM diagnostico d WHERE d.id_atencion = a.id_atencion))
                           FROM pacientes p LEFT JOIN atenciones a USING (id_paciente)
                           GROUP BY p.id_paciente, p.documento_identidad, p.tipo_documento, p.nombre_completo,
                                    p.fecha_nacimiento, p.fhir_patient_id ORDER BY p.nombre_completo""")
            pacs = cur.fetchall()
            conn.close()
            filas.append({**s, "pacientes": pacs, "pendientes": sum(1 for p in pacs if p[4] is None), "error": None})
        except Exception as e:
            filas.append({**s, "pacientes": [], "pendientes": 0, "error": str(e)})
    return filas


@app.route("/admision")
def vista_admision():
    return render_template("admision.html", sedes=pendientes_por_sede(), motor=MOTOR, error_motor=ERROR_MOTOR,
                           ahora=datetime.now().strftime("%Y-%m-%dT%H:%M"), hoy=date.today().isoformat())


@app.route("/admision/registrar", methods=["POST"])
def admision_registrar():
    if not MOTOR:
        flash("El motor de interoperabilidad no está disponible: " + ERROR_MOTOR, "error")
        return redirect(url_for("vista_admision"))
    f = request.form
    bd = f.get("sede", "")
    try:
        datos = esquema57.paciente_desde_formulario(f)
    except ValueError:
        flash("La fecha de nacimiento no es válida.", "error")
        return redirect(url_for("vista_admision"))
    if bd not in CIUDAD_POR_BD:
        flash("Seleccione una sede válida.", "error")
        return redirect(url_for("vista_admision"))
    try:
        atencion = esquema57.atencion_desde_formulario(f)
    except ValueError:
        flash("La fecha y hora de ingreso o de triage no es válida.", "error")
        return redirect(url_for("vista_admision"))
    faltan = esquema57.validar_paciente(datos) + esquema57.validar_atencion(atencion)
    if faltan:
        flash("Datos incompletos o inválidos: " + "; ".join(faltan), "error")
        return redirect(url_for("vista_admision"))
    doc = datos["documento_identidad"]
    try:
        conn = conectar(bd)
        if esquema57.leer_pacientes_por_documento(conn, doc):
            conn.close()
            flash(f"El documento {doc} ya existe en {CIUDAD_POR_BD[bd]}. No se duplica dentro de la misma sede.", "error")
            return redirect(url_for("vista_admision"))
        pid = esquema57.insertar_paciente(conn, datos)
        esquema57.insertar_atencion(conn, pid, atencion)
        conn.close()
        # Verificación MPI contra las otras sedes
        nuevo = Paciente(uuid4(), doc, datos["tipo_documento"], datos["nombre_completo"], datos["fecha_nacimiento"],
                         datos["sexo"] if datos["sexo"] in ("M", "F") else "F", migrar_a_fhir.SEDES[bd])
        otras = [b for b in migrar_a_fhir.SEDES if b != bd]
        mpi = MPIEstudiante()
        coincidencias = []
        for c in migrar_a_fhir.obtener_candidatos_otras_sedes(nuevo, otras):
            score = mpi.calcular_score(nuevo, c)
            if score >= UMBRAL_COINCIDENCIA_SUGERIDO:
                coincidencias.append(f"{c.nombre_completo} ({c.sede_origen.nombre_ciudad}, score {score:.2f})")
        flash(f"Paciente y atención registrados en {CIUDAD_POR_BD[bd]} (pendiente de migrar a FHIR; "
              "el médico completa diagnóstico y egreso).", "ok")
        if coincidencias:
            flash("MPI: posible identidad federada con " + "; ".join(coincidencias), "aviso")
    except Exception as e:
        flash(f"Error al registrar: {e}", "error")
    return redirect(url_for("vista_admision"))


@app.route("/admision/migrar", methods=["POST"])
def admision_migrar():
    bd = request.form.get("sede", "")
    if not MOTOR or bd not in CIUDAD_POR_BD:
        flash("No se puede migrar: motor no disponible o sede inválida.", "error")
        return redirect(url_for("vista_admision"))
    try:
        antes = len(migrar_a_fhir.obtener_pacientes_pendientes(bd))
        migrar_a_fhir.migrar_sede(bd, MapperEstudiante(), MPIEstudiante(), HealthServiceBus())
        flash(f"Migración de {CIUDAD_POR_BD[bd]} terminada: {antes} paciente(s) enviados a HAPI FHIR.", "ok")
    except Exception as e:
        flash(f"Error en la migración: {e}", "error")
    return redirect(url_for("vista_admision"))


# ───────────────────────── 4. REPORTERO ─────────────────────────
def completitud_sedes():
    """{ciudad: {n: (llenos, total)}} con los datos reales de cada sede."""
    resultado = {}
    for s in SEDES:
        try:
            conn = conectar(s["nombre_bd"])
            resultado[s["ciudad"]] = esquema57.completitud(conn)
            conn.close()
        except Exception:
            resultado[s["ciudad"]] = None
    return resultado


def datos_reportes():
    sedes, por_doc = [], {}
    comp = completitud_sedes()
    for s in SEDES:
        try:
            conn = conectar(s["nombre_bd"])
            cur = conn.cursor()
            cur.execute("SELECT documento_identidad, fhir_patient_id FROM pacientes")
            filas = cur.fetchall()
            conn.close()
            total = len(filas)
            migrados = sum(1 for _, fid in filas if fid is not None)
            for doc, _ in filas:
                por_doc.setdefault(doc, []).append(s["ciudad"])
            c = comp.get(s["ciudad"]) or {}
            obligatorios = [x["n"] for x in campos57.CAMPOS if x["obligatorio"]]

            def pct(numeros):
                ll = sum(c[n][0] for n in numeros if n in c)
                tt = sum(c[n][1] for n in numeros if n in c)
                return (ll / tt * 100) if tt else 0.0
            sedes.append({"ciudad": s["ciudad"], "total": total, "migrados": migrados, "pendientes": total - migrados,
                          "cobertura_pct": (migrados / total * 100) if total else 0.0,
                          "campos57_pct": pct(range(1, 58)), "obligatorios_pct": pct(obligatorios)})
        except Exception:
            sedes.append({"ciudad": s["ciudad"], "total": 0, "migrados": 0, "pendientes": 0, "cobertura_pct": 0.0,
                          "campos57_pct": 0.0, "obligatorios_pct": 0.0, "error": True})
    fhir = {}
    try:
        for tipo in ("Patient", "Encounter", "Condition", "Observation", "MedicationRequest", "AllergyIntolerance"):
            fhir[tipo] = fhir_get(tipo, {"_summary": "count"}).get("total", 0)
        conds = recursos(fhir_get("Condition", {"_count": 500}), "Condition")
        top = Counter((c["code"]["coding"][0].get("code"), c["code"]["coding"][0].get("display", ""))
                      for c in conds).most_common(5)
        fhir["top_diagnosticos"] = [{"codigo": k[0], "desc": k[1], "total": n} for k, n in top]
    except Exception as e:
        fhir["error"] = str(e)
    duplicados = [{"documento": d, "sedes": c} for d, c in por_doc.items() if len(set(c)) > 1]
    return {"sedes": sedes, "fhir": fhir, "duplicados": duplicados}


@app.route("/reportes")
def vista_reportes():
    return render_template("reportes.html")


@app.route("/api/reportes")
def api_reportes():
    return jsonify(datos_reportes())


@app.route("/api/cobertura")
def api_cobertura():
    resultado = []
    for sede in SEDES:
        try:
            pct = calcular_cobertura(sede["nombre_bd"])
        except Exception:
            pct = 0.0
        resultado.append({"ciudad": sede["ciudad"], "cobertura_pct": pct})
    return jsonify(resultado)


# ───────────────────────── MATRIZ DE TRAZABILIDAD (HU-06, auditor) ─────────────────────────
def filas_matriz():
    comp = completitud_sedes()
    filas = []
    for c in campos57.CAMPOS:
        por_sede = {}
        for s in SEDES:
            datos = (comp.get(s["ciudad"]) or {}).get(c["n"])
            por_sede[s["ciudad"]] = {"llenos": datos[0], "total": datos[1],
                                     "pct": (datos[0] / datos[1] * 100) if datos and datos[1] else 0.0} if datos else None
        filas.append({**c, "estado": "Cubierto", "sedes": por_sede})
    return filas


@app.route("/matriz")
def vista_matriz():
    return render_template("matriz.html", filas=filas_matriz(), sedes=SEDES,
                           obligatorios=sum(1 for c in campos57.CAMPOS if c["obligatorio"]))


@app.route("/matriz.csv")
def matriz_csv():
    salida = io.StringIO()
    w = csv.writer(salida)
    w.writerow(["#", "Grupo", "Campo", "Obligatorio", "Tabla.columna", "Elemento FHIR", "Estado"] +
               [f"% diligenciado {s['ciudad']}" for s in SEDES])
    for f in filas_matriz():
        w.writerow([f["n"], f["grupo"], f["nombre"], "Sí" if f["obligatorio"] else "No", f"{f['tabla']}.{f['columna']}",
                    f["fhir"], f["estado"]] + [f"{(f['sedes'][s['ciudad']] or {'pct': 0})['pct']:.0f}" for s in SEDES])
    return Response("\ufeff" + salida.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=matriz_57_campos.csv"})


preparar_bases()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
