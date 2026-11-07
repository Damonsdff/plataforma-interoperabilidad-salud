"""
esquema57.py — Modelo relacional ampliado con los 57 campos (Res. 866/2021).

Sigue el esquema del repositorio del docente (usuario, atencion, tecnologia_salud,
diagnostico, egreso, profesional_salud) pero conserva la tabla `pacientes` de cada
sede (con su marcador fhir_patient_id) para no romper el laboratorio 5.

    pacientes ──< atenciones ──┬─ 1:N tecnologia_salud >── profesional_salud
                               ├─ 1:1 diagnostico
                               └─ 1:1 egreso

Todo es idempotente: se puede ejecutar cuantas veces se quiera.
    python esquema57.py            # aplica esquema + datos de demostración en las 3 sedes
"""
import os
from datetime import date, datetime

import psycopg2

import campos57

BASES = ["historia_clinica_sede1", "historia_clinica_sede2", "historia_clinica_sede3"]


def conectar(nombre_bd: str):
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"), port=os.environ.get("DB_PORT", "5432"),
        dbname=nombre_bd, user=os.environ.get("DB_USER", "ips_admin"),
        password=os.environ.get("DB_PASSWORD", "kali"), connect_timeout=5)


DDL = """
ALTER TABLE pacientes
    ADD COLUMN IF NOT EXISTS pais_nacionalidad       VARCHAR(5),
    ADD COLUMN IF NOT EXISTS edad                    INT,
    ADD COLUMN IF NOT EXISTS unidad_edad             VARCHAR(2) DEFAULT '1',
    ADD COLUMN IF NOT EXISTS genero                  VARCHAR(30),
    ADD COLUMN IF NOT EXISTS ocupacion               VARCHAR(100),
    ADD COLUMN IF NOT EXISTS voluntad_anticipada     BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS categoria_discapacidad  VARCHAR(30),
    ADD COLUMN IF NOT EXISTS pais_residencia         VARCHAR(5),
    ADD COLUMN IF NOT EXISTS municipio_residencia    VARCHAR(10),
    ADD COLUMN IF NOT EXISTS etnia                   VARCHAR(30),
    ADD COLUMN IF NOT EXISTS comunidad_etnica        VARCHAR(100),
    ADD COLUMN IF NOT EXISTS zona_residencia         VARCHAR(2),
    ADD COLUMN IF NOT EXISTS direccion_residencia    VARCHAR(200),
    ADD COLUMN IF NOT EXISTS telefono                VARCHAR(20),
    ADD COLUMN IF NOT EXISTS correo                  VARCHAR(120),
    ADD COLUMN IF NOT EXISTS nombre_responsable      VARCHAR(150),
    ADD COLUMN IF NOT EXISTS parentesco_responsable  VARCHAR(2),
    ADD COLUMN IF NOT EXISTS telefono_responsable    VARCHAR(20);

CREATE TABLE IF NOT EXISTS profesional_salud (
    id_personal_salud VARCHAR(30) PRIMARY KEY,
    nombre            VARCHAR(150) NOT NULL,
    especialidad      VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS atenciones (
    id_atencion          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    id_paciente          UUID NOT NULL REFERENCES pacientes(id_paciente) ON DELETE CASCADE,
    entidad_salud        VARCHAR(150) NOT NULL,
    fecha_ingreso        TIMESTAMP NOT NULL,
    modalidad_entrega    VARCHAR(2) NOT NULL,
    entorno_atencion     VARCHAR(2) NOT NULL,
    via_ingreso          VARCHAR(2) NOT NULL,
    causa_atencion       TEXT NOT NULL,
    fecha_triage         TIMESTAMP,
    clasificacion_triage VARCHAR(3),
    fhir_encounter_id    VARCHAR(64),          -- NULL = historia pendiente de enviar a FHIR
    creado_en            TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tecnologia_salud (
    id_tecnologia           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    id_atencion             UUID NOT NULL REFERENCES atenciones(id_atencion) ON DELETE CASCADE,
    descripcion_medicamento VARCHAR(200),
    dosis                   VARCHAR(50),
    via_administracion      VARCHAR(2),
    frecuencia              VARCHAR(60),
    dias_tratamiento        INT,
    unidades_aplicadas      INT,
    id_personal_salud       VARCHAR(30) REFERENCES profesional_salud(id_personal_salud),
    finalidad_tecnologia    VARCHAR(2)
);

CREATE TABLE IF NOT EXISTS diagnostico (
    id_diagnostico UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    id_atencion    UUID NOT NULL UNIQUE REFERENCES atenciones(id_atencion) ON DELETE CASCADE,
    tipo_dx_ingreso VARCHAR(2),
    dx_ingreso      VARCHAR(10),
    tipo_dx_egreso  VARCHAR(2),
    dx_egreso       VARCHAR(10) NOT NULL,
    dx_rel1         VARCHAR(10),
    dx_rel2         VARCHAR(10),
    dx_rel3         VARCHAR(10)
);

CREATE TABLE IF NOT EXISTS egreso (
    id_egreso            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    id_atencion          UUID NOT NULL UNIQUE REFERENCES atenciones(id_atencion) ON DELETE CASCADE,
    fecha_salida         TIMESTAMP NOT NULL,
    condicion_salida     VARCHAR(2) NOT NULL,
    dx_muerte            VARCHAR(10),
    codigo_prestador     VARCHAR(20) NOT NULL,
    tipo_incapacidad     VARCHAR(2),
    dias_incapacidad     INT,
    dias_lic_maternidad  INT,
    alergias             TEXT,
    antecedente_familiar TEXT,
    riesgos_ocupacionales TEXT,
    responsable_egreso   VARCHAR(150) NOT NULL
);

CREATE TABLE IF NOT EXISTS meta (clave VARCHAR(40) PRIMARY KEY, valor VARCHAR(100));
"""

