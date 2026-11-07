"""
test_campos57.py — PRUEBAS PROPIAS DEL EQUIPO (no provistas por el docente).

Verifican que los 57 campos de la Res. 866/2021 están definidos, existen en el modelo
relacional y llegan a FHIR R4. No necesitan Docker ni base de datos.
Ejecución: pytest tests/test_campos57.py -v
"""
import json
from collections import Counter
from datetime import date, datetime
from uuid import uuid4

import pytest

import campos57
import esquema57
from interoperabilidad.models import Paciente, Sede
from solucion import historia57_fhir
from solucion.mapper_estudiante import MapperEstudiante

PACIENTE = {
    "pais_nacionalidad": "VE", "edad": 41, "unidad_edad": "1", "genero": "Femenino", "ocupacion": "Ingeniera civil",
    "voluntad_anticipada": True, "categoria_discapacidad": "Visual", "pais_residencia": "CO",
    "municipio_residencia": "13001", "etnia": "Raizal", "comunidad_etnica": "San Basilio", "zona_residencia": "02",
    "direccion_residencia": "Carrera 7 # 8-9", "telefono": "3151234567", "correo": "ana@demo.co",
    "nombre_responsable": "Pedro Barrios", "parentesco_responsable": "04", "telefono_responsable": "3169876543"}
ATENCION = {
    "entidad_salud": "Nueva EPS", "fecha_ingreso": datetime(2026, 2, 14, 10, 30), "modalidad_entrega": "03",
    "entorno_atencion": "03", "via_ingreso": "02", "causa_atencion": "Dolor torácico opresivo",
    "fecha_triage": datetime(2026, 2, 14, 10, 35), "clasificacion_triage": "II",
    "tecnologias": [{"descripcion_medicamento": "Enoxaparina 40 mg", "dosis": "40 mg", "via_administracion": "04",
                     "frecuencia": "Cada 12 horas", "dias_tratamiento": 7, "unidades_aplicadas": 14,
                     "id_personal_salud": "1234567", "nombre_personal_salud": "Dra. Sofía Marín", "finalidad_tecnologia": "01"}],
    "diagnostico": {"tipo_dx_ingreso": "01", "dx_ingreso": "I10", "tipo_dx_egreso": "03", "dx_egreso": "I21.9",
                    "dx_rel1": "E11.9", "dx_rel2": "J45.9", "dx_rel3": "K29.7"},
    "egreso": {"fecha_salida": datetime(2026, 2, 14, 14, 30), "condicion_salida": "02", "dx_muerte": "I46.9",
               "codigo_prestador": "130010099999", "tipo_incapacidad": "02", "dias_incapacidad": 30, "dias_lic_maternidad": 98,
               "alergias": "Penicilina, Mariscos", "antecedente_familiar": "Padre: HTA, Madre: DM2",
               "riesgos_ocupacionales": "Ruido, Polvo", "responsable_egreso": "Dr. Carlos Rodríguez"}}

# Texto que debe aparecer en el JSON FHIR para dar por "enviado" cada campo (1-57)
ESPERADO = {
    1: '"code": "CC"', 2: "1098765432", 3: '"code": "VE"', 4: "Ana Lucía Barrios Pérez", 5: "1985-03-15",
    6: '"value": 41', 7: '"code": "a"', 8: '"gender": "female"', 9: "Femenino", 10: "Ingeniera civil",
    11: '"valueBoolean": true', 12: "Visual", 13: '"country": "CO"', 14: '"code": "13001"', 15: "Raizal",
    16: "Nueva EPS", 17: "2026-02-14T10:30:00-05:00", 18: 'modalidad-entrega", "code": "03"',
    19: '"code": "IMP"', 20: 'via-ingreso", "code": "02"', 21: "Dolor torácico opresivo",
    22: "2026-02-14T10:35:00-05:00", 23: 'triage", "code": "II"', 24: "San Basilio",
    25: "Enoxaparina 40 mg", 26: '"value": 40.0', 27: 'via-administracion", "code": "04"', 28: "Cada 12 horas",
    29: '"expectedSupplyDuration": {"value": 7', 30: '"quantity": {"value": 14', 31: "1234567",
    32: 'finalidad-tecnologia", "code": "01"', 33: 'tipo-diagnostico", "code": "01"', 34: '"code": "I10"',
    35: 'tipo-diagnostico", "code": "03"', 36: '"code": "I21.9"', 37: '"code": "E11.9"', 38: '"code": "J45.9"',
    39: '"code": "K29.7"', 40: "2026-02-14T14:30:00-05:00", 41: '"code": "exp"', 42: '"code": "I46.9"',
    43: "130010099999", 44: 'tipo-incapacidad", "code": "02"', 45: 'incapacidad-dias", "valueInteger": 30',
    46: 'licencia-maternidad-dias", "valueInteger": 98', 47: "Penicilina", 48: "Padre: HTA, Madre: DM2",
    49: "Ruido, Polvo", 50: "Dr. Carlos Rodríguez", 51: 'zona-residencia", "code": "02"',
    52: "Carrera 7 # 8-9", 53: "3151234567", 54: "ana@demo.co", 55: "Pedro Barrios",
    56: 'parentesco", "code": "04"', 57: "3169876543"}


def _recursos_fhir():
    """Convierte el paciente y la atención de ejemplo en recursos FHIR (sin red)."""
    sede = Sede(1, "Sincelejo", "Meditech", "OpenMRS", "Appliance dedicado")
    pac = Paciente(uuid4(), "1098765432", "CC", "Ana Lucía Barrios Pérez", date(1985, 3, 15), "F", sede, extra=dict(PACIENTE))
    recursos = [MapperEstudiante().mapear_paciente(pac)]
    contador = iter(range(1, 1000))
    puestos = []

    def post(r):
        recursos.append(r)
        return str(next(contador))

    historia57_fhir.enviar_atencion(ATENCION, "77", post, lambda r: puestos.append(r))
    return recursos, puestos


