"""generar_bundle_document.py — Paso 6 del laboratorio: Composition/Bundle tipo document vía $document.
Se apoya en rda.py (usa un encuentro real con los campos de la Res. 866/2021).
Uso:  python generar_bundle_document.py [id_patient_fhir]"""
import runpy

if __name__ == "__main__":
    runpy.run_module("rda", run_name="__main__")
