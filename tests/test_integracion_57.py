"""
test_integracion_57.py — PRUEBA PROPIA: flujo completo con PostgreSQL real y un HAPI simulado.

Crea dos bases TEMPORALES (hc_test_a, hc_test_b), no toca las 3 sedes reales, y las borra al terminar.
Se omite sola si PostgreSQL no está disponible (levante `docker compose up -d pg_ips` para ejecutarla).
Flujo: admisión registra -> MPI avisa duplicado -> médico completa -> migración -> RDA ($document) -> matriz.
"""
import sys
from pathlib import Path

import psycopg2
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import esquema57  # noqa: E402

BASES = ["hc_test_a", "hc_test_b"]


def _admin():
    return psycopg2.connect(host=esquema57.os.environ.get("DB_HOST", "localhost"), port=esquema57.os.environ.get("DB_PORT", "5432"),
                            dbname=esquema57.os.environ.get("DB_ADMIN_DB", "postgres"),
                            user=esquema57.os.environ.get("DB_USER", "ips_admin"),
                            password=esquema57.os.environ.get("DB_PASSWORD", "kali"), connect_timeout=3)


@pytest.fixture(scope="module")
def entorno():
    try:
        admin = _admin()
    except Exception as e:
        pytest.skip(f"PostgreSQL no disponible: {e}")
    admin.autocommit = True
    cur = admin.cursor()
    for b in BASES:
        cur.execute(f"DROP DATABASE IF EXISTS {b}")
        cur.execute(f"CREATE DATABASE {b}")
        c = esquema57.conectar(b)
        c.cursor().execute("""CREATE TABLE pacientes (id_paciente UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            documento_identidad VARCHAR(20) NOT NULL, tipo_documento VARCHAR(5) NOT NULL, nombre_completo VARCHAR(150) NOT NULL,
            fecha_nacimiento DATE NOT NULL, sexo CHAR(1) NOT NULL, fhir_patient_id VARCHAR(64))""")
        c.commit()
        c.close()
        esquema57.preparar_sede(b, sembrar=False)
    from fake_hapi import ServidorFalso
    srv = ServidorFalso(18099).iniciar()
    import os
    os.environ["FHIR_BASE_URL"] = srv.url
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vista_unificada"))
    import app as A
    import migrar_a_fhir as M
    import rda
    A.FHIR = srv.url
    M.FHIR_BASE_URL = srv.url
    rda.FHIR = srv.url
    antes = (list(A.SEDES), dict(M.SEDES), dict(A.CIUDAD_POR_BD))
    A.SEDES[:] = [{"nombre_bd": "hc_test_a", "ciudad": "Sincelejo"}, {"nombre_bd": "hc_test_b", "ciudad": "Cartagena"}]
    A.CIUDAD_POR_BD.clear()
    A.CIUDAD_POR_BD.update({"hc_test_a": "Sincelejo", "hc_test_b": "Cartagena"})
    sedes = dict(M.SEDES)
    M.SEDES.clear()
    M.SEDES["hc_test_a"] = sedes["historia_clinica_sede1"]
    M.SEDES["hc_test_b"] = sedes["historia_clinica_sede2"]
    yield A, M, srv
    srv.detener()
    A.SEDES[:] = antes[0]
    M.SEDES.clear(); M.SEDES.update(antes[1])
    A.CIUDAD_POR_BD.clear(); A.CIUDAD_POR_BD.update(antes[2])
    for b in BASES:
        cur.execute(f"DROP DATABASE IF EXISTS {b} WITH (FORCE)")
    admin.close()


FORM = {"sede": "hc_test_a", "tipo": "CC", "documento": "1007654321", "pais_nacionalidad": "CO", "nombre": "Juan Pérez Gómez",
        "nacimiento": "1985-03-15", "sexo": "M", "genero": "Masculino", "ocupacion": "Ingeniero", "pais_residencia": "CO",
        "municipio_residencia": "70001", "etnia": "Ninguna", "zona_residencia": "01", "direccion_residencia": "Calle 1 # 2-3",
        "telefono": "3001234567", "correo": "juan@demo.co", "nombre_responsable": "María Pérez", "parentesco_responsable": "03",
        "telefono_responsable": "3009876543", "entidad_salud": "EPS Sanitas", "fecha_ingreso": "2026-02-14T10:30",
        "modalidad_entrega": "01", "entorno_atencion": "01", "via_ingreso": "01", "causa_atencion": "Dolor abdominal agudo",
        "fecha_triage": "2026-02-14T10:35", "clasificacion_triage": "III"}

