#!/bin/bash
# 01-init-databases.sh — Datos de prueba propios del equipo.
# Crea las 3 bases de sede + tabla pacientes con fhir_patient_id NULL,
# simulando el incidente de interoperabilidad inicial (0% de cobertura).
# Incluye 5 pacientes por sede y 1 duplicado cross-sede (Juan Pérez Gómez
# en sede1 y sede2) para validar el MPI en la federación de identidad.
set -e

for DB in historia_clinica_sede1 historia_clinica_sede2 historia_clinica_sede3; do
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    SELECT 'CREATE DATABASE $DB' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$DB')\gexec
EOSQL

  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$DB" <<-EOSQL
    CREATE TABLE IF NOT EXISTS pacientes (
        id_paciente UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        documento_identidad VARCHAR(20) NOT NULL,
        tipo_documento VARCHAR(5) NOT NULL,
        nombre_completo VARCHAR(150) NOT NULL,
        fecha_nacimiento DATE NOT NULL,
        sexo CHAR(1) NOT NULL,
        fhir_patient_id VARCHAR(64)  -- NULL = pendiente de migrar (0% cobertura inicial)
    );

    INSERT INTO pacientes (documento_identidad, tipo_documento, nombre_completo, fecha_nacimiento, sexo) VALUES
      ('1007654321', 'CC', 'Juan Pérez Gómez',     '1985-03-15', 'M'),
      ('1007654322', 'CC', 'María López Ruiz',     '1990-07-22', 'F'),
      ('1007654323', 'CC', 'Carlos Ramírez Díaz',  '1978-11-03', 'M'),
      ('1007654324', 'CC', 'Ana Torres Meza',      '1995-01-30', 'F'),
      ('1007654325', 'CC', 'Luis Herrera Pineda',  '1982-09-14', 'M');
EOSQL
done

# ─────────────────────────────────────────────────────────────────
# Duplicado cross-sede: mismo documento en sede2 (simula paciente
# que se atiende en otra ciudad). El MPI debe detectarlo con score 1.0.
# ─────────────────────────────────────────────────────────────────
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "historia_clinica_sede2" <<-EOSQL
    INSERT INTO pacientes (documento_identidad, tipo_documento, nombre_completo, fecha_nacimiento, sexo) VALUES
      ('1007654321', 'CC', 'Juan Pérez Gómez', '1985-03-15', 'M');
EOSQL

# ─────────────────────────────────────────────────────────────────
# Datos exclusivos de sede3 (Corozal) — 5 pacientes propios.
# ─────────────────────────────────────────────────────────────────
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "historia_clinica_sede3" <<-EOSQL
    INSERT INTO pacientes (documento_identidad, tipo_documento, nombre_completo, fecha_nacimiento, sexo) VALUES
      ('55667788',   'CC', 'Pedro Martínez S.',  '1970-05-12', 'M'),
      ('55667789',   'CC', 'Rosa Mendoza Vega',  '1988-02-28', 'F'),
      ('55667790',   'CC', 'Diego Castro Luna',  '1992-08-09', 'M'),
      ('55667791',   'CC', 'Luisa Fernández R.', '1980-12-17', 'F'),
      ('55667792',   'CC', 'Andrés Ospino M.',   '1975-06-04', 'M');
EOSQL
