"""
Autenticación (registro/login) — puerto directo de la celda 20 del
notebook. Sigue usando PBKDF2-SHA256 + salt, y MongoDB en vez de SQLite.
En la versión unificada no hay JWT/cookies de servidor: el "estar
logueado" se guarda en st.session_state (equivalente a localStorage en
las páginas HTML originales), vive mientras dure la sesión del navegador.
"""
import hashlib
import os
from datetime import datetime, timezone
from typing import Optional

from core.db import get_collections

PERFILES_VALIDOS = ("conservador", "moderado", "agresivo")


def _hash_password(password: str, salt: Optional[str] = None):
    if salt is None:
        salt = os.urandom(16).hex()
    hash_hex = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 200_000).hex()
    return hash_hex, salt


def registrar_usuario(nombre: str, email: str, password: str, perfil: str) -> tuple[bool, str]:
    if perfil not in PERFILES_VALIDOS:
        return False, "Perfil de riesgo inválido."
    if len(password) < 8:
        return False, "La contraseña debe tener al menos 8 caracteres."
    if not nombre.strip():
        return False, "El nombre es obligatorio."

    col_usuarios, _, _ = get_collections()
    email = email.strip().lower()

    if col_usuarios.find_one({"email": email}):
        return False, "Ya existe una cuenta con ese correo."

    hash_hex, salt = _hash_password(password)
    col_usuarios.insert_one({
        "email": email,
        "nombre": nombre,
        "perfil": perfil,
        "password_hash": hash_hex,
        "salt": salt,
        "creado_en": datetime.now(timezone.utc).isoformat(),
    })
    return True, f"Cuenta creada para {nombre}. Ya puedes iniciar sesión."


def login_usuario(email: str, password: str) -> tuple[bool, str, Optional[dict]]:
    col_usuarios, _, _ = get_collections()
    email = email.strip().lower()

    usuario = col_usuarios.find_one({"email": email})
    if not usuario:
        return False, "Correo o contraseña incorrectos.", None

    hash_calculado, _ = _hash_password(password, usuario["salt"])
    if hash_calculado != usuario["password_hash"]:
        return False, "Correo o contraseña incorrectos.", None

    datos = {"nombre": usuario["nombre"], "perfil": usuario["perfil"], "email": email}
    return True, "Bienvenido.", datos
