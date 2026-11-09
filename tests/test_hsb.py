"""Pruebas del HSB (Fase 3). Usan los mensajes de ejemplos/ (contrato del docente) y un destino simulado."""
import os
import unittest

from hsb.almacen import Almacen
from hsb.app import crear_app
from hsb.bus import Bus
from hsb.entrega import EntregaError
from hsb.terminologia import Terminologia

EJ = os.path.join(os.path.dirname(__file__), "..", "ejemplos")


def leer(nombre):
    p = os.path.join(EJ, nombre)
    if not os.path.exists(p):
        p = os.path.join(os.path.dirname(__file__), "ejemplos", nombre)
    with open(p, encoding="utf-8", newline="") as f:
        return f.read()


class EntregaFalsa:
    """Simula HAPI + base de sede. `caido` hace fallar la entrega; `entregas` cuenta los pacientes por id."""
    def __init__(self):
        self.caido = False
        self.pacientes = {}
        self.bundles = []

    def entregar(self, sol, bundle, patient_id):
        if self.caido:
            raise EntregaError("HAPI no disponible: ConnectionError")
        self.bundles.append(bundle)
        self.pacientes[patient_id] = sol["documento"]   # upsert: misma clave = un solo paciente

    def salud(self):
        return {"hapi": "caido" if self.caido else "ok"}


class Reloj:
    def __init__(self): self.t = 1_000_000.0
    def __call__(self): return self.t
    def avanzar(self, s): self.t += s


class BaseHSB(unittest.TestCase):
    def setUp(self):
        self.entrega, self.reloj = EntregaFalsa(), Reloj()
        self.bus = Bus(Almacen(), self.entrega, Terminologia(), max_intentos=4, espera_base=1.0, reloj=self.reloj)


class TestEjemplos(BaseHSB):
    def test_adt_valido_se_entrega(self):
        r = self.bus.recibir_hl7(leer("01_adt_a01_valido_sede2.hl7"))
        self.assertEqual(r["estado"], "entregado")
        tipos = {e["resource"]["resourceType"]: e["resource"] for e in self.entrega.bundles[0]["entry"]}
        self.assertEqual(tipos["Patient"]["identifier"][0]["value"], "1007")
        self.assertEqual(tipos["Patient"]["id"], "s2-1007")
        self.assertEqual(tipos["Condition"]["code"]["coding"][0]["code"], "J45.9")
        self.assertIn("Encounter", tipos)

    def test_oru_observation_loinc(self):
        r = self.bus.recibir_hl7(leer("02_oru_r01_laboratorio_sede1.hl7"))
        self.assertEqual(r["estado"], "entregado")
        obs = [e["resource"] for e in self.entrega.bundles[0]["entry"] if e["resource"]["resourceType"] == "Observation"][0]
        self.assertEqual(obs["code"]["coding"][0]["code"], "718-7")
        self.assertEqual(obs["valueQuantity"]["value"], 13.8)
        self.assertEqual(obs["valueQuantity"]["unit"], "g/dL")
        self.assertIn("s1-1001", self.entrega.pacientes)

    def test_adt_invalido_tres_motivos(self):
        r = self.bus.recibir_hl7(leer("03_adt_a01_invalido.hl7"))
        self.assertEqual(r["estado"], "rechazado")
        self.assertEqual(len(r["motivos"]), 3)
        texto = " | ".join(r["motivos"])
        self.assertIn("documento no numérico", texto)
        self.assertIn("sexo no válido", texto)
        self.assertIn("sin mapeo a CIE-10", texto)
        self.assertEqual(self.entrega.bundles, [])   # no se transformó ni entregó
        self.assertEqual(self.bus.db.listar("rechazado")[0]["id"], r["id"])  # quedó registrado

    def test_csv_tres_entregados_dos_rechazados(self):
        res = self.bus.recibir_csv(leer("04_sede3_legado.csv"), 3)
        estados = [r["estado"] for r in res]
        self.assertEqual(estados.count("entregado"), 3)
        self.assertEqual(estados.count("rechazado"), 2)
        self.assertEqual(sorted(self.entrega.pacientes.values()), ["1008", "1009", "1010"])
        motivos = " ".join(m for r in res if r["estado"] == "rechazado" for m in r["motivos"])
        self.assertIn("DOLOR MISTERIOSO", motivos)
        self.assertIn("2 dígitos", motivos)

    def test_csv_triage_vacio_no_rechaza(self):
        res = self.bus.recibir_csv(leer("04_sede3_legado.csv"), 3)
        self.assertEqual(res[1]["estado"], "entregado")   # 1009 sin triage


class TestIdempotencia(BaseHSB):
    def test_reenvio_es_duplicado_y_un_solo_paciente(self):
        msg = leer("01_adt_a01_valido_sede2.hl7")
        self.assertEqual(self.bus.recibir_hl7(msg)["estado"], "entregado")
        r2 = self.bus.recibir_hl7(msg)
        self.assertEqual(r2["estado"], "duplicado")
        self.assertEqual(len(self.entrega.bundles), 1)
        self.assertEqual(len(self.entrega.pacientes), 1)
        self.assertEqual(self.bus.metricas()["duplicados_detectados"], 1)

    def test_csv_duplicado_por_hash(self):
        txt = leer("04_sede3_legado.csv")
        self.bus.recibir_csv(txt, 3)
        res = self.bus.recibir_csv(txt, 3)
        self.assertTrue(all(r["estado"] == "duplicado" for r in res))

    def test_idempotencia_persistente(self):
        """La clave vive en el almacén, no en memoria: otro Bus sobre el mismo almacén también ve el duplicado."""
        msg = leer("01_adt_a01_valido_sede2.hl7")
        self.bus.recibir_hl7(msg)
        otro = Bus(self.bus.db, self.entrega, Terminologia(), reloj=self.reloj)
        self.assertEqual(otro.recibir_hl7(msg)["estado"], "duplicado")


