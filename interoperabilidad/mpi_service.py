"""
mpi_service.py — INTERFAZ PROVISTA / IMPLEMENTACION A CARGO DEL ESTUDIANTE.

Contrato del componente de resolución de identidad maestra de paciente
(Master Patient Index) entre las 3 sedes. Es el núcleo del problema de
sistemas distribuidos del laboratorio: un mismo paciente puede existir
como 3 registros distintos (uno por sede) y este servicio debe
resolverlos a una única IdentidadFederada.

QUE SI SE ENTREGA (docente): la forma del contrato y el umbral sugerido
(0.9) usado en el criterio de aceptación HU-04 de la guía.
QUE DEBE DESARROLLAR EL ESTUDIANTE: el algoritmo de comparación
(determinístico por documento_identidad, probabilístico por nombre +
fecha de nacimiento, o una combinación) y la lógica de creación /
actualización de IdentidadFederada.
"""
from abc import ABC, abstractmethod
from typing import List, Optional

from .models import IdentidadFederada, Paciente

UMBRAL_COINCIDENCIA_SUGERIDO = 0.9


class MPIService(ABC):

    @abstractmethod
    def calcular_score(self, paciente_a: Paciente, paciente_b: Paciente) -> float:
        """
        Debe retornar un float en [0.0, 1.0] que represente qué tan
        probable es que paciente_a y paciente_b sean la misma persona.

        TODO(estudiante): definir las reglas o pesos de comparación
        (documento_identidad, nombre_completo, fecha_nacimiento, sexo).
        Documentar la fórmula elegida en el paper (sección Metodología).
        """
        raise NotImplementedError

    @abstractmethod
    def resolver_identidad(
        self, paciente: Paciente, candidatos: List[Paciente]
    ) -> Optional[IdentidadFederada]:
        """
        Debe comparar 'paciente' contra la lista de 'candidatos' (registros
        de otras sedes), y si el mejor score >= UMBRAL_COINCIDENCIA_SUGERIDO,
        crear o actualizar una IdentidadFederada que los vincule.
        Si ningún candidato supera el umbral, debe retornar None
        (el paciente aún no tiene par federado).

        TODO(estudiante): implementar el criterio de decisión y el
        registro/actualización de IdentidadFederada.
        """
        raise NotImplementedError
