"""
campos57.py — Registro único de los 57 campos de la Historia Clínica Interoperable
(Resolución 866 de 2021, MinSalud), siguiendo la numeración y los dominios del
documento 57_CAMPOS_HC.md y del repositorio del docente (historia-clinica-distribuida).

Cada campo indica: en qué tabla/columna de las bases de sede se guarda, qué rol lo
captura en las vistas, y a qué recurso/elemento FHIR R4 se envía. A partir de esta
lista se generan la matriz de trazabilidad (docs/Matriz_Trazabilidad_57_Campos.xlsx),
la vista /matriz y las pruebas automáticas.
"""
from datetime import date

# n, grupo, nombre, tabla, columna, obligatorio, rol que lo captura, elemento FHIR, ejemplo
_C = [
    # ── 1. Identificación del usuario (15) ──────────────────────────────
    (1, "Identificación", "Tipo de documento de identidad", "pacientes", "tipo_documento", True, "Admisionista", "Patient.identifier.system / identifier.type", "CC"),
    (2, "Identificación", "Número de documento de identidad", "pacientes", "documento_identidad", True, "Admisionista", "Patient.identifier.value", "1234567890"),
    (3, "Identificación", "País de nacionalidad", "pacientes", "pais_nacionalidad", True, "Admisionista", "Patient.extension[patient-nationality]", "CO"),
    (4, "Identificación", "Nombre completo", "pacientes", "nombre_completo", True, "Admisionista", "Patient.name (family/given/text)", "Juan Pérez García"),
    (5, "Identificación", "Fecha de nacimiento", "pacientes", "fecha_nacimiento", True, "Admisionista", "Patient.birthDate", "1985-03-15"),
    (6, "Identificación", "Edad", "pacientes", "edad", True, "Admisionista (calculada)", "Patient.extension[edad] (Quantity)", "39"),
    (7, "Identificación", "Unidad de medida de edad", "pacientes", "unidad_edad", True, "Admisionista (calculada)", "Patient.extension[edad].unit (UCUM a/mo/d)", "1"),
    (8, "Identificación", "Sexo", "pacientes", "sexo", True, "Admisionista", "Patient.gender", "M"),
    (9, "Identificación", "Género", "pacientes", "genero", False, "Admisionista", "Patient.extension[patient-genderIdentity]", "Masculino"),
    (10, "Identificación", "Ocupación", "pacientes", "ocupacion", False, "Admisionista", "Patient.extension[ocupacion]", "Ingeniero"),
    (11, "Identificación", "Voluntad anticipada", "pacientes", "voluntad_anticipada", False, "Admisionista", "Patient.extension[voluntad-anticipada] (boolean)", "true"),
    (12, "Identificación", "Categoría de discapacidad", "pacientes", "categoria_discapacidad", False, "Admisionista", "Patient.extension[discapacidad]", "Ninguna"),
    (13, "Identificación", "País de residencia", "pacientes", "pais_residencia", True, "Admisionista", "Patient.address.country", "CO"),
    (14, "Identificación", "Municipio de residencia", "pacientes", "municipio_residencia", True, "Admisionista", "Patient.address.city + extensión DIVIPOLA/DANE", "11001"),
    (15, "Identificación", "Etnia", "pacientes", "etnia", False, "Admisionista", "Patient.extension[etnia]", "Otro"),
    # ── 2. Datos de la atención (9) ─────────────────────────────────────
    (16, "Atención", "Entidad de salud", "atenciones", "entidad_salud", True, "Admisionista", "Encounter.extension[entidad-salud]", "EPS Sanitas"),
    (17, "Atención", "Fecha y hora de ingreso", "atenciones", "fecha_ingreso", True, "Admisionista", "Encounter.period.start", "2026-02-14T10:30:00"),
    (18, "Atención", "Modalidad de entrega del servicio", "atenciones", "modalidad_entrega", True, "Admisionista", "Encounter.type[modalidad-entrega]", "01"),
    (19, "Atención", "Entorno de atención", "atenciones", "entorno_atencion", True, "Admisionista", "Encounter.class (v3-ActCode) + Encounter.type[entorno]", "01"),
    (20, "Atención", "Vía de ingreso", "atenciones", "via_ingreso", True, "Admisionista", "Encounter.hospitalization.admitSource", "01"),
    (21, "Atención", "Causa de la atención", "atenciones", "causa_atencion", True, "Admisionista", "Encounter.reasonCode.text", "Dolor abdominal agudo"),
    (22, "Atención", "Fecha y hora del triage", "atenciones", "fecha_triage", False, "Admisionista", "Encounter.extension[triage-fecha]", "2026-02-14T10:35:00"),
    (23, "Atención", "Clasificación del triage", "atenciones", "clasificacion_triage", False, "Admisionista", "Encounter.priority", "III"),
    (24, "Atención", "Comunidad étnica", "pacientes", "comunidad_etnica", False, "Admisionista", "Patient.extension[comunidad-etnica]", "Wayúu"),
    # ── 3. Tecnologías en salud (11) ────────────────────────────────────
    (25, "Tecnologías en salud", "Descripción del medicamento", "tecnologia_salud", "descripcion_medicamento", False, "Médico", "MedicationRequest.medicationCodeableConcept.text", "Acetaminofén 500mg"),
    (26, "Tecnologías en salud", "Dosis", "tecnologia_salud", "dosis", False, "Médico", "MedicationRequest.dosageInstruction.doseAndRate.doseQuantity", "500mg"),
    (27, "Tecnologías en salud", "Vía de administración", "tecnologia_salud", "via_administracion", False, "Médico", "MedicationRequest.dosageInstruction.route", "01"),
    (28, "Tecnologías en salud", "Frecuencia", "tecnologia_salud", "frecuencia", False, "Médico", "MedicationRequest.dosageInstruction.timing", "Cada 8 horas"),
    (29, "Tecnologías en salud", "Días de tratamiento", "tecnologia_salud", "dias_tratamiento", False, "Médico", "MedicationRequest.dispenseRequest.expectedSupplyDuration", "5"),
    (30, "Tecnologías en salud", "Unidades aplicadas", "tecnologia_salud", "unidades_aplicadas", False, "Médico", "MedicationRequest.dispenseRequest.quantity", "15"),
    (31, "Tecnologías en salud", "Identificación del personal de salud", "tecnologia_salud", "id_personal_salud", False, "Médico", "MedicationRequest.requester → Practitioner.identifier", "98765432"),
    (32, "Tecnologías en salud", "Finalidad de la tecnología", "tecnologia_salud", "finalidad_tecnologia", False, "Médico", "MedicationRequest.reasonCode", "01"),
    (33, "Tecnologías en salud", "Tipo de diagnóstico de ingreso", "diagnostico", "tipo_dx_ingreso", False, "Médico", "Condition.extension[tipo-diagnostico] (ingreso)", "01"),
    (34, "Tecnologías en salud", "Diagnóstico de ingreso (CIE-10)", "diagnostico", "dx_ingreso", False, "Médico", "Condition.code + Encounter.diagnosis (rol AD)", "J00"),
    (35, "Tecnologías en salud", "Tipo de diagnóstico de egreso", "diagnostico", "tipo_dx_egreso", False, "Médico", "Condition.extension[tipo-diagnostico] (egreso)", "01"),
    # ── 4. Diagnósticos (4) ─────────────────────────────────────────────
    (36, "Diagnósticos", "Diagnóstico de egreso (CIE-10)", "diagnostico", "dx_egreso", True, "Médico", "Condition.code + Encounter.diagnosis (rol DD)", "J18.9"),
    (37, "Diagnósticos", "Diagnóstico relacionado 1", "diagnostico", "dx_rel1", False, "Médico", "Condition.code + Encounter.diagnosis (rol CM)", "I10"),
    (38, "Diagnósticos", "Diagnóstico relacionado 2", "diagnostico", "dx_rel2", False, "Médico", "Condition.code + Encounter.diagnosis (rol CM)", "E11.9"),
    (39, "Diagnósticos", "Diagnóstico relacionado 3", "diagnostico", "dx_rel3", False, "Médico", "Condition.code + Encounter.diagnosis (rol CM)", "K29.7"),
    # ── 5. Datos de egreso (18) ─────────────────────────────────────────
    (40, "Egreso", "Fecha y hora de salida", "egreso", "fecha_salida", True, "Médico", "Encounter.period.end", "2026-02-14T14:30:00"),
    (41, "Egreso", "Condición de salida", "egreso", "condicion_salida", True, "Médico", "Encounter.hospitalization.dischargeDisposition", "01"),
    (42, "Egreso", "Diagnóstico de muerte", "egreso", "dx_muerte", False, "Médico", "Condition (categoría causa de muerte)", "I21.9"),
    (43, "Egreso", "Código del prestador", "egreso", "codigo_prestador", True, "Médico", "Organization.identifier → Encounter.serviceProvider", "110010001234"),
    (44, "Egreso", "Tipo de incapacidad", "egreso", "tipo_incapacidad", False, "Médico", "Encounter.extension[incapacidad-tipo]", "01"),
    (45, "Egreso", "Días de incapacidad", "egreso", "dias_incapacidad", False, "Médico", "Encounter.extension[incapacidad-dias]", "3"),
    (46, "Egreso", "Días de licencia de maternidad", "egreso", "dias_lic_maternidad", False, "Médico", "Encounter.extension[licencia-maternidad-dias]", "0"),
    (47, "Egreso", "Alergias", "egreso", "alergias", False, "Médico", "AllergyIntolerance.code.text", "Penicilina, Mariscos"),
    (48, "Egreso", "Antecedentes familiares", "egreso", "antecedente_familiar", False, "Médico", "FamilyMemberHistory.condition.code.text", "Padre: HTA, Madre: DM2"),
    (49, "Egreso", "Riesgos ocupacionales", "egreso", "riesgos_ocupacionales", False, "Médico", "Observation (riesgos ocupacionales).valueString", "Ruido, Polvo"),
    (50, "Egreso", "Responsable del egreso", "egreso", "responsable_egreso", True, "Médico", "Encounter.participant.individual → Practitioner.name", "Dr. Carlos Rodríguez"),
    (51, "Egreso", "Zona de residencia", "pacientes", "zona_residencia", True, "Admisionista", "Patient.address.extension[zona-residencia]", "01"),
    (52, "Egreso", "Dirección de residencia", "pacientes", "direccion_residencia", True, "Admisionista", "Patient.address.line / text", "Calle 123 #45-67"),
    (53, "Egreso", "Teléfono", "pacientes", "telefono", False, "Admisionista", "Patient.telecom (phone)", "3001234567"),
    (54, "Egreso", "Correo electrónico", "pacientes", "correo", False, "Admisionista", "Patient.telecom (email)", "juan@example.com"),
    (55, "Egreso", "Nombre del responsable", "pacientes", "nombre_responsable", False, "Admisionista", "Patient.contact.name.text", "María Pérez"),
    (56, "Egreso", "Parentesco del responsable", "pacientes", "parentesco_responsable", False, "Admisionista", "Patient.contact.relationship", "03"),
    (57, "Egreso", "Teléfono del responsable", "pacientes", "telefono_responsable", False, "Admisionista", "Patient.contact.telecom (phone)", "3009876543"),
]

