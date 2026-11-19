import ctypes
import json
import os
import secrets
import threading
from ctypes import wintypes

from django.conf import settings
from email.utils import formataddr

settings_lock = threading.RLock()


class PrivateSettingsProtectionError(ValueError):
    pass


class Blob(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]


def protect(data, decrypt=False):
    if os.name != "nt":
        raise ValueError("Le stockage securise utilise le compte Windows de cette machine.")
    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    target = Blob()
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    if decrypt:
        crypt = crypt32.CryptUnprotectData
        crypt.argtypes = [
            ctypes.POINTER(Blob),
            ctypes.POINTER(wintypes.LPWSTR),
            ctypes.POINTER(Blob),
            ctypes.c_void_p,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(Blob),
        ]
    else:
        crypt = crypt32.CryptProtectData
        crypt.argtypes = [
            ctypes.POINTER(Blob),
            wintypes.LPCWSTR,
            ctypes.POINTER(Blob),
            ctypes.c_void_p,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(Blob),
        ]
    crypt.restype = wintypes.BOOL
    if not crypt(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        error_code = ctypes.get_last_error() & 0xFFFFFFFF
        operation = "dechiffrer" if decrypt else "chiffrer"
        raise PrivateSettingsProtectionError(
            f"DPAPI n'a pas pu {operation} les reglages proteges "
            f"(erreur Windows 0x{error_code:08X}). Le fichier reste inchange; "
            "verifiez le compte Windows et son profil d'origine."
        )
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        free = ctypes.windll.kernel32.LocalFree
        free.argtypes = [ctypes.c_void_p]
        free.restype = ctypes.c_void_p
        free(ctypes.cast(target.data, ctypes.c_void_p))


def load_settings():
    path = settings.BASE_DIR / "private-settings.bin"
    if path.exists():
        return json.loads(protect(path.read_bytes(), decrypt=True))
    return {}


def brevo_key():
    return load_settings().get("brevo_api_key", getattr(settings, "BREVO_API_KEY", ""))


def sender_address():
    saved = load_settings()
    if saved.get("sender_email"):
        return formataddr((saved.get("sender_name", ""), saved["sender_email"]))
    return settings.DEFAULT_FROM_EMAIL


def desktop_access_token():
    if not settings.DESKTOP_MODE:
        raise ValueError("Acces bureau uniquement.")
    if settings.OWNER_ACCESS_TOKEN:
        return settings.OWNER_ACCESS_TOKEN
    with settings_lock:
        data = load_settings()
        if not data.get("desktop_access_token"):
            data["desktop_access_token"] = secrets.token_urlsafe(48)
            save_private_settings(**data)
        return data["desktop_access_token"]


def save_private_settings(**values):
    if not settings.DESKTOP_MODE:
        raise ValueError("Ces reglages sont reserves a l'application locale.")
    with settings_lock:
        path = settings.BASE_DIR / "private-settings.bin"
        temp = path.with_suffix(".tmp")
        data = {**load_settings(), **values}
        temp.write_bytes(protect(json.dumps(data).encode()))
        temp.replace(path)


def save_brevo_key(key):
    save_private_settings(brevo_api_key=key)