# ───────────────────────── datos de demostración ─────────────────────────
PROFESIONALES = [
    ("98765432", "Dr. Carlos Rodríguez", "Medicina general"),
    ("98765433", "Dra. Luz Marina Ortega", "Medicina interna"),
    ("98765434", "Dr. Andrés Villadiego", "Urgencias"),
]
# (dx_egreso, dx_rel1, dx_rel2, medicamento, dosis, via, frecuencia, días, unidades, finalidad, causa)
PLANTILLAS = [
    ("I10", "E66.9", None, "Losartán 50 mg", "50 mg", "01", "Cada 24 horas", 30, 30, "01", "Control de presión arterial elevada"),
    ("E11.9", "I10", None, "Metformina 850 mg", "850 mg", "01", "Cada 12 horas", 30, 60, "01", "Control de glucemia y mareo"),
    ("J45.9", None, None, "Salbutamol inhalador 100 mcg", "200 mcg", "06", "Cada 6 horas", 5, 20, "01", "Dificultad respiratoria y sibilancias"),
    ("J06.9", "J00", None, "Acetaminofén 500 mg", "500 mg", "01", "Cada 8 horas", 5, 15, "01", "Fiebre y dolor de garganta"),
    ("K29.7", "A09", "M54.5", "Omeprazol 20 mg", "20 mg", "01", "Cada 24 horas", 14, 14, "01", "Dolor abdominal agudo"),
]
EPS = ["EPS Sanitas", "Nueva EPS", "Salud Total", "Coosalud", "Mutual Ser"]
OCUPACIONES = ["Ingeniero", "Docente", "Comerciante", "Agricultor", "Enfermera", "Estudiante"]
MUNICIPIO_SEDE = {"historia_clinica_sede1": ("70001", "700010012345"),
                  "historia_clinica_sede2": ("13001", "130010054321"),
                  "historia_clinica_sede3": ("70215", "702150067890")}
ALERGIAS = [None, "Penicilina", "Mariscos, Polen", None, "Dipirona"]


def asegurar_esquema(conn):
    """Crea/ajusta tablas (idempotente)."""
    cur = conn.cursor()
    cur.execute(DDL)
    conn.commit()