CLAVES = ("n", "grupo", "nombre", "tabla", "columna", "obligatorio", "rol", "fhir", "ejemplo")
CAMPOS = [dict(zip(CLAVES, fila)) for fila in _C]

# ── Dominios (valores permitidos según 57_CAMPOS_HC.md) ───────────────────────
CATALOGOS = {
    "tipo_documento": [("CC", "Cédula de ciudadanía"), ("TI", "Tarjeta de identidad"), ("CE", "Cédula de extranjería"),
                       ("PA", "Pasaporte"), ("RC", "Registro civil"), ("MS", "Menor sin identificación"),
                       ("AS", "Adulto sin identificación")],
    "sexo": [("M", "Masculino"), ("F", "Femenino"), ("I", "Indeterminado")],
    "genero": [("Masculino", "Masculino"), ("Femenino", "Femenino"), ("Otro", "Otro")],
    "unidad_edad": [("1", "Años"), ("2", "Meses"), ("3", "Días")],
    "categoria_discapacidad": [("Ninguna", "Ninguna"), ("Física", "Física"), ("Mental", "Mental"),
                               ("Sensorial", "Sensorial"), ("Múltiple", "Múltiple")],
    "etnia": [("Ninguna", "Ninguna"), ("Indígena", "Indígena"), ("ROM", "ROM"), ("Raizal", "Raizal"),
              ("Palenquero", "Palenquero"), ("Negro", "Negro / afrocolombiano"), ("Otro", "Otro")],
    "pais": [("CO", "Colombia"), ("VE", "Venezuela"), ("EC", "Ecuador"), ("PE", "Perú"), ("US", "Estados Unidos"),
             ("ES", "España"), ("OT", "Otro")],
    "municipio_residencia": [("70001", "Sincelejo"), ("13001", "Cartagena"), ("70215", "Corozal"), ("11001", "Bogotá D.C."),
                             ("05001", "Medellín"), ("76001", "Cali"), ("08001", "Barranquilla"),
                             ("23001", "Montería"), ("47001", "Santa Marta")],
    "zona_residencia": [("01", "Urbana"), ("02", "Rural")],
    "parentesco_responsable": [("01", "Padre/Madre"), ("02", "Hijo/Hija"), ("03", "Esposo/Esposa"), ("04", "Hermano/Hermana"),
                               ("05", "Abuelo/Abuela"), ("06", "Tío/Tía"), ("07", "Otro")],
    "modalidad_entrega": [("01", "Intramural"), ("02", "Extramural"), ("03", "Telemedicina interactiva"),
                          ("04", "Telemedicina no interactiva"), ("05", "Telexperticia"), ("06", "Telemonitoreo")],
    "entorno_atencion": [("01", "Urgencias"), ("02", "Consulta externa"), ("03", "Hospitalización"), ("04", "Cirugía"),
                         ("05", "Apoyo diagnóstico"), ("06", "Apoyo terapéutico")],
    "via_ingreso": [("01", "Espontánea"), ("02", "Remitido"), ("03", "Contraremitido")],
    "clasificacion_triage": [("I", "I - Resucitación (inmediato)"), ("II", "II - Emergencia (15 min)"),
                             ("III", "III - Urgente (30 min)"), ("IV", "IV - Menos urgente (60 min)"),
                             ("V", "V - No urgente (120 min)")],
    "via_administracion": [("01", "Oral"), ("02", "Intravenosa"), ("03", "Intramuscular"), ("04", "Subcutánea"),
                           ("05", "Tópica"), ("06", "Inhalatoria"), ("07", "Rectal"), ("08", "Oftálmica"),
                           ("09", "Ótica"), ("10", "Nasal")],
    "finalidad_tecnologia": [("01", "Terapéutica"), ("02", "Diagnóstica"), ("03", "Paliativa"), ("04", "Preventiva"),
                             ("05", "Rehabilitación")],
    "tipo_diagnostico": [("01", "Principal"), ("02", "Relacionado"), ("03", "Complicación")],
    "condicion_salida": [("01", "Vivo"), ("02", "Muerto")],
    "tipo_incapacidad": [("01", "Temporal"), ("02", "Permanente parcial"), ("03", "Permanente total")],
}