def test_hay_exactamente_57_campos_numerados_del_1_al_57():
    assert [c["n"] for c in campos57.CAMPOS] == list(range(1, 58))


def test_distribucion_por_grupo_como_en_el_documento_del_docente():
    cuenta = Counter(c["grupo"] for c in campos57.CAMPOS)
    assert cuenta == {"Identificación": 15, "Atención": 9, "Tecnologías en salud": 11, "Diagnósticos": 4, "Egreso": 18}


def test_campos_obligatorios_segun_la_tabla_del_docente():
    obligatorios = {c["n"] for c in campos57.CAMPOS if c["obligatorio"]}
    esperados = set(range(1, 9)) | {13, 14} | set(range(16, 22)) | {36, 40, 41, 43, 50, 51, 52}
    assert obligatorios == esperados and len(obligatorios) == 23


def test_cada_campo_tiene_columna_en_el_modelo_relacional():
    ddl = esquema57.DDL.lower()
    base_pacientes = {"documento_identidad", "tipo_documento", "nombre_completo", "fecha_nacimiento", "sexo"}  # init-db
    for c in campos57.CAMPOS:
        assert c["columna"] in base_pacientes or c["columna"].lower() in ddl, f"campo {c['n']}: falta la columna {c['columna']}"


def test_catalogos_del_documento_del_docente():
    assert dict(campos57.CATALOGOS["modalidad_entrega"])["03"] == "Telemedicina interactiva"
    assert [c for c, _ in campos57.CATALOGOS["clasificacion_triage"]] == ["I", "II", "III", "IV", "V"]
    assert campos57.nombre_catalogo("zona_residencia", "02") == "Rural"


@pytest.mark.parametrize("nacimiento,hoy,esperado", [
    (date(1985, 3, 15), date(2026, 3, 14), (40, "1")), (date(1985, 3, 15), date(2026, 3, 15), (41, "1")),
    (date(2026, 1, 20), date(2026, 5, 10), (3, "2")), (date(2026, 5, 1), date(2026, 5, 10), (9, "3"))])
def test_edad_y_unidad_campos_6_y_7(nacimiento, hoy, esperado):
    assert campos57.calcular_edad(nacimiento, hoy) == esperado


def test_validacion_de_campos_obligatorios_del_paciente():
    assert esquema57.validar_paciente({}) != []
    ok = {"tipo_documento": "CC", "documento_identidad": "1", "pais_nacionalidad": "CO", "nombre_completo": "Ana Perez",
          "fecha_nacimiento": date(1990, 1, 1), "sexo": "F", "pais_residencia": "CO", "municipio_residencia": "70001",
          "zona_residencia": "01", "direccion_residencia": "Calle 1"}
    assert esquema57.validar_paciente(ok) == []
    assert esquema57.validar_paciente({**ok, "nombre_completo": "Ana"}) != []


def test_validacion_de_atencion_y_egreso():
    a = {k: ATENCION[k] for k in ("entidad_salud", "fecha_ingreso", "modalidad_entrega", "entorno_atencion",
                                  "via_ingreso", "causa_atencion")}
    clinica = {"tecnologia": ATENCION["tecnologias"][0], "diagnostico": ATENCION["diagnostico"], "egreso": dict(ATENCION["egreso"])}
    assert esquema57.validar_atencion(a, clinica) == []
    clinica["egreso"]["dx_muerte"] = None
    assert any("campo 42" in m for m in esquema57.validar_atencion(a, clinica))
    clinica["egreso"].update(dx_muerte="I46.9", fecha_salida=datetime(2026, 2, 14, 9, 0))
    assert any("anterior" in m for m in esquema57.validar_atencion(a, clinica))


@pytest.mark.parametrize("n", range(1, 58))
def test_cada_campo_llega_a_fhir(n):
    recursos, puestos = _recursos_fhir()
    texto = json.dumps(recursos + puestos, ensure_ascii=False)
    assert ESPERADO[n] in texto, f"El campo {n} ({campos57.CAMPOS[n - 1]['nombre']}) no aparece en los recursos FHIR"


def test_todos_los_recursos_son_fhir_r4_validos():
    modelos = pytest.importorskip("fhir.resources.R4B")
    recursos, puestos = _recursos_fhir()
    tipos = Counter()
    for r in recursos + puestos:
        modelos.get_fhir_model_class(r["resourceType"]).model_validate(r)
        tipos[r["resourceType"]] += 1
    assert {"Patient", "Encounter", "Condition", "MedicationRequest", "AllergyIntolerance", "FamilyMemberHistory",
            "Observation", "Practitioner", "Organization"} <= set(tipos)


def test_el_encuentro_se_actualiza_con_los_diagnosticos_y_sus_roles():
    _, puestos = _recursos_fhir()
    enc = puestos[0]
    roles = [d["use"]["coding"][0]["code"] for d in enc["diagnosis"]]
    assert roles == ["AD", "DD", "CM", "CM", "CM"]


def test_practitioner_y_organization_no_se_duplican_con_cache():
    llamadas = []
    cache = {}
    for _ in range(2):
        historia57_fhir.enviar_atencion(ATENCION, "1", lambda r: (llamadas.append(r["resourceType"]), str(len(llamadas)))[1],
                                        lambda r: None, cache)
    assert llamadas.count("Organization") == 1
