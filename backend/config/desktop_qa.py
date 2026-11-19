"""Empty, isolated database and in-memory email for the Windows launcher test."""
import os
from pathlib import Path

from .settings import *  # noqa: F403

BASE_DIR = Path(os.environ["PROSPECT_DESKTOP_QA"])
DATABASES["default"]["NAME"] = BASE_DIR / "launcher.sqlite3"  # noqa: F405
BACKUP_DIR = BASE_DIR / "backups"
OWNER_ACCESS_TOKEN = "local-launcher-qa"
BREVO_API_KEY = ""
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
