"""
test_service_bus.py — PROVISTO POR EL DOCENTE.

Este test valida infraestructura YA RESUELTA (HealthServiceBus). Debe
pasar sin que el equipo toque nada: si falla, algo se rompió en
interoperabilidad/service_bus.py y debe revisarse antes de continuar.
"""
from interoperabilidad.service_bus import HealthServiceBus


def test_publicar_y_suscribir():
    bus = HealthServiceBus()
    recibidos = []

    bus.suscribir("paciente.federado", lambda evento: recibidos.append(evento))
    bus.publicar("paciente.federado", {"sede": "historia_clinica_sede1", "ok": True})

    assert len(recibidos) == 1
    assert recibidos[0]["sede"] == "historia_clinica_sede1"
    assert len(bus.historial) == 1
