"""entrega.py — Destinos del bus: HAPI FHIR (Bundle transaction) y la base de la sede (PostgreSQL).

Orden: primero HAPI, después la sede. Como el Bundle usa PUT y el upsert de la sede es por documento,
repetir la entrega completa tras un fallo no crea duplicados.
"""
import os

import requests

CAB = {"Content-Type": "application/fhir+json", "Accept": "application/fhir+json"}


class EntregaError(Exception):
    pass


class EntregaReal:
    def __init__(self, fhir_base=None, db_host=None, db_user=None, db_password=None):
        self.fhir = (fhir_base or os.environ.get("FHIR_BASE_URL", "http://hapi-fhir:8080/fhir")).rstrip("/")
        self.db_host = db_host or os.environ.get("DB_HOST", "pg_ips")
        self.db_user = db_user or os.environ.get("DB_USER", "ips_admin")
        self.db_password = db_password or os.environ.get("DB_PASSWORD", "")

    def a_hapi(self, bundle):
        try:
            r = requests.post(self.fhir, json=bundle, headers=CAB, timeout=15)
        except requests.RequestException as e:
            raise EntregaError(f"HAPI no disponible: {e.__class__.__name__}") from e
        if r.status_code not in (200, 201):
            raise EntregaError(f"HAPI respondió {r.status_code}: {r.text[:150]}")

    def _conectar(self, sede):
        import psycopg2
        return psycopg2.connect(host=self.db_host, dbname=f"historia_clinica_sede{sede}", user=self.db_user,
                                password=self.db_password, connect_timeout=4)

    def a_sede(self, sol, patient_id):
        """Upsert del paciente en la base legada de su sede y marca fhir_patient_id (sube la cobertura)."""
        try:
            con = self._conectar(sol["sede"])
        except Exception as e:
            raise EntregaError(f"Base de la sede {sol['sede']} no disponible: {e.__class__.__name__}") from e
        try:
            cur = con.cursor()
            nombre = sol.get("nombre_completo") or f"{sol['nombres']} {sol['apellido']}".strip()
            cur.execute("SELECT id_paciente FROM pacientes WHERE documento_identidad=%s", (sol["documento"],))
            if cur.fetchone():
                cur.execute("UPDATE pacientes SET fhir_patient_id=%s WHERE documento_identidad=%s", (patient_id, sol["documento"]))
            else:
                cur.execute("INSERT INTO pacientes (documento_identidad,tipo_documento,nombre_completo,fecha_nacimiento,sexo,fhir_patient_id) "
                            "VALUES (%s,%s,%s,%s,%s,%s)", (sol["documento"], sol["tipo_documento"], nombre, sol["nacimiento"], sol["sexo"], patient_id))
            con.commit()
        except Exception as e:
            con.rollback()
            raise EntregaError(f"Error escribiendo en la sede {sol['sede']}: {e}") from e
        finally:
            con.close()

    def entregar(self, sol, bundle, patient_id):
        self.a_hapi(bundle)
        self.a_sede(sol, patient_id)

    def salud(self):
        estado = {}
        try:
            estado["hapi"] = "ok" if requests.get(self.fhir + "/metadata", params={"_summary": "true"}, headers=CAB, timeout=3).ok else "caido"
        except requests.RequestException:
            estado["hapi"] = "caido"
        for s in (1, 2, 3):
            try:
                self._conectar(s).close()
                estado[f"sede{s}"] = "ok"
            except Exception:
                estado[f"sede{s}"] = "caido"
        return estado