class TestReintentos(BaseHSB):
    def test_falla_se_reintenta_y_se_entrega_sin_duplicar(self):
        self.entrega.caido = True
        r = self.bus.recibir_hl7(leer("02_oru_r01_laboratorio_sede1.hl7"))
        self.assertEqual(r["estado"], "reintentando")
        self.assertEqual(r["proximo_intento_s"], 1.0)
        self.assertEqual(self.bus.procesar_pendientes(), [])      # aún no toca
        self.entrega.caido = False
        self.reloj.avanzar(1.1)
        res = self.bus.procesar_pendientes()
        self.assertEqual(res[0]["estado"], "entregado")
        self.assertEqual(res[0]["intentos"], 2)
        self.assertEqual(len(self.entrega.pacientes), 1)
        estados = [e["estado"] for e in self.bus.db.eventos(r["id"])]
        self.assertEqual(estados, ["recibido", "validado", "transformado", "reintentando", "entregado"])

    def test_retroceso_exponencial_y_cola_de_muertos(self):
        self.entrega.caido = True
        r = self.bus.recibir_hl7(leer("02_oru_r01_laboratorio_sede1.hl7"))
        esperas = [r["proximo_intento_s"]]
        for _ in range(2):
            self.reloj.avanzar(10)
            esperas.append(self.bus.procesar_pendientes()[0]["proximo_intento_s"])
        self.assertEqual(esperas, [1.0, 2.0, 4.0])
        self.reloj.avanzar(10)
        ultimo = self.bus.procesar_pendientes()[0]
        self.assertEqual(ultimo["estado"], "muerto")
        self.assertEqual(ultimo["intentos"], 4)
        self.reloj.avanzar(1000)
        self.assertEqual(self.bus.procesar_pendientes(), [])      # no reintenta para siempre

    def test_reencolar_mensaje_muerto(self):
        self.entrega.caido = True
        r = self.bus.recibir_hl7(leer("02_oru_r01_laboratorio_sede1.hl7"))
        for _ in range(3):
            self.reloj.avanzar(10)
            self.bus.procesar_pendientes()
        self.assertEqual(self.bus.db.obtener(r["id"])["estado"], "muerto")
        self.entrega.caido = False
        self.assertEqual(self.bus.reencolar(r["id"])["estado"], "entregado")
        self.assertIsNone(self.bus.reencolar(r["id"]))             # ya no está muerto


class TestRobustez(BaseHSB):
    def test_texto_que_no_es_hl7_se_rechaza_con_motivo(self):
        r = self.bus.recibir_hl7("hola mundo")
        self.assertEqual(r["estado"], "rechazado")

    def test_csv_encabezado_incorrecto(self):
        self.assertEqual(self.bus.recibir_csv("a;b\n1;2\n", 1)[0]["estado"], "rechazado")

    def test_sede_invalida(self):
        r = self.bus.recibir_hl7(leer("01_adt_a01_valido_sede2.hl7").replace("SEDE2", "SEDE9").replace("MSG-0001", "MSG-9"))
        self.assertEqual(r["estado"], "rechazado")
        self.assertIn("sede no válida", r["motivos"][0])

    def test_oyente_de_auditoria_recibe_eventos(self):
        vistos = []
        self.bus.oyentes.append(vistos.append)
        self.bus.recibir_hl7(leer("01_adt_a01_valido_sede2.hl7"))
        self.bus.recibir_hl7(leer("01_adt_a01_valido_sede2.hl7"))
        self.assertEqual([v["tipo"] for v in vistos], ["entregado", "duplicado"])


class TestHTTP(BaseHSB):
    def setUp(self):
        super().setUp()
        self.cli = crear_app(bus=self.bus, entrega=self.entrega, arrancar_hilo=False).test_client()

    def test_codigos_http_y_metricas(self):
        self.assertEqual(self.cli.post("/hsb/hl7", data=leer("01_adt_a01_valido_sede2.hl7")).status_code, 200)
        self.assertEqual(self.cli.post("/hsb/hl7", data=leer("03_adt_a01_invalido.hl7")).status_code, 422)
        self.entrega.caido = True
        self.assertEqual(self.cli.post("/hsb/hl7", data=leer("02_oru_r01_laboratorio_sede1.hl7")).status_code, 202)
        r = self.cli.post("/hsb/csv?sede=3", data=leer("04_sede3_legado.csv"))
        self.assertEqual(r.status_code, 200)
        m = self.cli.get("/metrics").get_json()
        self.assertEqual(m["por_estado"]["rechazado"], 3)  # 03.hl7 + 2 filas del CSV
        self.assertIn("latencia_media_ms", m)
        self.assertEqual(self.cli.get("/health").get_json()["estado"], "degradado")
        self.assertEqual(self.cli.post("/hsb/csv", data="x").status_code, 400)


if __name__ == "__main__":
    unittest.main()
