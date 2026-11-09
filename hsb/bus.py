"""bus.py — Cadena del HSB: recepción -> validación -> transformación -> entrega, con cola, reintentos y mensajes muertos."""
import hashlib
import json
import logging
import time

from . import hl7, normalizador, validacion
from .entrega import EntregaError

log = logging.getLogger("hsb")


class Bus:
    def __init__(self, almacen, entrega, terminologia, max_intentos=4, espera_base=1.0, reloj=time.time):
        self.db, self.entrega, self.term = almacen, entrega, terminologia
        self.max_intentos, self.espera_base, self.reloj = max_intentos, espera_base, reloj
        self.oyentes = []  # funciones f(evento: dict): la auditoría (Fase 4) se engancha aquí

    def _emitir(self, tipo, id_, **datos):
        for f in self.oyentes:
            try:
                f({"tipo": tipo, "id_mensaje": id_, **datos})
            except Exception:  # la auditoría nunca debe romper el bus
                log.exception("oyente falló")

    # ── puertas de entrada ──
    def recibir_hl7(self, texto):
        ahora = self.reloj()
        try:
            sol = hl7.parsear_hl7(texto)
        except hl7.HL7Error as e:
            clave = "hl7-ilegible:" + hashlib.sha256((texto or "").encode()).hexdigest()[:16]
            return self._rechazo_ilegible(clave, "HL7", texto, str(e), ahora)
        return self._procesar(f"hl7:{sol['id_mensaje']}" if sol["id_mensaje"] else
                              "hl7-sin-id:" + hashlib.sha256(texto.encode()).hexdigest()[:16], sol, texto, ahora)

    def recibir_csv(self, texto, sede):
        try:
            filas = hl7.parsear_csv(texto, sede)
        except hl7.HL7Error as e:
            return [self._rechazo_ilegible("csv-ilegible:" + hashlib.sha256((texto or "").encode()).hexdigest()[:16], "CSV", texto, str(e), self.reloj())]
        res = []
        for crudo, sol in filas:
            clave = "csv:" + hashlib.sha256(f"{sede}|{crudo}".encode()).hexdigest()[:20]
            res.append(self._procesar(clave, sol, crudo, self.reloj()))
        return res

    # ── cadena ──
    def _rechazo_ilegible(self, clave, formato, texto, motivo, ahora):
        id_, previo = self.db.crear(clave, formato, "?", 0, "", (texto or "")[:2000], ahora)
        if previo:
            return self._duplicado(id_, previo)
        self.db.actualizar(id_, ahora, motivo, estado="rechazado", motivo=motivo)
        log.warning("msg=%s RECHAZADO: %s", id_, motivo)
        self._emitir("rechazado", id_, motivos=[motivo])
        return {"id": id_, "estado": "rechazado", "motivos": [motivo]}

    def _duplicado(self, id_, previo):
        self.db.sumar("duplicados")
        self.db.evento(id_, "duplicado", f"reenvío; estado original: {previo['estado']}", self.reloj())
        log.info("msg=%s DUPLICADO (estado original %s): no se reprocesa", id_, previo["estado"])
        self._emitir("duplicado", id_)
        return {"id": id_, "estado": "duplicado", "estado_original": previo["estado"]}

    def _procesar(self, clave, sol, payload, ahora):
        id_, previo = self.db.crear(clave, sol["formato"], sol["tipo"], sol["sede"], sol["documento"], payload, ahora)
        if previo:
            return self._duplicado(id_, previo)
        motivos = validacion.validar(sol, self.term)
        if motivos:
            self.db.actualizar(id_, ahora, "; ".join(motivos), estado="rechazado", motivo=json.dumps(motivos, ensure_ascii=False))
            log.warning("msg=%s RECHAZADO: %s", id_, "; ".join(motivos))
            self._emitir("rechazado", id_, motivos=motivos)
            return {"id": id_, "estado": "rechazado", "motivos": motivos}
        self.db.actualizar(id_, ahora, "validación correcta", estado="validado")
        bundle = normalizador.construir_bundle(sol)
        self.db.actualizar(id_, ahora, f"Bundle con {len(bundle['entry'])} recursos", estado="transformado",
                           bundle=json.dumps(bundle), solicitud=json.dumps(sol))
        return self._intentar(id_)

    def _intentar(self, id_):
        fila = self.db.obtener(id_)
        sol, bundle = json.loads(fila["solicitud"]), json.loads(fila["bundle"])
        n = fila["intentos"] + 1
        ahora = self.reloj()
        try:
            self.entrega.entregar(sol, bundle, normalizador.ids(sol)[0])
        except EntregaError as e:
            if n >= self.max_intentos:
                self.db.actualizar(id_, self.reloj(), str(e), estado="muerto", intentos=n, error=str(e), proximo_intento=None)
                log.error("msg=%s MUERTO tras %d intentos: %s", id_, n, e)
                self._emitir("muerto", id_, error=str(e))
                return {"id": id_, "estado": "muerto", "intentos": n, "error": str(e)}
            espera = self.espera_base * 2 ** (n - 1)
            self.db.actualizar(id_, self.reloj(), f"intento {n} falló: {e}; reintento en {espera:g}s", estado="reintentando",
                               intentos=n, error=str(e), proximo_intento=self.reloj() + espera)
            log.warning("msg=%s intento %d falló (%s); REINTENTANDO en %gs", id_, n, e, espera)
            self._emitir("reintentando", id_, intento=n, error=str(e))
            return {"id": id_, "estado": "reintentando", "intentos": n, "proximo_intento_s": espera, "error": str(e)}
        fin = self.reloj()
        self.db.actualizar(id_, fin, f"entregado en el intento {n}", estado="entregado", intentos=n, error=None,
                           entregado=fin, latencia_ms=(fin - fila["recibido"]) * 1000, proximo_intento=None)
        log.info("msg=%s ENTREGADO (intento %d, %.0f ms)", id_, n, (fin - fila["recibido"]) * 1000)
        self._emitir("entregado", id_, intentos=n, sede=sol["sede"], documento=sol["documento"])
        return {"id": id_, "estado": "entregado", "intentos": n}

    # ── cola ──
    def procesar_pendientes(self):
        """Reintenta los mensajes cuyo momento de reintento ya llegó. Lo llama el hilo de fondo (o las pruebas)."""
        return [self._intentar(f["id"]) for f in self.db.pendientes(self.reloj())]

    def reencolar(self, id_):
        f = self.db.obtener(id_)
        if not f or f["estado"] != "muerto":
            return None
        self.db.actualizar(id_, self.reloj(), "reencolado manualmente", estado="reintentando", intentos=0, proximo_intento=self.reloj())
        return self._intentar(id_)

    # ── métricas ──
    def metricas(self):
        por_estado, ult, lat_media, lat_max, por_sede = self.db.metricas(self.reloj())
        dup = self.db.contador("duplicados")
        procesados = sum(por_estado.values())
        fallidos = por_estado.get("rechazado", 0) + por_estado.get("muerto", 0)
        return {"mensajes_total": procesados, "por_estado": por_estado, "duplicados_detectados": dup,
                "ultimo_minuto": ult, "latencia_media_ms": round(lat_media, 1) if lat_media is not None else None,
                "latencia_max_ms": round(lat_max, 1) if lat_max is not None else None,
                "porcentaje_fallidos": round(100 * fallidos / procesados, 1) if procesados else 0.0,
                "entregados_por_sede": por_sede}
