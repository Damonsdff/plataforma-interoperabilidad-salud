from typing import Any, Dict

import requests

from interoperabilidad.mappers import HL7v2ToFhirMapper
from interoperabilidad.models import Encuentro, Paciente
from solucion import historia57_fhir


class MapperEstudiante(HL7v2ToFhirMapper):

    def mapear_paciente(self, paciente: Paciente) -> Dict[str, Any]:
        mapa_genero = {"M": "male", "F": "female"}
        genero_fhir = mapa_genero.get(paciente.sexo, "unknown")

        partes = paciente.nombre_completo.split()
        # partes es una lista, ej: ["Ana", "Maria", "Perez", "Lopez"]
        # RELLENA_AQUI: family = apellidos (las ultimas palabras)
        # RELLENA_AQUI: given = nombres (las primeras palabras, como lista)
        mitad = len(partes) // 2
        family = " ".join(partes[mitad:])
        given = partes[:mitad]

        recurso = {
            "resourceType": "Patient",
            "id": str(paciente.id_paciente),
            "identifier": [
                {
                    "system": "http://uajs.edu.co/tipo-documento/" + paciente.tipo_documento,
                    "value": paciente.documento_identidad,
                }
            ],
            "name": [{"family": family, "given": given}],
            "birthDate": paciente.fecha_nacimiento.isoformat(),
            "gender": genero_fhir,
        }
        # Campos adicionales de la Res. 866/2021 (si la sede los capturó)
        if paciente.extra:
            datos = {**paciente.extra, "sexo": paciente.sexo, "tipo_documento": paciente.tipo_documento,
                     "nombre_completo": paciente.nombre_completo}
            historia57_fhir.completar_paciente_fhir(recurso, datos)
        return recurso

    def mapear_condicion(self, encuentro: Encuentro, condicion) -> Dict[str, Any]:
        return {
            "resourceType": "Condition",
            "subject": {"reference": "Patient/" + str(encuentro.paciente.id_paciente)},
            "code": {
                "coding": [
                    {
                        "system": "http://hl7.org/fhir/sid/icd-10",
                        "code": condicion.codigo_cie10,
                        "display": condicion.descripcion,
                    }
                ]
            },
        }

    def mapear_observacion(self, encuentro: Encuentro, observacion) -> Dict[str, Any]:
        return {
            "resourceType": "Observation",
            "status": "final",
            "subject": {"reference": f"Patient/{encuentro.paciente.id_paciente}"},
            "code": {
                "coding": [
                    {
                        "system": "http://loinc.org",
                        "code": observacion.codigo_loinc,
                        "display": observacion.codigo_loinc,
                    }
                ]
            },
            "valueQuantity": {
                "value": float(observacion.valor),
                "unit": observacion.unidad,
            },
        }

    def generar_bundle_document(self, encuentro: Encuentro) -> Dict[str, Any]:
        paciente_fhir = self.mapear_paciente(encuentro.paciente)
        condiciones_fhir = [self.mapear_condicion(encuentro, c) for c in encuentro.condiciones]
        observaciones_fhir = [self.mapear_observacion(encuentro, o) for o in encuentro.observaciones]

        composition = {
            "resourceType": "Composition",
            "type": {"coding": [{"system": "http://loinc.org", "code": "nota-clinica"}]},
            "subject": {"reference": f"Patient/{encuentro.paciente.id_paciente}"},
        }

        entradas = [{"resource": composition}, {"resource": paciente_fhir}]
        for c in condiciones_fhir:
            entradas.append({"resource": c})
        for o in observaciones_fhir:
            entradas.append({"resource": o})

        return {
            "resourceType": "Bundle",
            "type": "document",
            "entry": entradas,
        }

    def enviar_a_servidor_fhir(self, recurso: Dict[str, Any], base_url: str) -> Dict[str, Any]:
        tipo = recurso["resourceType"]
        url = f"{base_url}/{tipo}"
        respuesta = requests.post(url, json=recurso)
        if respuesta.status_code not in (200, 201):
            raise RuntimeError(
                f"Error al enviar {tipo} a FHIR: HTTP {respuesta.status_code} - {respuesta.text}"
            )
        return respuesta.json()
