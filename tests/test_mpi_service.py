"""
test_mpi_service.py — PROVISTO POR EL DOCENTE.

Valida el comportamiento esperado del MPIService del estudiante frente
a dos casos de referencia: un duplicado real cross-sede (debe federarse)
y dos pacientes no relacionados (no debe federarse).

Ejecución: pytest tests/test_mpi_service.py -v
"""
import pytest

from interoperabilidad.mpi_service import UMBRAL_COINCIDENCIA_SUGERIDO
from solucion.mpi_estudiante import MPIEstudiante


@pytest.fixture
def mpi():
    return MPIEstudiante()


def test_score_alto_para_duplicado_real(mpi, paciente_a, paciente_a_duplicado_otra_sede):
    score = mpi.calcular_score(paciente_a, paciente_a_duplicado_otra_sede)
    assert 0.0 <= score <= 1.0, "El score debe estar normalizado entre 0 y 1"
    assert score >= UMBRAL_COINCIDENCIA_SUGERIDO, (
        "Dos registros con mismo documento, nombre y fecha de nacimiento "
        "deben producir un score alto (>= umbral sugerido)"
    )


def test_score_bajo_para_pacientes_no_relacionados(mpi, paciente_a, paciente_b_no_relacionado):
    score = mpi.calcular_score(paciente_a, paciente_b_no_relacionado)
    assert 0.0 <= score <= 1.0
    assert score < UMBRAL_COINCIDENCIA_SUGERIDO, (
        "Dos pacientes sin relación no deben superar el umbral de coincidencia"
    )


def test_resolver_identidad_federa_al_duplicado(mpi, paciente_a, paciente_a_duplicado_otra_sede):
    identidad = mpi.resolver_identidad(paciente_a, candidatos=[paciente_a_duplicado_otra_sede])
    assert identidad is not None, "Debe crearse una IdentidadFederada cuando hay un candidato sobre el umbral"
    assert identidad.score_coincidencia >= UMBRAL_COINCIDENCIA_SUGERIDO


def test_resolver_identidad_no_federa_sin_candidatos_validos(mpi, paciente_a, paciente_b_no_relacionado):
    identidad = mpi.resolver_identidad(paciente_a, candidatos=[paciente_b_no_relacionado])
    assert identidad is None, "No debe federarse cuando ningún candidato supera el umbral"
