# Guía paso a paso (Kali Linux) — del cero a la entrega

Todo se ejecuta en la terminal de Kali. Después de cada paso, si algo falla, pega el mensaje de error en el chat.

## A. Instalar (una sola vez)
1. Descomprimir: `cd ~/Downloads && unzip lab5-parcial-FINAL.zip -d ~/Desktop && cd ~/Desktop/lab5-parcial-FINAL/lab5-starter-kit`
2. `bash scripts/instalar_kali.sh` (pide la contraseña de sudo; instala Docker, Python venv y PlantUML).
3. **Cerrar sesión y volver a entrar** (o reiniciar la máquina virtual) para que Docker te dé permisos.
4. Comprobar: `docker ps` (debe responder sin error) y `git log --oneline` (el repositorio ya viene listo).

## B. Levantar todo
1. `cd ~/Desktop/lab5-parcial-FINAL/lab5-starter-kit && bash scripts/iniciar_todo.sh` (la primera vez descarga imágenes: 5-10 min).
2. `bash scripts/ver_estado_bd.sh` → migrados = 0 en las 3 sedes. `bash scripts/ver_campos57.sh` → atenciones por sede.
3. Abrir http://localhost:5000.

## C. Pruebas (captura #9)
```bash
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -v
```

## D. Capturas (en este orden)
| # | Dónde | Qué capturar |
|---|---|---|
| 1 | /reportes | 0 % en las 3 sedes |
| 2 | /admision | formulario con los campos 1-24 y 51-57 |
| 3 | /admision | registrar `1007654321` en Corozal → aviso MPI |
| 4 | /admision | «Migrar pendientes» en cada sede (mensaje de éxito) |
| 5 | /reportes | 100 % en las 3 sedes + % de campos de la Res. 866 |
| 6 | /paciente?documento=1007654321 | historia unificada de 2-3 sedes |
| 7 | /medico?documento=1007654321 | formulario «Completar atención» (25-50) |
| 8 | /medico | enlace RDA abierto (Bundle type=document) |
| 9 | terminal | `pytest -v` en verde |
| 10 | terminal | `docker ps` |
| 11 | http://localhost:8080/fhir/Patient | recursos en HAPI |
| 12 | /matriz | matriz de los 57 campos |

Para tener el 0 % otra vez: `bash scripts/reiniciar_a_cero.sh`.
Para que el médico complete una atención nueva: registra primero un paciente en /admision (con atención) y luego búscalo en /medico.

## E. Informe
Abrir `docs/Informe_Parcial_Interoperabilidad.docx`: poner autores y correo, y reemplazar cada recuadro «[Figura N…]» por la captura de la tabla anterior.
La matriz Excel está en `docs/Matriz_Trazabilidad_57_Campos.xlsx` (ya completa; si una sede difiere, cambia su columna).

## F. Entrega
Al terminar: `bash scripts/detener_todo.sh`, comprimir la carpeta del proyecto (con `.git`) y subir informe + zip.