def _sembrar_pacientes(conn, bd):
    """Completa los campos de identificación de los pacientes de demostración y
    crea una atención completa (57 campos) por paciente. Solo se ejecuta UNA vez por base."""
    cur = conn.cursor()
    cur.execute("SELECT valor FROM meta WHERE clave='semilla57'")
    if cur.fetchone():
        return 0
    for ident, nombre, esp in PROFESIONALES:
        cur.execute("INSERT INTO profesional_salud VALUES (%s,%s,%s) ON CONFLICT DO NOTHING", (ident, nombre, esp))
    municipio, prestador = MUNICIPIO_SEDE.get(bd, ("70001", "700010012345"))
    cur.execute("SELECT id_paciente, nombre_completo, fecha_nacimiento FROM pacientes ORDER BY documento_identidad")
    creados = 0
    for i, (pid, nombre, nac) in enumerate(cur.fetchall()):
        edad, unidad = campos57.calcular_edad(nac)
        primer = nombre.split()[0].lower()
        cur.execute("""UPDATE pacientes SET pais_nacionalidad='CO', edad=%s, unidad_edad=%s,
              genero=CASE sexo WHEN 'M' THEN 'Masculino' WHEN 'F' THEN 'Femenino' ELSE 'Otro' END,
              ocupacion=%s, voluntad_anticipada=%s, categoria_discapacidad='Ninguna', pais_residencia='CO',
              municipio_residencia=%s, etnia=%s, comunidad_etnica=%s, zona_residencia=%s,
              direccion_residencia=%s, telefono=%s, correo=%s, nombre_responsable=%s,
              parentesco_responsable=%s, telefono_responsable=%s
              WHERE id_paciente=%s AND pais_nacionalidad IS NULL""",
            (edad, unidad, OCUPACIONES[i % len(OCUPACIONES)], i % 4 == 0, municipio,
             "Indígena" if i % 5 == 3 else "Ninguna", "Zenú" if i % 5 == 3 else None,
             "02" if i % 5 == 4 else "01", f"Calle {10 + i} # {20 + i}-{30 + i}",
             f"300{1000000 + i * 7919:07d}", f"{primer}{i}@correo-demo.co",
             "María Pérez" if i % 2 == 0 else "Pedro Gómez", "03" if i % 2 == 0 else "01",
             f"310{2000000 + i * 4231:07d}", str(pid)))
        p = PLANTILLAS[i % len(PLANTILLAS)]
        ingreso = datetime(2026, 9, 10 + i % 15, 8 + i % 8, 30)
        salida = datetime(2026, 9, 10 + i % 15, 11 + i % 8, 45)
        urg = i % 3 == 0
        cur.execute("""INSERT INTO atenciones (id_paciente, entidad_salud, fecha_ingreso, modalidad_entrega,
              entorno_atencion, via_ingreso, causa_atencion, fecha_triage, clasificacion_triage)
              VALUES (%s,%s,%s,'01',%s,%s,%s,%s,%s) RETURNING id_atencion""",
            (str(pid), EPS[i % len(EPS)], ingreso, "01" if urg else "02", "01" if i % 4 else "02", p[10],
             ingreso.replace(minute=40) if urg else None, ["III", "II", "IV"][i % 3] if urg else None))
        aid = cur.fetchone()[0]
        prof = PROFESIONALES[i % len(PROFESIONALES)]
        cur.execute("""INSERT INTO tecnologia_salud (id_atencion, descripcion_medicamento, dosis, via_administracion,
              frecuencia, dias_tratamiento, unidades_aplicadas, id_personal_salud, finalidad_tecnologia)
              VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""", (aid, p[3], p[4], p[5], p[6], p[7], p[8], prof[0], p[9]))
        cur.execute("""INSERT INTO diagnostico (id_atencion, tipo_dx_ingreso, dx_ingreso, tipo_dx_egreso, dx_egreso,
              dx_rel1, dx_rel2, dx_rel3) VALUES (%s,'01',%s,'01',%s,%s,%s,NULL)""",
            (aid, "J00" if p[0].startswith("J") else p[0], p[0], p[1], p[2]))
        cur.execute("""INSERT INTO egreso (id_atencion, fecha_salida, condicion_salida, codigo_prestador,
              tipo_incapacidad, dias_incapacidad, dias_lic_maternidad, alergias, antecedente_familiar,
              riesgos_ocupacionales, responsable_egreso) VALUES (%s,%s,'01',%s,%s,%s,%s,%s,%s,%s,%s)""",
            (aid, salida, prestador, "01" if i % 3 == 0 else None, 3 if i % 3 == 0 else None,
             0,
             ALERGIAS[i % len(ALERGIAS)], ["Padre: HTA, Madre: DM2", "Madre: asma", None][i % 3],
             ["Ruido, Polvo", None, "Exposición solar"][i % 3], prof[1]))
        creados += 1
    cur.execute("INSERT INTO meta VALUES ('semilla57','ok') ON CONFLICT DO NOTHING")
    conn.commit()
    return creados


