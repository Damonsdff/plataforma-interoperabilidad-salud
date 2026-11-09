"""app.py — Servicio HSB (Flask). Puertas: POST /hsb/hl7, POST /hsb/csv?sede=N. Operación: /health, /metrics, /hsb/mensajes."""
import logging
import os
import threading
import time

from flask import Flask, Response, jsonify, request

from .almacen import Almacen
from .bus import Bus
from .entrega import EntregaReal
from .terminologia import Terminologia

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
CODIGO = {"entregado": 200, "duplicado": 200, "reintentando": 202, "rechazado": 422, "muerto": 503}


def crear_app(bus=None, entrega=None, arrancar_hilo=True):
    entrega = entrega or EntregaReal()
    bus = bus or Bus(Almacen(os.environ.get("HSB_DB", "/data/hsb.db")), entrega, Terminologia(),
                     max_intentos=int(os.environ.get("MAX_INTENTOS", 4)), espera_base=float(os.environ.get("ESPERA_BASE_S", 1)))
    app = Flask(__name__)
    app.bus = bus

    # ── Enganchar auditoría encadenada por hash (Fase 4) ────────────────────
    try:
        from auditoria import get_auditoria
        bus.oyentes.append(get_auditoria().oyente_bus)
        logging.getLogger("hsb").info("Auditoría encadenada por hash activada en HSB.")
    except Exception as _e_aud:
        logging.getLogger("hsb").warning("Auditoría no disponible en este entorno: %s", _e_aud)

    if arrancar_hilo:
        def trabajador():
            while True:
                try:
                    bus.procesar_pendientes()
                except Exception:
                    logging.getLogger("hsb").exception("error en la cola de reintentos")
                time.sleep(0.5)
        threading.Thread(target=trabajador, daemon=True).start()

    @app.post("/hsb/hl7")
    def hl7_in():
        r = bus.recibir_hl7(request.get_data(as_text=True))
        return jsonify(r), CODIGO.get(r["estado"], 200)

    @app.post("/hsb/csv")
    def csv_in():
        try:
            sede = int(request.args.get("sede", ""))
        except ValueError:
            return jsonify({"error": "falta el parámetro ?sede=N (1 a 3)"}), 400
        res = bus.recibir_csv(request.get_data(as_text=True), sede)
        cuenta = {}
        for r in res:
            cuenta[r["estado"]] = cuenta.get(r["estado"], 0) + 1
        return jsonify({"total": len(res), "por_estado": cuenta, "resultados": res}), 200

    @app.get("/hsb/mensajes")
    def mensajes():
        return jsonify(bus.db.listar(request.args.get("estado")))

    @app.get("/hsb/mensajes/<int:id_>")
    def mensaje(id_):
        f = bus.db.obtener(id_)
        if not f:
            return jsonify({"error": "no existe"}), 404
        f.pop("payload", None); f.pop("bundle", None); f.pop("solicitud", None)
        return jsonify({**f, "eventos": bus.db.eventos(id_)})

    @app.post("/hsb/mensajes/<int:id_>/reencolar")
    def reencolar(id_):
        r = bus.reencolar(id_)
        return (jsonify(r), 200) if r else (jsonify({"error": "solo se reencolan mensajes en estado muerto"}), 409)

    @app.get("/health")
    def health():
        deps = entrega.salud() if hasattr(entrega, "salud") else {}
        return jsonify({"servicio": "hsb", "estado": "ok" if all(v == "ok" for v in deps.values()) else "degradado", "dependencias": deps})

    @app.get("/metrics")
    def metrics():
        m = bus.metricas()
        if request.args.get("format") == "prom":
            lin = [f'hsb_mensajes{{estado="{k}"}} {v}' for k, v in m["por_estado"].items()]
            lin += [f"hsb_duplicados {m['duplicados_detectados']}", f"hsb_mensajes_ultimo_minuto {m['ultimo_minuto']}",
                    f"hsb_porcentaje_fallidos {m['porcentaje_fallidos']}", f"hsb_latencia_media_ms {m['latencia_media_ms'] or 0}"]
            return Response("\n".join(lin) + "\n", mimetype="text/plain")
        return jsonify(m)

    return app


if __name__ == "__main__":
    crear_app().run(host="0.0.0.0", port=8000)
