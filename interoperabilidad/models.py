"""
models.py — PROVISTO POR EL DOCENTE.

Dataclasses que representan el modelo relacional de referencia (Figura 1
de la guía). No es necesario modificarlas para completar el desafío,
pero pueden extenderse si el equipo justifica el cambio en el documento
tipo paper (sección de Metodología).

Estas clases son simples contenedores de datos (sin lógica de negocio):
la lógica va en los servicios de interoperabilidad que sí deben
implementar (mappers.py, mpi_service.py).
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional
from uuid import UUID


@dataclass
class Sede:
    id_sede: int
    nombre_ciudad: str
    vendor_his: str
    vendor_emr: str
    vendor_lis_pacs: str


@dataclass
class Paciente:
    id_paciente: UUID
    documento_identidad: str
    tipo_documento: str
    nombre_completo: str
    fecha_nacimiento: date
    sexo: str
    sede_origen: Sede
    fhir_patient_id: Optional[UUID] = None  # None = pendiente de migrar
    # Extensión del equipo (justificada en el informe): campos adicionales de la Res. 866/2021
    # (campos 3, 6-15, 24 y 51-57). Es opcional, así que el contrato del docente no cambia.
    extra: dict = field(default_factory=dict)

    def esta_migrado(self) -> bool:
        return self.fhir_patient_id is not None


@dataclass
class Condicion:
    id_condicion: UUID
    codigo_cie10: str
    descripcion: str
    fecha_diagnostico: date


@dataclass
class Observacion:
    id_observacion: UUID
    codigo_loinc: str
    valor: str
    unidad: str
    fecha_medicion: datetime


@dataclass
class Encuentro:
    id_encuentro: UUID
    paciente: Paciente
    sede: Sede
    fecha_atencion: datetime
    tipo_encuentro: str
    condiciones: List[Condicion] = field(default_factory=list)
    observaciones: List[Observacion] = field(default_factory=list)
    estado_migracion: str = "PENDIENTE"  # PENDIENTE | MIGRADO | ERROR


@dataclass
class IdentidadFederada:
    id_mpi: UUID
    pacientes_por_sede: dict  # {id_sede: Paciente}
    score_coincidencia: float
