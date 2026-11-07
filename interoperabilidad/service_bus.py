"""
service_bus.py — PROVISTO POR EL DOCENTE (implementación funcional).

Esta clase SÍ viene resuelta: el foco de aprendizaje del laboratorio es
el mapeo HL7v2->FHIR y la resolución de identidad (MPI), no la
mensajería en sí. Se entrega un bus en memoria (pub/sub simple) para
que el equipo pueda conectar sus servicios sin depender de levantar
Kafka/RabbitMQ reales.

Si el equipo quiere sustituirlo por Kafka/RabbitMQ real (opcional, no
obligatorio), debe respetar esta misma interfaz pública: publicar() y
suscribir().
"""
from collections import defaultdict
from typing import Any, Callable, Dict, List


class HealthServiceBus:
    def __init__(self) -> None:
        self._suscriptores: Dict[str, List[Callable[[dict], None]]] = defaultdict(list)
        self.historial: List[Dict[str, Any]] = []  # útil para pruebas/depuración

    def publicar(self, topico: str, evento: dict) -> None:
        self.historial.append({"topico": topico, "evento": evento})
        for handler in self._suscriptores.get(topico, []):
            handler(evento)

    def suscribir(self, topico: str, handler: Callable[[dict], None]) -> None:
        self._suscriptores[topico].append(handler)
