#!/bin/bash
# Instala lo necesario en Kali Linux (ejecutar UNA vez, desde la carpeta del proyecto)
set -e
sudo apt update
sudo apt install -y docker.io python3-venv python3-pip git unzip curl plantuml
sudo apt install -y docker-compose-v2 || sudo apt install -y docker-compose
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
echo
echo "Instalación lista. CIERRA SESIÓN Y VUELVE A ENTRAR (o reinicia la máquina virtual)"
echo "para que el permiso de docker se active. Luego: bash scripts/iniciar_todo.sh"
