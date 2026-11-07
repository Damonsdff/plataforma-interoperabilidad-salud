"""
mappers.py — INTERFAZ PROVISTA / IMPLEMENTACION A CARGO DEL ESTUDIANTE.

Define el contrato que debe cumplir el adaptador que traduce los
registros nativos de cada sede (Meditech, Cerner, OpenMRS, vendor
propietario, etc.) a recursos HL7 FHIR R4.

QUE SI SE ENTREGA (docente):
    - La forma del contrato (nombres de método, tipos de entrada/salida).
QUE DEBE DESARROLLAR EL ESTUDIANTE:
    - El cuerpo de cada método: cómo se construye cada recurso FHIR,
      qué campos de los 57 de la Res. 866/2021 se mapean, y cómo se
      arma el Bundle tipo document para el RDA (Res. 1888/2025).

No modifique las firmas de los métodos: los tests de tests/test_mappers.py
importan esta interfaz para validar que su implementación cumple el
contrato, sin importar cómo lo resuelva internamente.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict

from .models import Encuentro, Paciente


class HL7v2ToFhirMapper(ABC):

    @abstractmethod
    def mapear_paciente(self, paciente: Paciente) -> Dict[str, Any]:
        """
        Debe retornar un dict con forma de recurso FHIR Patient, p. ej.:
            {"resourceType": "Patient", "id": ..., "identifier": [...],
             "name": [...], "birthDate": ..., "gender": ...}

        TODO(estudiante): completar el mapeo de campos obligatorios
        de la Res. 866/2021 aplicables a Patient.
        """
        raise NotImplementedError

    @abstractmethod
    def mapear_condicion(self, encuentro: Encuentro, condicion) -> Dict[str, Any]:
        """
        Debe retornar un recurso FHIR Condition, codificado en CIE-10
        (system: "http://hl7.org/fhir/sid/icd-10").

        TODO(estudiante): construir el CodeableConcept con el código
        CIE-10 de la Condicion y enlazar el 'subject' al Patient mapeado.
        """
        raise NotImplementedError

    @abstractmethod
    def mapear_observacion(self, encuentro: Encuentro, observacion) -> Dict[str, Any]:
        """
        Debe retornar un recurso FHIR Observation, codificado en LOINC
        (system: "http://loinc.org").

        TODO(estudiante): construir 'code', 'valueQuantity' o
        'valueString' según corresponda, y enlazar 'encounter'.
        """
        raise NotImplementedError

    @abstractmethod
    def generar_bundle_document(self, encuentro: Encuentro) -> Dict[str, Any]:
        """
        Debe retornar un Bundle FHIR de tipo "document": una Composition
        (secciones por tipo de recurso) seguida de todos los recursos
        satélite (Patient, Encounter, Condition, Observation,
        Practitioner, Organization si aplica). Corresponde al RDA de
        la Res. 1888/2025.

        Sugerencia: reutilizar mapear_paciente / mapear_condicion /
        mapear_observacion dentro de este método en vez de duplicar
        lógica de mapeo.

        TODO(estudiante): construir la Composition con sus 'section'
        y ensamblar el Bundle {"resourceType": "Bundle", "type": "document", "entry": [...]}.
        """
        raise NotImplementedError

    @abstractmethod
    def enviar_a_servidor_fhir(self, recurso: Dict[str, Any], base_url: str) -> Dict[str, Any]:
        """
        Debe hacer POST del recurso al servidor HAPI FHIR (base_url,
        p. ej. http://localhost:8080/fhir) y retornar la respuesta
        (incluyendo el id asignado por el servidor).

        TODO(estudiante): usar requests.post(...) y manejar errores
        HTTP (4xx/5xx) sin detener toda la migración por sede.
        """
        raise NotImplementedError
