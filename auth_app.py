"""
auth_app.py — Endpoints de autenticación para el parcial:
  POST /auth/login         → genera token JWT
  POST /auth/logout        → invalida cookie
  GET  /auth/me            → info del token actual
  GET  /auditoria          → lista eventos de auditoría (solo auditor/medico)
  GET  /auditoria/verificar → verifica integridad de la cadena (solo auditor)

Se registra como Blueprint y se monta en la vista unificada (app.py).
"""
import os
import sys
from flask import Blueprint, g, jsonify, make_response, request

# Permite importar desde la raíz del proyecto
RAIZ = os.path.dirname(os.path.abspath(__file__))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from auditoria import get_auditoria
from seguridad import USUARIOS, generar_token, requiere_rol, usuario_actual

bp_auth = Blueprint("auth", __name__)


# ─────────────────────────── LOGIN ────────────────────────────────────────
@bp_auth.post("/auth/login")
def login():
    datos = request.get_json(silent=True) or {}
    usuario = datos.get("usuario", "").strip()
    password = datos.get("password", "").strip()

    info = USUARIOS.get(usuario)
    if not info or info["password"] != password:
        get_auditoria().registrar(
            quien=usuario or "desconocido",
            que="auth.login",
            resultado="denegado",
            detalle="credenciales incorrectas",
        )
        return jsonify({"error": "Credenciales incorrectas"}), 401

    extra = {}
    if "sede" in info and info["sede"]:
        extra["sede"] = info["sede"]
    if "documento" in info:
        extra["documento"] = info["documento"]

    token = generar_token(usuario, info["rol"], **extra)

    get_auditoria().registrar(
        quien=usuario,
        que="auth.login",
        resultado="exito",
        detalle=f"rol={info['rol']}",
    )

    resp = make_response(jsonify({"token": token, "rol": info["rol"], "usuario": usuario}))
    # También devolvemos la cookie para el cliente web
    resp.set_cookie("token", token, httponly=True, samesite="Lax", max_age=3600)
    return resp


# ─────────────────────────── LOGOUT ───────────────────────────────────────
@bp_auth.post("/auth/logout")
def logout():
    payload = usuario_actual()
    if payload:
        get_auditoria().registrar(
            quien=payload.get("sub", "?"),
            que="auth.logout",
            resultado="exito",
        )
    resp = make_response(jsonify({"ok": True}))
    resp.delete_cookie("token")
    return resp


# ─────────────────────────── ME ───────────────────────────────────────────
@bp_auth.get("/auth/me")
def me():
    payload = usuario_actual()
    if not payload:
        return jsonify({"error": "No autenticado"}), 401
    return jsonify({k: v for k, v in payload.items() if k not in ("exp", "iat")})


# ─────────────────────────── AUDITORÍA ────────────────────────────────────
@bp_auth.get("/auditoria")
@requiere_rol("auditor", "medico")
def ver_auditoria():
    limite = int(request.args.get("limite", 100))
    eventos = get_auditoria().listar(limite)
    return jsonify({"total": len(eventos), "eventos": eventos})


@bp_auth.get("/auditoria/verificar")
@requiere_rol("auditor")
def verificar_auditoria():
    resultado = get_auditoria().verificar_cadena()
    get_auditoria().registrar(
        quien=g.usuario,
        que="auditoria.verificar",
        resultado="exito",
        detalle=f"total={resultado['total']} errores={len(resultado.get('errores', []))}",
    )
    return jsonify(resultado), (200 if resultado["ok"] else 409)


@bp_auth.get("/auditoria/<int:id_>")
@requiere_rol("auditor")
def ver_evento(id_):
    ev = get_auditoria().obtener(id_)
    if not ev:
        return jsonify({"error": "Evento no encontrado"}), 404
    return jsonify(ev)
