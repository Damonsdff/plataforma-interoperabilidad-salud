"""terminologia.py — ref_terminologia: diagnóstico local -> CIE-10 y prueba local -> LOINC (ConceptMap simple)."""
import csv
import os
import re

RUTA = os.path.join(os.path.dirname(__file__), "data")
CIE10_RE = re.compile(r"^[A-Z]\d{2}(\.\d{1,4})?$")
LOINC_RE = re.compile(r"^\d{1,5}-\d$")


def _leer(nombre):
    with open(os.path.join(RUTA, nombre), encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


class Terminologia:
    def __init__(self):
        self.cie10 = {r["dx_local"].upper(): (r["cie10"], r["descripcion"]) for r in _leer("ref_cie10.csv")}
        self.cie10_desc = {c: d for c, d in self.cie10.values()}
        self.loinc = {r["local"].upper(): (r["loinc"], r["descripcion"], r["ucum"]) for r in _leer("ref_loinc.csv")}

    def dx_a_cie10(self, texto):
        """('A09','Diarrea...') o None si el diagnóstico local no está en la tabla."""
        return self.cie10.get((texto or "").strip().upper())

    def prueba_a_loinc(self, texto):
        return self.loinc.get((texto or "").strip().upper())
