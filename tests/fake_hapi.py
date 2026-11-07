"""
fake_hapi.py — Servidor FHIR SIMULADO para pruebas sin Docker.

Imita lo que usa el proyecto de HAPI FHIR: POST/PUT/GET de recursos, búsqueda por identifier / subject / patient,
_summary=count, Patient/{id}/$everything y Composition/{id}/$document. Además:
  * rechaza referencias a recursos que no existen (HAPI lo hace por defecto: integridad referencial),
  * valida la ESTRUCTURA del recurso contra FHIR R4B si está instalado `fhir.resources`
    (pip install fhir.resources); así se detectan elementos mal escritos antes de ir al HAPI real.

NO sustituye a HAPI: la demostración real usa el contenedor hapiproject/hapi del docker-compose.
"""
import itertools
import re
import threading

from flask import Flask, jsonify, request

try:
    from fhir.resources.R4B import get_fhir_model_class
except Exception:  # pragma: no cover
    get_fhir_model_class = None


def crear_app():
    app = Flask(__name__)
    almacen = {}                      # {(tipo, id): recurso}
    contador = itertools.count(1)
    app.almacen = almacen

    def referencias(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == "reference" and isinstance(v, str):
                    yield v
                else:
                    yield from referencias(v)
        elif isinstance(obj, list):
            for x in obj:
                yield from referencias(x)

    def guardar(tipo, recurso, rid):
        if recurso.get("resourceType") != tipo:
            return jsonify({"resourceType": "OperationOutcome", "issue": [{"diagnostics": "resourceType no coincide"}]}), 400
        if get_fhir_model_class is not None:
            try:
                get_fhir_model_class(tipo).model_validate(recurso)
            except Exception as e:
                return jsonify({"resourceType": "OperationOutcome", "issue": [{"diagnostics": f"Estructura FHIR inválida: {e}"}]}), 400
        for ref in referencias(recurso):
            m = re.match(r"^([A-Za-z]+)/([^/]+)$", ref)
            if m and (m.group(1), m.group(2)) not in almacen:
                return jsonify({"resourceType": "OperationOutcome", "issue": [{"diagnostics": f"Referencia inexistente: {ref}"}]}), 409
        recurso["id"] = rid
        recurso.setdefault("meta", {})["lastUpdated"] = "2026-11-05T12:00:00.000+00:00"
        almacen[(tipo, rid)] = recurso
        return jsonify(recurso), 201

    @app.post("/fhir/<tipo>")
    def crear(tipo):
        return guardar(tipo, request.get_json(force=True), str(next(contador)))

    @app.put("/fhir/<tipo>/<rid>")
    def actualizar(tipo, rid):
        if (tipo, rid) not in almacen:
            return jsonify({"resourceType": "OperationOutcome"}), 404
        return guardar(tipo, request.get_json(force=True), rid)

    @app.get("/fhir/<tipo>/<rid>")
    def leer(tipo, rid):
        r = almacen.get((tipo, rid))
        return (jsonify(r), 200) if r else (jsonify({"resourceType": "OperationOutcome"}), 404)

    def apunta_a(recurso, paciente_ref):
        return any(ref == paciente_ref for ref in referencias(recurso))

    @app.get("/fhir/<tipo>")
    def buscar(tipo):
        res = [r for (t, _), r in almacen.items() if t == tipo]
        ident = request.args.get("identifier")
        if ident:
            valor = ident.split("|")[-1]
            res = [r for r in res if any(i.get("value") == valor for i in r.get("identifier", []))]
        for param in ("subject", "patient"):
            if request.args.get(param):
                ref = request.args[param] if "/" in request.args[param] else f"Patient/{request.args[param]}"
                res = [r for r in res if apunta_a(r, ref)]
        if request.args.get("_summary") == "count":
            return jsonify({"resourceType": "Bundle", "type": "searchset", "total": len(res)})
        n = int(request.args.get("_count", 20))
        return jsonify({"resourceType": "Bundle", "type": "searchset", "total": len(res),
                        "entry": [{"resource": r} for r in res[:n]]})

    @app.get("/fhir/Patient/<rid>/$everything")
    def everything(rid):
        ref = f"Patient/{rid}"
        base = almacen.get(("Patient", rid))
        if not base:
            return jsonify({"resourceType": "OperationOutcome"}), 404
        propios = [r for r in almacen.values() if r["resourceType"] != "Patient" and apunta_a(r, ref)]
        extra, vistos = [], set()
        for r in propios:                      # recursos referenciados (Organization, Practitioner, ...)
            for rf in referencias(r):
                m = re.match(r"^([A-Za-z]+)/([^/]+)$", rf)
                if m and m.group(1) in ("Organization", "Practitioner") and rf not in vistos and (m.group(1), m.group(2)) in almacen:
                    vistos.add(rf)
                    extra.append(almacen[(m.group(1), m.group(2))])
        return jsonify({"resourceType": "Bundle", "type": "searchset",
                        "entry": [{"resource": r} for r in [base] + propios + extra]})

    @app.get("/fhir/Composition/<rid>/$document")
    def documento(rid):
        comp = almacen.get(("Composition", rid))
        if not comp:
            return jsonify({"resourceType": "OperationOutcome"}), 404
        entradas, vistos = [{"resource": comp}], set()
        for rf in referencias(comp):
            m = re.match(r"^([A-Za-z]+)/([^/]+)$", rf)
            if m and rf not in vistos and (m.group(1), m.group(2)) in almacen:
                vistos.add(rf)
                entradas.append({"resource": almacen[(m.group(1), m.group(2))]})
        return jsonify({"resourceType": "Bundle", "type": "document", "entry": entradas})

    return app


class ServidorFalso:
    """Levanta la app en un hilo (para pytest)."""

    def __init__(self, puerto=18080):
        from werkzeug.serving import make_server
        self.app = crear_app()
        self.servidor = make_server("127.0.0.1", puerto, self.app, threaded=True)
        self.url = f"http://127.0.0.1:{puerto}/fhir"
        self.hilo = threading.Thread(target=self.servidor.serve_forever, daemon=True)

    def iniciar(self):
        self.hilo.start()
        return self

    def detener(self):
        self.servidor.shutdown()


if __name__ == "__main__":
    s = ServidorFalso(8080).iniciar()
    print("HAPI simulado en", s.url)
    s.hilo.join()
