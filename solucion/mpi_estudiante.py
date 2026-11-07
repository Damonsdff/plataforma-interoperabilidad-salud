"""
mpi_estudiante.py — ARCHIVO A COMPLETAR POR EL ESTUDIANTE.

Implemente aquí su propia subclase de MPIService. Los tests en
tests/test_mpi_service.py importan esta clase exactamente desde esta
ruta (solucion.mpi_estudiante.MPIEstudiante).
"""
from typing import List, Optional
from uuid import uuid4

from interoperabilidad.mpi_service import MPIService, UMBRAL_COINCIDENCIA_SUGERIDO
from interoperabilidad.models import IdentidadFederada, Paciente


class MPIEstudiante(MPIService):

    def calcular_score(self, paciente_a: Paciente, paciente_b: Paciente) -> float:
        score = 0.0
        if paciente_a.documento_identidad == paciente_b.documento_identidad:
            score += 0.7
        if paciente_a.nombre_completo == paciente_b.nombre_completo:
            score += 0.2
        if paciente_a.fecha_nacimiento == paciente_b.fecha_nacimiento:
            score += 0.1
        return score

    def resolver_identidad(
        self, paciente: Paciente, candidatos: List[Paciente]
    ) -> Optional[IdentidadFederada]:
        if not candidatos:
            return None

        mejor_candidato = max(candidatos, key=lambda c: self.calcular_score(paciente, c))
        mejor_score = self.calcular_score(paciente, mejor_candidato)

        if mejor_score >= UMBRAL_COINCIDENCIA_SUGERIDO:
            return IdentidadFederada(
                id_mpi=uuid4(),
                pacientes_por_sede={
                    paciente.sede_origen.id_sede: paciente,
                    mejor_candidato.sede_origen.id_sede: mejor_candidato,
                },
                score_coincidencia=mejor_score,
            )
        return None
