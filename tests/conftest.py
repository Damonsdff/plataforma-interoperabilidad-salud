"""
conftest.py — PROVISTO POR EL DOCENTE.
Fixtures de datos de prueba compartidos por todos los tests.
No requiere modificación para pasar el checklist mínimo.
"""
import sys
from datetime import date
from pathlib import Path
from uuid import uuid4

import pytest

# Permite ejecutar `pytest` desde la raíz del starter kit sin instalar el paquete
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from interoperabilidad.models import Condicion, Encuentro, Observacion, Paciente, Sede


@pytest.fixture
def sede_sincelejo():
    return Sede(1, "Sincelejo", "Meditech", "OpenMRS", "Appliance dedicado")


@pytest.fixture
def sede_cartagena():
    return Sede(2, "Cartagena", "Cerner", "Vendor propio", "Appliance imagenología")


@pytest.fixture
def paciente_a(sede_sincelejo):
    return Paciente(
        id_paciente=uuid4(),
        documento_identidad="1007654321",
        tipo_documento="CC",
        nombre_completo="Ana Maria Perez Lopez",
        fecha_nacimiento=date(1990, 5, 12),
        sexo="F",
        sede_origen=sede_sincelejo,
    )


@pytest.fixture
def paciente_a_duplicado_otra_sede(sede_cartagena):
    """Mismo paciente que paciente_a, pero registrado en otra sede con
    ligeras variaciones de digitación (caso típico de duplicado cross-sede)."""
    return Paciente(
        id_paciente=uuid4(),
        documento_identidad="1007654321",
        tipo_documento="CC",
        nombre_completo="Ana Maria Perez Lopez",
        fecha_nacimiento=date(1990, 5, 12),
        sexo="F",
        sede_origen=sede_cartagena,
    )


@pytest.fixture
def paciente_b_no_relacionado(sede_cartagena):
    return Paciente(
        id_paciente=uuid4(),
        documento_identidad="55667788",
        tipo_documento="CC",
        nombre_completo="Carlos Andres Gomez Ruiz",
        fecha_nacimiento=date(1985, 2, 20),
        sexo="M",
        sede_origen=sede_cartagena,
    )


@pytest.fixture
def condicion_diabetes():
    return Condicion(uuid4(), "E11", "Diabetes mellitus tipo 2", date(2024, 3, 1))


@pytest.fixture
def observacion_glucosa():
    from datetime import datetime
    return Observacion(uuid4(), "2339-0", "180", "mg/dL", datetime(2024, 3, 1, 8, 30))


@pytest.fixture
def encuentro(paciente_a, sede_sincelejo, condicion_diabetes, observacion_glucosa):
    from datetime import datetime
    return Encuentro(
        id_encuentro=uuid4(),
        paciente=paciente_a,
        sede=sede_sincelejo,
        fecha_atencion=datetime(2024, 3, 1, 8, 0),
        tipo_encuentro="Consulta externa",
        condiciones=[condicion_diabetes],
        observaciones=[observacion_glucosa],
    )