def preparar_sede(bd: str, sembrar: bool = True):
    conn = conectar(bd)
    try:
        asegurar_esquema(conn)
        return _sembrar_pacientes(conn, bd) if sembrar else 0
    finally:
        conn.close()


def preparar_todo(sembrar: bool = True):
    return {bd: preparar_sede(bd, sembrar) for bd in BASES}


# ───────────────────────── formularios → diccionarios ─────────────────────────
def _txt(v):
    v = (v or "").strip() if isinstance(v, str) or v is None else v
    return v or None


def _entero(v):
    v = _txt(v)
    return int(v) if v is not None else None


def _fecha_hora(v):
    v = _txt(v)
    return datetime.fromisoformat(v) if v else None


def paciente_desde_formulario(f) -> dict:
    nac = date.fromisoformat(f.get("nacimiento", ""))
    edad, unidad = campos57.calcular_edad(nac)
    d = {"tipo_documento": _txt(f.get("tipo")) or "CC", "documento_identidad": _txt(f.get("documento")),
         "nombre_completo": " ".join((f.get("nombre") or "").split()), "fecha_nacimiento": nac,
         "edad": edad, "unidad_edad": unidad, "sexo": _txt(f.get("sexo")),
         "voluntad_anticipada": f.get("voluntad_anticipada") in ("on", "true", "1", True)}
    for col in ("pais_nacionalidad", "genero", "ocupacion", "categoria_discapacidad", "pais_residencia",
                "municipio_residencia", "etnia", "comunidad_etnica", "zona_residencia", "direccion_residencia",
                "telefono", "correo", "nombre_responsable", "parentesco_responsable", "telefono_responsable"):
        d[col] = _txt(f.get(col))
    return d


def validar_paciente(d: dict) -> list:
    faltan = []
    obligatorios = [("tipo_documento", 1), ("documento_identidad", 2), ("pais_nacionalidad", 3), ("nombre_completo", 4),
                    ("fecha_nacimiento", 5), ("sexo", 8), ("pais_residencia", 13), ("municipio_residencia", 14),
                    ("zona_residencia", 51), ("direccion_residencia", 52)]
    for col, n in obligatorios:
        if not d.get(col):
            faltan.append(f"campo {n} ({col})")
    if d.get("nombre_completo") and len(d["nombre_completo"].split()) < 2:
        faltan.append("campo 4: indique nombre y apellido")
    if d.get("sexo") not in (None, "M", "F", "I"):
        faltan.append("campo 8: sexo debe ser M, F o I")
    return faltan


def atencion_desde_formulario(f) -> dict:
    d = {"entidad_salud": _txt(f.get("entidad_salud")), "fecha_ingreso": _fecha_hora(f.get("fecha_ingreso")),
         "modalidad_entrega": _txt(f.get("modalidad_entrega")), "entorno_atencion": _txt(f.get("entorno_atencion")),
         "via_ingreso": _txt(f.get("via_ingreso")), "causa_atencion": _txt(f.get("causa_atencion")),
         "fecha_triage": _fecha_hora(f.get("fecha_triage")), "clasificacion_triage": _txt(f.get("clasificacion_triage"))}
    return d


