"""almacen.py — Persistencia del bus (SQLite en un volumen): mensaje_bus + eventos + terminología.

La idempotencia vive aquí (columna UNIQUE `clave`), no en memoria: sobrevive a reiniciar el bus.
"""
import json
import sqlite3
import threading
import time

ESQUEMA = """
CREATE TABLE IF NOT EXISTS mensaje_bus (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  clave TEXT UNIQUE NOT NULL,          -- MSH-10 (HL7) o hash del contenido (CSV)
  formato TEXT, tipo TEXT, sede INTEGER, documento TEXT,
  estado TEXT NOT NULL,                -- recibido|validado|transformado|entregado|rechazado|reintentando|muerto
  intentos INTEGER DEFAULT 0, motivo TEXT, error TEXT,
  payload TEXT, bundle TEXT, solicitud TEXT,
  recibido REAL, actualizado REAL, entregado REAL, latencia_ms REAL, proximo_intento REAL
);
CREATE TABLE IF NOT EXISTS evento_bus (
  id INTEGER PRIMARY KEY AUTOINCREMENT, id_mensaje INTEGER, ts REAL, estado TEXT, detalle TEXT
);
CREATE TABLE IF NOT EXISTS contador (nombre TEXT PRIMARY KEY, valor INTEGER DEFAULT 0);
"""


class Almacen:
    def __init__(self, ruta=":memory:"):
        self.con = sqlite3.connect(ruta, check_same_thread=False)
        self.con.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        with self.lock:
            self.con.executescript(ESQUEMA)

    def _q(self, sql, args=(), commit=True):
        with self.lock:
            cur = self.con.execute(sql, args)
            if commit:
                self.con.commit()
            return cur

    def crear(self, clave, formato, tipo, sede, documento, payload, ahora):
        """Inserta el mensaje. Devuelve (id, None) si es nuevo o (id_existente, fila) si la clave ya existía."""
        with self.lock:
            fila = self._q("SELECT * FROM mensaje_bus WHERE clave=?", (clave,), False).fetchone()
            if fila:
                return fila["id"], dict(fila)
            cur = self._q("INSERT INTO mensaje_bus (clave,formato,tipo,sede,documento,estado,payload,recibido,actualizado) "
                          "VALUES (?,?,?,?,?,?,?,?,?)", (clave, formato, tipo, sede, documento, "recibido", payload, ahora, ahora))
            self.evento(cur.lastrowid, "recibido", f"{formato} {tipo} sede {sede}", ahora)
            return cur.lastrowid, None

    def evento(self, id_, estado, detalle, ahora):
        self._q("INSERT INTO evento_bus (id_mensaje,ts,estado,detalle) VALUES (?,?,?,?)", (id_, ahora, estado, detalle))

    def actualizar(self, id_, ahora, detalle="", **campos):
        campos["actualizado"] = ahora
        cols = ", ".join(f"{k}=?" for k in campos)
        self._q(f"UPDATE mensaje_bus SET {cols} WHERE id=?", (*campos.values(), id_))
        if "estado" in campos:
            self.evento(id_, campos["estado"], detalle, ahora)

    def obtener(self, id_):
        f = self._q("SELECT * FROM mensaje_bus WHERE id=?", (id_,), False).fetchone()
        return dict(f) if f else None

    def pendientes(self, ahora):
        return [dict(f) for f in self._q("SELECT * FROM mensaje_bus WHERE estado='reintentando' AND proximo_intento<=? "
                                         "ORDER BY proximo_intento", (ahora,), False).fetchall()]

    def listar(self, estado=None, limite=100):
        sql = "SELECT id,clave,formato,tipo,sede,documento,estado,intentos,motivo,error,recibido,latencia_ms FROM mensaje_bus"
        args = ()
        if estado:
            sql += " WHERE estado=?"
            args = (estado,)
        return [dict(f) for f in self._q(sql + " ORDER BY id DESC LIMIT ?", (*args, limite), False).fetchall()]

    def eventos(self, id_):
        return [dict(f) for f in self._q("SELECT ts,estado,detalle FROM evento_bus WHERE id_mensaje=? ORDER BY id", (id_,), False)]

    def sumar(self, nombre, n=1):
        self._q("INSERT INTO contador (nombre,valor) VALUES (?,?) ON CONFLICT(nombre) DO UPDATE SET valor=valor+?", (nombre, n, n))

    def contador(self, nombre):
        f = self._q("SELECT valor FROM contador WHERE nombre=?", (nombre,), False).fetchone()
        return f["valor"] if f else 0

    def metricas(self, ahora):
        por_estado = {r["estado"]: r["n"] for r in self._q("SELECT estado, COUNT(*) n FROM mensaje_bus GROUP BY estado", (), False)}
        ult = self._q("SELECT COUNT(*) n FROM mensaje_bus WHERE recibido>=?", (ahora - 60,), False).fetchone()["n"]
        lat = self._q("SELECT AVG(latencia_ms) a, MAX(latencia_ms) m FROM mensaje_bus WHERE estado='entregado'", (), False).fetchone()
        por_sede = {r["sede"]: r["n"] for r in self._q("SELECT sede, COUNT(*) n FROM mensaje_bus WHERE estado='entregado' GROUP BY sede", (), False)}
        return por_estado, ult, lat["a"], lat["m"], por_sede
