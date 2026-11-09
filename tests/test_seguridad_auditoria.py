"""
test_seguridad_auditoria.py — Tests de Fase 4: JWT, roles y cadena de auditoría.

Cubre:
  - Generación y verificación de tokens JWT
  - Acceso permitido y denegado por rol
  - Cadena de auditoría íntegra
  - Detección de alteración en un evento de auditoría
"""
import sys
import os
import time
import unittest

# Permite importar desde la raíz del proyecto
RAIZ = os.path.join(os.path.dirname(__file__), "..")
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from seguridad import generar_token, verificar_token
from auditoria import Auditoria


class TestJWT(unittest.TestCase):
    """Verifica la generación, verificación y rechazo de tokens JWT."""

    def test_token_valido_devuelve_payload(self):
        token = generar_token("medico_perez", "medico", sede=None)
        payload = verificar_token(token)
        self.assertEqual(payload["sub"], "medico_perez")
        self.assertEqual(payload["rol"], "medico")

    def test_token_expirado_lanza_error(self):
        import seguridad
        orig = seguridad.JWT_EXPIRACION_S
        try:
            seguridad.JWT_EXPIRACION_S = -1  # ya expirado
            token = generar_token("x", "medico")
            with self.assertRaises(ValueError) as ctx:
                verificar_token(token)
            self.assertIn("expirado", str(ctx.exception))
        finally:
            seguridad.JWT_EXPIRACION_S = orig

    def test_token_firma_alterada_lanza_error(self):
        token = generar_token("auditor", "auditor")
        # Alterar el payload
        partes = token.split(".")
        partes[1] = partes[1][:-3] + "aaa"
        token_malo = ".".join(partes)
        with self.assertRaises(ValueError):
            verificar_token(token_malo)

    def test_token_incompleto_lanza_error(self):
        with self.assertRaises(ValueError):
            verificar_token("esto.no_es_un_jwt")

    def test_token_incluye_rol_y_extra(self):
        token = generar_token("admin_sincelejo", "admisionista", sede=1)
        payload = verificar_token(token)
        self.assertEqual(payload["rol"], "admisionista")
        self.assertEqual(payload["sede"], 1)


class TestControlAcceso(unittest.TestCase):
    """Verifica acceso permitido y denegado con el decorador requiere_rol."""

    def setUp(self):
        """Crea una mini-app Flask con rutas protegidas."""
        from flask import Flask, jsonify
        from seguridad import requiere_rol

        self.app = Flask(__name__)
        self.app.secret_key = "test-secret"

        @self.app.route("/solo-medico")
        @requiere_rol("medico")
        def ruta_medico():
            return jsonify({"ok": True, "rol": "medico"})

        @self.app.route("/medico-o-auditor")
        @requiere_rol("medico", "auditor")
        def ruta_mixta():
            return jsonify({"ok": True})

        @self.app.route("/publica")
        def ruta_publica():
            return jsonify({"ok": True})

        self.client = self.app.test_client()

    def _headers(self, token):
        return {"Authorization": f"Bearer {token}"}

    def test_medico_accede_a_ruta_de_medico(self):
        token = generar_token("medico_perez", "medico")
        r = self.client.get("/solo-medico", headers=self._headers(token))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.get_json()["ok"])

    def test_admisionista_no_puede_acceder_a_ruta_de_medico(self):
        """PRUEBA DE ACCESO DENEGADO: el admisionista no puede ver diagnósticos del médico."""
        token = generar_token("admin_sincelejo", "admisionista", sede=1)
        r = self.client.get("/solo-medico", headers=self._headers(token))
        self.assertEqual(r.status_code, 403)
        self.assertIn("Acceso denegado", r.get_json()["error"])
        self.assertEqual(r.get_json()["codigo"], "AUTH_FORBIDDEN")

    def test_auditor_accede_a_ruta_mixta(self):
        """PRUEBA DE ACCESO PERMITIDO: el auditor puede ver la ruta compartida."""
        token = generar_token("auditor", "auditor")
        r = self.client.get("/medico-o-auditor", headers=self._headers(token))
        self.assertEqual(r.status_code, 200)

    def test_sin_token_devuelve_401(self):
        r = self.client.get("/solo-medico")
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.get_json()["codigo"], "AUTH_MISSING")

    def test_token_invalido_devuelve_401(self):
        r = self.client.get("/solo-medico", headers={"Authorization": "Bearer token-basura"})
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.get_json()["codigo"], "AUTH_INVALID")

    def test_paciente_no_puede_acceder_a_ruta_de_medico(self):
        """Un paciente solo ve su propia historia, nunca la vista del médico."""
        token = generar_token("paciente_1007654321", "paciente", documento="1007654321")
        r = self.client.get("/solo-medico", headers=self._headers(token))
        self.assertEqual(r.status_code, 403)