def clinica_desde_formulario(f) -> dict:
    return {
        "tecnologia": {"descripcion_medicamento": _txt(f.get("descripcion_medicamento")), "dosis": _txt(f.get("dosis")),
                       "via_administracion": _txt(f.get("via_administracion")), "frecuencia": _txt(f.get("frecuencia")),
                       "dias_tratamiento": _entero(f.get("dias_tratamiento")),
                       "unidades_aplicadas": _entero(f.get("unidades_aplicadas")),
                       "id_personal_salud": _txt(f.get("id_personal_salud")),
                       "nombre_personal_salud": _txt(f.get("nombre_personal_salud")),
                       "finalidad_tecnologia": _txt(f.get("finalidad_tecnologia"))},
        "diagnostico": {k: _txt(f.get(k)) for k in ("tipo_dx_ingreso", "dx_ingreso", "tipo_dx_egreso", "dx_egreso",
                                                     "dx_rel1", "dx_rel2", "dx_rel3")},
        "egreso": {"fecha_salida": _fecha_hora(f.get("fecha_salida")), "condicion_salida": _txt(f.get("condicion_salida")),
                   "dx_muerte": _txt(f.get("dx_muerte")), "codigo_prestador": _txt(f.get("codigo_prestador")),
                   "tipo_incapacidad": _txt(f.get("tipo_incapacidad")), "dias_incapacidad": _entero(f.get("dias_incapacidad")),
                   "dias_lic_maternidad": _entero(f.get("dias_lic_maternidad")), "alergias": _txt(f.get("alergias")),
                   "antecedente_familiar": _txt(f.get("antecedente_familiar")),
                   "riesgos_ocupacionales": _txt(f.get("riesgos_ocupacionales")),
                   "responsable_egreso": _txt(f.get("responsable_egreso"))},
    }


def validar_atencion(a: dict, clinica: dict | None = None) -> list:
    faltan = []
    for col, n in (("entidad_salud", 16), ("fecha_ingreso", 17), ("modalidad_entrega", 18), ("entorno_atencion", 19),
                   ("via_ingreso", 20), ("causa_atencion", 21)):
        if not a.get(col):
            faltan.append(f"campo {n} ({col})")
    if clinica is not None:
        if not clinica["diagnostico"].get("dx_egreso"):
            faltan.append("campo 36 (dx_egreso)")
        e = clinica["egreso"]
        for col, n in (("fecha_salida", 40), ("condicion_salida", 41), ("codigo_prestador", 43), ("responsable_egreso", 50)):
            if not e.get(col):
                faltan.append(f"campo {n} ({col})")
        if e.get("condicion_salida") == "02" and not e.get("dx_muerte"):
            faltan.append("campo 42 (dx_muerte) es obligatorio si la condición de salida es Muerto")
        if e.get("fecha_salida") and a.get("fecha_ingreso") and e["fecha_salida"] < a["fecha_ingreso"]:
            faltan.append("la fecha de salida (40) no puede ser anterior al ingreso (17)")
        t = clinica["tecnologia"]
        if t.get("descripcion_medicamento") and not t.get("id_personal_salud"):
            faltan.append("campo 31: indique el personal de salud que ordena el medicamento")
    return faltan


# ───────────────────────── escritura ─────────────────────────
def insertar_paciente(conn, d: dict):
    cols = ["documento_identidad", "tipo_documento", "nombre_completo", "fecha_nacimiento", "sexo", "edad", "unidad_edad",
            "pais_nacionalidad", "genero", "ocupacion", "voluntad_anticipada", "categoria_discapacidad", "pais_residencia",
            "municipio_residencia", "etnia", "comunidad_etnica", "zona_residencia", "direccion_residencia", "telefono",
            "correo", "nombre_responsable", "parentesco_responsable", "telefono_responsable"]
    cur = conn.cursor()
    cur.execute(f"INSERT INTO pacientes ({','.join(cols)}) VALUES ({','.join(['%s'] * len(cols))}) RETURNING id_paciente",
                [d.get(c) for c in cols])
    pid = cur.fetchone()[0]
    conn.commit()
    return pid


