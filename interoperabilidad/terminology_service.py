"""
terminology_service.py — PROVISTO POR EL DOCENTE (base funcional + extensión opcional).

Se entrega una implementación mínima que normaliza un par de códigos de
ejemplo, para que el equipo no tenga que partir de cero. Extender la
tabla de mapeo (o cambiar la fuente a un servicio terminológico real)
es OPCIONAL y no hace parte de los entregables obligatorios del
checklist (Tabla 4 de la guía) — se valora como mérito adicional.
"""
from typing import Optional

# TODO(estudiante, OPCIONAL): ampliar esta tabla o reemplazarla por
# consultas a un servicio terminológico real (p. ej. tx.fhir.org).
_CIE10_EJEMPLO = {
    "E11": "Diabetes mellitus tipo 2",
    "I10": "Hipertensión esencial (primaria)",
}
_LOINC_EJEMPLO = {
    "8480-6": "Presión arterial sistólica",
    "2339-0": "Glucosa en sangre",
}


class TerminologyService:
    def normalizar_cie10(self, codigo: str) -> Optional[str]:
        return _CIE10_EJEMPLO.get(codigo)

    def normalizar_loinc(self, codigo: str) -> Optional[str]:
        return _LOINC_EJEMPLO.get(codigo)
