"""
auditoria.py — Cadena de auditoría encadenada por hash (Fase 4).

Cada evento de auditoría incluye:
  - quien: usuario/sistema que actúa
  - cuando: timestamp ISO
  - que: tipo de acción
  - resultado: exito | denegado | error
  - hash_anterior: SHA-256 del evento previo (cadena)
  - hash_propio: SHA-256 de este evento (incluye hash_anterior)

El registro se guarda en SQLite (misma DB del bus) o en un archivo JSON
de líneas (por defecto audit.jsonl) para facilitar la inspección.

Verificación:
    python auditoria.py verificar               # recorre toda la cadena
"""
import hashlib
import json
import os
import sqlite3
import threading
import time
from datetime import datetime, timezone

RUTA_AUDIT = os.environ.get("AUDIT_DB", "/data/auditoria.db")


class Auditoria:
    """Almacén de eventos de auditoría con cadena de hashes."""

    ESQUEMA = """
    CREATE TABLE IF NOT EXISTS evento_auditoria (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        ts          REAL    NOT NULL,
        quien       TEXT    NOT NULL,
        que         TEXT    NOT NULL,
        detalle     TEXT,
        resultado   TEXT    NOT NULL,
        hash_ant    TEXT,
        hash_propio TEXT    NOT NULL
    );
    """

    def __init__(self, ruta: str = ":memory:"):
        self.ruta = ruta
        self.con = sqlite3.connect(ruta, check_same_thread=False)
        self.con.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        with self.lock:
            self.con.executescript(self.ESQUEMA)

    # ── escritura ──────────────────────────────────────────────────────────
    def registrar(self, quien: str, que: str, resultado: str, detalle: str = "") -> dict:
        """
        Inserta un evento y devuelve el dict con su hash.
        Thread-safe gracias al lock.
        """
        ts = time.time()
        with self.lock:
            # Obtener el hash del último evento (cadena)
            prev = self.con.execute(
                "SELECT hash_propio FROM evento_auditoria ORDER BY id DESC LIMIT 1"
            ).fetchone()
            hash_ant = prev["hash_propio"] if prev else "GENESIS"

            # Construir el contenido canónico para hashear
            contenido = {
                "ts": ts, "quien": quien, "que": que,
                "detalle": detalle, "resultado": resultado,
                "hash_ant": hash_ant,
            }
            canon = json.dumps(contenido, sort_keys=True, ensure_ascii=False)
            hash_propio = hashlib.sha256(canon.encode()).hexdigest()

            self.con.execute(
                "INSERT INTO evento_auditoria (ts,quien,que,detalle,resultado,hash_ant,hash_propio) "
                "VALUES (?,?,?,?,?,?,?)",
                (ts, quien, que, detalle, resultado, hash_ant, hash_propio),
            )
            self.con.commit()
            return {**contenido, "hash_propio": hash_propio,
                    "iso": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()}

    # ── lectura ────────────────────────────────────────────────────────────
    def listar(self, limite: int = 100) -> list[dict]:
        with self.lock:
            rows = self.con.execute(
                "SELECT * FROM evento_auditoria ORDER BY id DESC LIMIT ?", (limite,)
            ).fetchall()
        return [dict(r) for r in rows]

    def obtener(self, id_: int) -> dict | None:
        with self.lock:
            r = self.con.execute(
                "SELECT * FROM evento_auditoria WHERE id=?", (id_,)
            ).fetchone()
        return dict(r) if r else None

    # ── verificación de la cadena ──────────────────────────────────────────
    def verificar_cadena(self) -> dict:
        """
        Recorre todos los eventos en orden y comprueba:
        1. Que el hash_propio de cada evento coincide con SHA-256(contenido).
        2. Que el hash_ant de cada evento es igual al hash_propio del anterior.

        Devuelve {"ok": True, "total": N} o {"ok": False, "errores": [...]}
        """
        with self.lock:
            rows = self.con.execute(
                "SELECT * FROM evento_auditoria ORDER BY id ASC"
            ).fetchall()

        errores = []
        hash_prev = "GENESIS"

        for row in rows:
            r = dict(row)
            # Reconstruir contenido canónico
            contenido = {
                "ts": r["ts"], "quien": r["quien"], "que": r["que"],
                "detalle": r["detalle"] or "", "resultado": r["resultado"],
                "hash_ant": r["hash_ant"],
            }
            canon = json.dumps(contenido, sort_keys=True, ensure_ascii=False)
            hash_calculado = hashlib.sha256(canon.encode()).hexdigest()

            if hash_calculado != r["hash_propio"]:
                errores.append({
                    "id": r["id"], "error": "hash_propio no coincide",
                    "calculado": hash_calculado, "almacenado": r["hash_propio"],
                })
            if r["hash_ant"] != hash_prev:
                errores.append({
                    "id": r["id"], "error": "hash_ant roto (cadena alterada)",
                    "esperado": hash_prev, "almacenado": r["hash_ant"],
                })
            hash_prev = r["hash_propio"]

        return {"ok": not errores, "total": len(rows), "errores": errores}

    # ── oyente para el Bus ─────────────────────────────────────────────────
    def oyente_bus(self, evento: dict):
        """
        Se engancha en Bus.oyentes para registrar automáticamente cada
        evento del HSB (recibido, rechazado, reintentando, entregado, muerto).
        """
        tipo = evento.get("tipo", "desconocido")
        id_msg = evento.get("id_mensaje", "?")
        detalle = json.dumps(
            {k: v for k, v in evento.items() if k not in ("tipo", "id_mensaje")},
            ensure_ascii=False,
        )
        resultado = "exito" if tipo == "entregado" else ("denegado" if tipo == "rechazado" else "info")
        self.registrar(
            quien="hsb",
            que=f"mensaje.{tipo}",
            resultado=resultado,
            detalle=f"msg_id={id_msg} {detalle}",
        )


# ── singleton (usado por la app Flask) ────────────────────────────────────
_instancia: Auditoria | None = None


def get_auditoria() -> Auditoria:
    global _instancia
    if _instancia is None:
        _instancia = Auditoria(RUTA_AUDIT)
    return _instancia


# ── CLI de verificación ────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    ruta = sys.argv[2] if len(sys.argv) > 2 else RUTA_AUDIT
    if len(sys.argv) < 2 or sys.argv[1] != "verificar":
        print("Uso: python auditoria.py verificar [ruta_db]")
        sys.exit(1)
    aud = Auditoria(ruta)
    res = aud.verificar_cadena()
    if res["ok"]:
        print(f"✅ Cadena íntegra — {res['total']} eventos verificados.")
    else:
        print(f"❌ CADENA ALTERADA — {len(res['errores'])} errores en {res['total']} eventos:")
        for e in res["errores"]:
            print(f"   ID={e['id']}: {e['error']}")
    sys.exit(0 if res["ok"] else 1)