def insertar_atencion(conn, id_paciente, atencion: dict, clinica: dict | None = None):
    """Inserta atención (16-23) y, si se envía `clinica`, tecnología (25-32), diagnósticos (33-39) y egreso (40-50)."""
    cur = conn.cursor()
    cols = ["entidad_salud", "fecha_ingreso", "modalidad_entrega", "entorno_atencion", "via_ingreso", "causa_atencion",
            "fecha_triage", "clasificacion_triage"]
    cur.execute(f"INSERT INTO atenciones (id_paciente,{','.join(cols)}) VALUES (%s,{','.join(['%s'] * len(cols))}) "
                "RETURNING id_atencion", [str(id_paciente)] + [atencion.get(c) for c in cols])
    aid = cur.fetchone()[0]
    if clinica:
        t = clinica["tecnologia"]
        if t.get("descripcion_medicamento"):
            if t.get("id_personal_salud"):
                cur.execute("INSERT INTO profesional_salud (id_personal_salud, nombre) VALUES (%s,%s) ON CONFLICT DO NOTHING",
                            (t["id_personal_salud"], t.get("nombre_personal_salud") or "Profesional " + t["id_personal_salud"]))
            tc = ["descripcion_medicamento", "dosis", "via_administracion", "frecuencia", "dias_tratamiento",
                  "unidades_aplicadas", "id_personal_salud", "finalidad_tecnologia"]
            cur.execute(f"INSERT INTO tecnologia_salud (id_atencion,{','.join(tc)}) VALUES (%s,{','.join(['%s'] * len(tc))})",
                        [aid] + [t.get(c) for c in tc])
        dc = ["tipo_dx_ingreso", "dx_ingreso", "tipo_dx_egreso", "dx_egreso", "dx_rel1", "dx_rel2", "dx_rel3"]
        cur.execute(f"INSERT INTO diagnostico (id_atencion,{','.join(dc)}) VALUES (%s,{','.join(['%s'] * len(dc))})",
                    [aid] + [clinica["diagnostico"].get(c) for c in dc])
        ec = ["fecha_salida", "condicion_salida", "dx_muerte", "codigo_prestador", "tipo_incapacidad", "dias_incapacidad",
              "dias_lic_maternidad", "alergias", "antecedente_familiar", "riesgos_ocupacionales", "responsable_egreso"]
        cur.execute(f"INSERT INTO egreso (id_atencion,{','.join(ec)}) VALUES (%s,{','.join(['%s'] * len(ec))})",
                    [aid] + [clinica["egreso"].get(c) for c in ec])
    conn.commit()
    return aid


def completar_atencion(conn, id_atencion, clinica: dict):
    """El médico completa una atención creada por el admisionista (tecnología + diagnósticos + egreso)."""
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM diagnostico WHERE id_atencion=%s", (str(id_atencion),))
    if cur.fetchone():
        raise ValueError("Esta atención ya tiene diagnóstico y egreso registrados.")
    t = clinica["tecnologia"]
    if t.get("descripcion_medicamento"):
        if t.get("id_personal_salud"):
            cur.execute("INSERT INTO profesional_salud (id_personal_salud, nombre) VALUES (%s,%s) ON CONFLICT DO NOTHING",
                        (t["id_personal_salud"], t.get("nombre_personal_salud") or "Profesional " + t["id_personal_salud"]))
        tc = ["descripcion_medicamento", "dosis", "via_administracion", "frecuencia", "dias_tratamiento",
              "unidades_aplicadas", "id_personal_salud", "finalidad_tecnologia"]
        cur.execute(f"INSERT INTO tecnologia_salud (id_atencion,{','.join(tc)}) VALUES (%s,{','.join(['%s'] * len(tc))})",
                    [str(id_atencion)] + [t.get(c) for c in tc])
    dc = ["tipo_dx_ingreso", "dx_ingreso", "tipo_dx_egreso", "dx_egreso", "dx_rel1", "dx_rel2", "dx_rel3"]
    cur.execute(f"INSERT INTO diagnostico (id_atencion,{','.join(dc)}) VALUES (%s,{','.join(['%s'] * len(dc))})",
                [str(id_atencion)] + [clinica["diagnostico"].get(c) for c in dc])
    ec = ["fecha_salida", "condicion_salida", "dx_muerte", "codigo_prestador", "tipo_incapacidad", "dias_incapacidad",
          "dias_lic_maternidad", "alergias", "antecedente_familiar", "riesgos_ocupacionales", "responsable_egreso"]
    cur.execute(f"INSERT INTO egreso (id_atencion,{','.join(ec)}) VALUES (%s,{','.join(['%s'] * len(ec))})",
                [str(id_atencion)] + [clinica["egreso"].get(c) for c in ec])
    cur.execute("UPDATE atenciones SET fhir_encounter_id=NULL WHERE id_atencion=%s", (str(id_atencion),))
    conn.commit()