CLINICA = {"descripcion_medicamento": "Acetaminofén 500mg", "dosis": "500mg", "via_administracion": "01",
           "frecuencia": "Cada 8 horas", "dias_tratamiento": "5", "unidades_aplicadas": "15", "id_personal_salud": "98765432",
           "nombre_personal_salud": "Dr. Carlos Rodríguez", "finalidad_tecnologia": "01", "tipo_dx_ingreso": "01",
           "dx_ingreso": "J00", "tipo_dx_egreso": "01", "dx_egreso": "J18.9", "dx_rel1": "I10", "fecha_salida": "2026-02-14T14:30",
           "condicion_salida": "01", "codigo_prestador": "700010012345", "alergias": "Penicilina, Mariscos",
           "antecedente_familiar": "Padre: HTA", "riesgos_ocupacionales": "Ruido", "responsable_egreso": "Dr. Carlos Rodríguez",
           "dias_incapacidad": "3", "tipo_incapacidad": "01"}


def test_flujo_completo(entorno):
    A, M, srv = entorno
    c = A.app.test_client()
    # 1) admisión en sede A, y el mismo documento en sede B -> el MPI debe avisar
    c.post("/admision/registrar", data=FORM)
    r = c.post("/admision/registrar", data={**FORM, "sede": "hc_test_b"}, follow_redirects=True).data.decode()
    assert "MPI: posible identidad federada" in r
    # 2) campos obligatorios: sin dirección se rechaza
    r = c.post("/admision/registrar", data={**FORM, "documento": "2", "direccion_residencia": ""}, follow_redirects=True).data.decode()
    assert "Datos incompletos" in r
    # 3) estado inicial: 0 %
    assert [s["cobertura_pct"] for s in A.datos_reportes()["sedes"]] == [0.0, 0.0]
    # 4) el médico completa la atención de la sede A (aún sin migrar: queda pendiente)
    pend = A.atenciones_por_completar("1007654321")
    assert len(pend) == 2
    a = next(p for p in pend if p["bd"] == "hc_test_a")
    r = c.post("/medico/completar", data={**CLINICA, "documento": "1007654321", "bd": a["bd"], "id_atencion": a["id_atencion"]},
               follow_redirects=True).data.decode()
    assert "pendiente" in r.lower()
    # 5) migración de ambas sedes -> 100 %
    for bd in ("hc_test_a", "hc_test_b"):
        c.post("/admision/migrar", data={"sede": bd})
    assert [s["cobertura_pct"] for s in A.datos_reportes()["sedes"]] == [100.0, 100.0]
    # 6) la atención completa llegó a FHIR (Encounter + 3 Condition + MedicationRequest + 2 alergias)
    fh = A.datos_reportes()["fhir"]
    assert fh["Patient"] == 2 and fh["MedicationRequest"] == 1 and fh["AllergyIntolerance"] == 2
    # la atención de la sede B no tenía diagnóstico/egreso: solo se migró el paciente (más historia demo)
    # 7) las vistas muestran la historia unificada
    for url in ("/paciente?documento=1007654321", "/medico?documento=1007654321"):
        t = c.get(url).data.decode()
        assert "Acetaminofén 500mg" in t and "Penicilina" in t and "J18.9" in t
    # 8) el médico completa la atención de B con el paciente YA migrado -> se envía de inmediato
    b = A.atenciones_por_completar("1007654321")[0]
    r = c.post("/medico/completar", data={**CLINICA, "descripcion_medicamento": "", "documento": "1007654321", "bd": b["bd"],
                                          "id_atencion": b["id_atencion"]}, follow_redirects=True).data.decode()
    assert "Enviada a HAPI FHIR" in r
    # 9) RDA: Composition + Bundle document
    pid = srv.app.almacen and next(k[1] for k in srv.app.almacen if k[0] == "Patient")
    import rda
    res = rda.generar_rda(srv.url, pid)
    assert res["bundle"]["type"] == "document" and res["tipos"][0] == "Composition"
    # 10) matriz de trazabilidad con datos reales
    t = c.get("/matriz").data.decode()
    assert "Cubierto" in t and "tecnologia_salud.dosis" in t
    assert c.get("/matriz.csv").status_code == 200
