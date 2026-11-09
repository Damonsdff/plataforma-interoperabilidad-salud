"""
seguridad.py — Autenticación JWT y control de acceso por rol.

Roles:
  paciente      → solo ve su propia historia (documento fijado en el token)
  admisionista  → puede buscar/registrar pacientes, NO ve diagnósticos/notas
  medico        → historia completa + registrar diagnóstico/egreso
  auditor       → solo lectura total + reporte de HC + auditoría

Uso en Flask:
    from seguridad import requiere_rol, generar_token
    @app.route("/ruta-protegida")
    @requiere_rol("medico", "auditor")
    def ruta():
        ...
"""
import hashlib
import hmac
import json
import os
import time
from base64 import urlsafe_b64decode, urlsafe_b64encode
from functools import wraps

from flask import g, jsonify, request

# Clave secreta: en producción viene de variable de entorno
JWT_SECRET = os.environ.get("JWT_SECRET", "clave-secreta-local-cambiar-en-produccion")
JWT_ALGORITMO = "HS256"
JWT_EXPIRACION_S = int(os.environ.get("JWT_EXPIRACION_S", 3600))  # 1 hora

# ─────────────────────────── usuarios de prueba ───────────────────────────
# En producción esto iría en Keycloak / base de datos
USUARIOS = {
    "admin_sincelejo": {"password": "kali", "rol": "admisionista", "sede": 1},
    "admin_cartagena": {"password": "kali", "rol": "admisionista", "sede": 2},
    "admin_corozal": {"password": "kali", "rol": "admisionista", "sede": 3},
    "medico_perez": {"password": "kali", "rol": "medico", "sede": None},
    "medico_garcia": {"password": "kali", "rol": "medico", "sede": None},
    "auditor": {"password": "kali", "rol": "auditor", "sede": None},
    "paciente_1007654321": {"password": "kali", "rol": "paciente", "documento": "1007654321"},
    "paciente_1007654322": {"password": "kali", "rol": "paciente", "documento": "1007654322"},
}

# ─────────────────────────── JWT mínimo (sin librería externa) ────────────
def _b64url(data: bytes) -> str:
    return urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_dec(s: str) -> bytes:
    pad = 4 - len(s) % 4
    return urlsafe_b64decode(s + "=" * pad)


def _firmar(header_b64: str, payload_b64: str) -> str:
    msg = f"{header_b64}.{payload_b64}".encode()
    sig = hmac.new(JWT_SECRET.encode(), msg, hashlib.sha256).digest()
    return _b64url(sig)


def generar_token(usuario: str, rol: str, **extra) -> str:
    """Genera un JWT firmado con HS256."""
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = {
        "sub": usuario, "rol": rol, "iat": int(time.time()),
        "exp": int(time.time()) + JWT_EXPIRACION_S, **extra,
    }
    payload_b64 = _b64url(json.dumps(payload).encode())
    firma = _firmar(header, payload_b64)
    return f"{header}.{payload_b64}.{firma}"


def verificar_token(token: str) -> dict:
    """
    Verifica firma y expiración. Devuelve el payload.
    Lanza ValueError si es inválido o expiró.
    """
    try:
        partes = token.split(".")
        if len(partes) != 3:
            raise ValueError("Formato JWT inválido")
        header_b64, payload_b64, firma_recibida = partes
        firma_esperada = _firmar(header_b64, payload_b64)
        if not hmac.compare_digest(firma_recibida, firma_esperada):
            raise ValueError("Firma JWT inválida")
        payload = json.loads(_b64url_dec(payload_b64))
        if payload.get("exp", 0) < time.time():
            raise ValueError("Token expirado")
        return payload
    except (KeyError, json.JSONDecodeError, Exception) as e:
        raise ValueError(f"Token inválido: {e}") from e


def _extraer_token() -> str | None:
    """Extrae el token del header Authorization o de la cookie 'token'."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return request.cookies.get("token")


def requiere_rol(*roles):
    """
    Decorador que protege una ruta Flask.
    Acepta el token en el header Authorization: Bearer <token>
    o en la cookie 'token'.
    """
    def decorador(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            token = _extraer_token()
            if not token:
                return jsonify({"error": "Se requiere autenticación", "codigo": "AUTH_MISSING"}), 401
            try:
                payload = verificar_token(token)
            except ValueError as e:
                return jsonify({"error": str(e), "codigo": "AUTH_INVALID"}), 401
            if roles and payload.get("rol") not in roles:
                return jsonify({
                    "error": f"Acceso denegado: se requiere rol {' o '.join(roles)}, tiene '{payload.get('rol')}'",
                    "codigo": "AUTH_FORBIDDEN",
                }), 403
            g.usuario = payload.get("sub")
            g.rol = payload.get("rol")
            g.payload_jwt = payload
            return f(*args, **kwargs)
        return wrapper
    return decorador


def usuario_actual() -> dict:
    """Devuelve {sub, rol, ...} del JWT del request actual (None si no hay sesión)."""
    token = _extraer_token()
    if not token:
        return {}
    try:
        return verificar_token(token)
    except ValueError:
        return {}