# ───────────────────────── lectura ─────────────────────────
def _filas(cur):
    nombres = [c[0] for c in cur.description]
    return [dict(zip(nombres, f)) for f in cur.fetchall()]


def leer_paciente(conn, id_paciente) -> dict | None:
    cur = conn.cursor()
    cur.execute("SELECT * FROM pacientes WHERE id_paciente=%s", (str(id_paciente),))
    r = _filas(cur)
    return r[0] if r else None


def leer_pacientes_por_documento(conn, documento):
    cur = conn.cursor()
    cur.execute("SELECT * FROM pacientes WHERE documento_identidad=%s", (documento,))
    return _filas(cur)


def leer_atenciones(conn, id_paciente, solo_pendientes: bool = False) -> list:
    """Atenciones del paciente con sus tecnologías, diagnóstico y egreso (todo en diccionarios)."""
    cur = conn.cursor()
    cur.execute("SELECT * FROM atenciones WHERE id_paciente=%s " +
                ("AND fhir_encounter_id IS NULL " if solo_pendientes else "") + "ORDER BY fecha_ingreso", (str(id_paciente),))
    atenciones = _filas(cur)
    for a in atenciones:
        cur.execute("""SELECT t.*, p.nombre AS nombre_personal_salud FROM tecnologia_salud t
                       LEFT JOIN profesional_salud p USING (id_personal_salud) WHERE t.id_atencion=%s""", (str(a["id_atencion"]),))
        a["tecnologias"] = _filas(cur)
        cur.execute("SELECT * FROM diagnostico WHERE id_atencion=%s", (str(a["id_atencion"]),))
        d = _filas(cur)
        a["diagnostico"] = d[0] if d else None
        cur.execute("SELECT * FROM egreso WHERE id_atencion=%s", (str(a["id_atencion"]),))
        e = _filas(cur)
        a["egreso"] = e[0] if e else None
    return atenciones


def marcar_atencion_migrada(conn, id_atencion, fhir_encounter_id):
    cur = conn.cursor()
    cur.execute("UPDATE atenciones SET fhir_encounter_id=%s WHERE id_atencion=%s", (str(fhir_encounter_id), str(id_atencion)))
    conn.commit()


def completitud(conn) -> dict:
    """Por cada campo (1-57): {n: (diligenciados, total)} según los datos reales de la sede."""
    cur = conn.cursor()
    resultado = {}
    totales = {}
    for tabla in ("pacientes", "atenciones", "tecnologia_salud", "diagnostico", "egreso"):
        cur.execute(f"SELECT COUNT(*) FROM {tabla}")
        totales[tabla] = cur.fetchone()[0]
    # Tecnología/diagnóstico/egreso se miden contra el número de atenciones
    for c in campos57.CAMPOS:
        tabla, col = c["tabla"], c["columna"]
        cur.execute(f"SELECT COUNT(*) FROM {tabla} WHERE {col} IS NOT NULL AND CAST({col} AS TEXT) <> ''")
        llenos = cur.fetchone()[0]
        total = totales["pacientes"] if tabla == "pacientes" else totales["atenciones"]
        resultado[c["n"]] = (min(llenos, total) if total else 0, total)
    return resultado


if __name__ == "__main__":
    for bd, n in preparar_todo().items():
        print(f"{bd}: esquema listo, {n} atención(es) de demostración creadas")