CIE10 = {
    "J00": "Rinofaringitis aguda (resfriado común)", "J18.9": "Neumonía, no especificada",
    "I10": "Hipertensión esencial (primaria)", "E11.9": "Diabetes mellitus tipo 2 sin complicaciones",
    "K29.7": "Gastritis, no especificada", "M54.5": "Dolor lumbar",
    "A09": "Diarrea y gastroenteritis de presunto origen infeccioso", "J45.9": "Asma, no especificada",
    "E66.9": "Obesidad, no especificada", "J06.9": "Infección aguda de vías respiratorias superiores",
    "I21.9": "Infarto agudo de miocardio, sin otra especificación",
}


def nombre_catalogo(catalogo: str, codigo):
    """Devuelve la descripción de un código (o el mismo código si no está)."""
    for c, d in CATALOGOS.get(catalogo, []):
        if str(c) == str(codigo):
            return d
    return str(codigo) if codigo is not None else ""


def por_tabla(tabla: str):
    return [c for c in CAMPOS if c["tabla"] == tabla]


def columnas(tabla: str):
    return [c["columna"] for c in por_tabla(tabla)]


def calcular_edad(nacimiento: date, hoy: date | None = None):
    """Devuelve (edad, unidad) con unidad 1=años, 2=meses, 3=días (campos 6 y 7)."""
    hoy = hoy or date.today()
    años = hoy.year - nacimiento.year - ((hoy.month, hoy.day) < (nacimiento.month, nacimiento.day))
    if años >= 1:
        return años, "1"
    meses = (hoy.year - nacimiento.year) * 12 + hoy.month - nacimiento.month - (hoy.day < nacimiento.day)
    if meses >= 1:
        return meses, "2"
    return max((hoy - nacimiento).days, 0), "3"
