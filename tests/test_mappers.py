"""
test_mappers.py — PROVISTO POR EL DOCENTE.

Valida que la implementación del estudiante (solucion/mapper_estudiante.py)
cumple el contrato de HL7v2ToFhirMapper. No evalúa "qué tan bonito" está
el código, sólo que la forma de los recursos FHIR generados es correcta.

Ejecución: pytest tests/test_mappers.py -v
"""
import pytest

from solucion.mapper_estudiante import MapperEstudiante


@pytest.fixture
def mapper():
    return MapperEstudiante()


def test_mapear_paciente_retorna_resource_type_patient(mapper, paciente_a):
    recurso = mapper.mapear_paciente(paciente_a)
    assert recurso["resourceType"] == "Patient"
    assert "identifier" in recurso, "El recurso Patient debe incluir el documento de identidad como identifier"
    assert "name" in recurso


def test_mapear_condicion_usa_codigo_cie10(mapper, encuentro, condicion_diabetes):
    recurso = mapper.mapear_condicion(encuentro, condicion_diabetes)
    assert recurso["resourceType"] == "Condition"
    codigos = str(recurso.get("code", {}))
    assert "E11" in codigos, "El código CIE-10 de la Condicion debe aparecer en el recurso Condition"


def test_mapear_observacion_usa_codigo_loinc(mapper, encuentro, observacion_glucosa):
    recurso = mapper.mapear_observacion(encuentro, observacion_glucosa)
    assert recurso["resourceType"] == "Observation"
    codigos = str(recurso.get("code", {}))
    assert "2339-0" in codigos, "El código LOINC de la Observacion debe aparecer en el recurso Observation"


def test_generar_bundle_document_tipo_document(mapper, encuentro):
    bundle = mapper.generar_bundle_document(encuentro)
    assert bundle["resourceType"] == "Bundle"
    assert bundle["type"] == "document"
    assert "entry" in bundle and len(bundle["entry"]) >= 2, (
        "El Bundle debe incluir al menos la Composition y un recurso satélite"
    )
    tipos_incluidos = [e["resource"]["resourceType"] for e in bundle["entry"]]
    assert "Composition" in tipos_incluidos, "El primer recurso del Bundle document debe ser una Composition"