class TestAuditoria(unittest.TestCase):
    """Verifica la cadena de hash de auditoría y su verificación."""

    def setUp(self):
        self.aud = Auditoria(":memory:")  # BD en memoria para tests

    def test_primer_evento_usa_genesis(self):
        ev = self.aud.registrar("sistema", "inicio", "exito", "arranque del sistema")
        self.assertEqual(ev["hash_ant"], "GENESIS")
        self.assertIsNotNone(ev["hash_propio"])

    def test_cadena_correcta_pasa_verificacion(self):
        self.aud.registrar("admin", "auth.login", "exito")
        self.aud.registrar("medico_perez", "paciente.consultar", "exito", "doc=1007654321")
        self.aud.registrar("hsb", "mensaje.entregado", "exito", "msg_id=42")
        resultado = self.aud.verificar_cadena()
        self.assertTrue(resultado["ok"])
        self.assertEqual(resultado["total"], 3)
        self.assertEqual(resultado["errores"], [])

    def test_alterar_evento_es_detectado(self):
        """
        PRUEBA CLAVE (rúbrica): si alguien altera un registro de auditoría,
        el verificador DEBE detectarlo.
        """
        self.aud.registrar("admin", "auth.login", "exito")
        self.aud.registrar("auditor", "auditoria.consultar", "exito")

        # Alterar directamente en la BD (simulando un atacante)
        with self.aud.lock:
            self.aud.con.execute(
                "UPDATE evento_auditoria SET resultado='denegado' WHERE id=1"
            )
            self.aud.con.commit()

        resultado = self.aud.verificar_cadena()
        self.assertFalse(resultado["ok"], "La verificación debería detectar la alteración")
        self.assertTrue(len(resultado["errores"]) > 0)
        ids_con_error = [e["id"] for e in resultado["errores"]]
        self.assertIn(1, ids_con_error)

    def test_alterar_hash_en_cadena_es_detectado(self):
        """Si se altera el hash_ant de un evento, la cadena se rompe."""
        self.aud.registrar("x", "a", "exito")
        self.aud.registrar("x", "b", "exito")
        self.aud.registrar("x", "c", "exito")

        # Alterar hash_ant del tercer evento
        with self.aud.lock:
            self.aud.con.execute(
                "UPDATE evento_auditoria SET hash_ant='hash-falso-inyectado' WHERE id=3"
            )
            self.aud.con.commit()

        resultado = self.aud.verificar_cadena()
        self.assertFalse(resultado["ok"])

    def test_evento_de_bus_engancha_bien(self):
        """El oyente del bus registra el evento con el tipo correcto."""
        evento = {"tipo": "entregado", "id_mensaje": 7, "sede": 2, "documento": "1007654321"}
        self.aud.oyente_bus(evento)
        eventos = self.aud.listar()
        self.assertEqual(len(eventos), 1)
        self.assertEqual(eventos[0]["que"], "mensaje.entregado")
        self.assertEqual(eventos[0]["quien"], "hsb")

    def test_cadena_vacia_es_ok(self):
        resultado = self.aud.verificar_cadena()
        self.assertTrue(resultado["ok"])
        self.assertEqual(resultado["total"], 0)


class TestIntegracionHSBAuditoria(unittest.TestCase):
    """Integra el Bus con la Auditoría para verificar el flujo completo."""

    def test_bus_emite_eventos_que_llegan_a_auditoria(self):
        import os
        from hsb.almacen import Almacen
        from hsb.bus import Bus
        from hsb.entrega import EntregaError
        from hsb.terminologia import Terminologia

        aud = Auditoria(":memory:")

        class EntregaFalsa:
            def entregar(self, sol, bundle, pid): pass
            def salud(self): return {}

        bus = Bus(Almacen(), EntregaFalsa(), Terminologia(), max_intentos=2, espera_base=0.01)
        bus.oyentes.append(aud.oyente_bus)

        # Enviar un mensaje válido y uno inválido
        hl7_valido = (
            "MSH|^~\\&|HIS|SEDE-1|HSB|IPS|20261107||ADT^A01|MSGTEST01|P|2.5\r\n"
            "PID|1||1007654321^^^CC||Perez^Juan||19850315|M\r\n"
            "PV1|1|E|IPS^^1||||MED-001^^Dr.|||01|||||||V|20261107"
        )
        bus.recibir_hl7(hl7_valido)
        bus.recibir_hl7("texto inválido que no es HL7")

        eventos = aud.listar()
        tipos = [e["que"] for e in eventos]
        self.assertIn("mensaje.entregado", tipos)
        self.assertIn("mensaje.rechazado", tipos)

        # La cadena debe seguir siendo íntegra tras múltiples eventos
        resultado = aud.verificar_cadena()
        self.assertTrue(resultado["ok"])


if __name__ == "__main__":
    unittest.main()
