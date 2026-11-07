#!/bin/bash
# Usa "docker compose" (v2) o "docker-compose" (v1), lo que exista en la máquina
if docker compose version >/dev/null 2>&1; then docker compose "$@"; else docker-compose "$@"; fi
