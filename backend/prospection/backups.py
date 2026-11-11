import hashlib
import re
import sqlite3
import threading
import uuid
from contextlib import closing
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.db import connection, connections
from django.utils import timezone

backup_lock = threading.RLock()
restoring = False


def backup_directory():
    directory = Path(getattr(settings, "BACKUP_DIR", settings.BASE_DIR / "backups"))
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def validate_backup(path):
    with closing(sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)) as db:
        if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("Sauvegarde endommagee.")
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {"django_migrations", "prospection_prospect", "prospection_campaign"}.issubset(tables):
            raise ValueError("Ce fichier n'est pas une base Prospect.")


def create_backup(reason="manual"):
    if connection.vendor != "sqlite":
        raise ValueError("Les sauvegardes bureau necessitent la base locale.")
    with backup_lock:
        directory = backup_directory()
        reason = re.sub(r"[^a-z-]", "", reason.lower())[:30] or "manual"
        name = f"prospect-{timezone.now():%Y%m%d-%H%M%S}-{reason}-{uuid.uuid4().hex[:8]}.sqlite3"
        path = directory / name
        connection.ensure_connection()
        with closing(sqlite3.connect(str(path))) as destination:
            connection.connection.backup(destination)
        validate_backup(path)
        return backup_metadata(path)


def backup_metadata(path):
    return {"name": path.name, "size": path.stat().st_size,
            "created_at": timezone.datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.get_current_timezone()).isoformat(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def list_backups():
    return [backup_metadata(path) for path in sorted(backup_directory().glob("prospect-*.sqlite3"), reverse=True)]


def automatic_backup():
    directory = backup_directory()
    today = timezone.now().strftime("%Y%m%d")
    if list(directory.glob(f"prospect-{today}-*-auto-*.sqlite3")):
        return
    result = create_backup("auto")
    automatic = sorted(directory.glob("prospect-*-auto-*.sqlite3"), reverse=True)
    for path in automatic[14:]:
        path.unlink()
    return result


def restore_backup(name):
    from .activity import worker_activity
    with worker_activity() as idle:
        if not idle:
            raise ValueError("Une tache termine son operation. Mets-la en pause puis reessaie dans un instant.")
        return _restore_backup(name)


def _restore_backup(name):
    global restoring
    from .models import Campaign, SearchJob
    if not re.fullmatch(r"prospect-[a-z0-9-]+\.sqlite3", name or ""):
        raise ValueError("Nom de sauvegarde invalide.")
    path = backup_directory() / name
    if not path.is_file():
        raise ValueError("Sauvegarde introuvable.")
    validate_backup(path)
    if SearchJob.objects.filter(status__in=["running", "queued"]).exists():
        raise ValueError("Mets les recherches en pause avant de restaurer.")
    with backup_lock:
        recovery = create_backup("before-restore")
        restoring = True
        try:
            connections.close_all()
            database_path = settings.DATABASES["default"]["NAME"]
            with closing(sqlite3.connect(str(path))) as source, closing(sqlite3.connect(str(database_path))) as destination:
                source.backup(destination)
            call_command("migrate", interactive=False, verbosity=0)
            SearchJob.objects.filter(status__in=["running", "queued"]).update(status="paused", stage="A reprendre apres restauration")
            Campaign.objects.filter(status__in=["running", "queued"]).update(status="paused")
        except Exception:
            with closing(sqlite3.connect(str(backup_directory() / recovery["name"]))) as source, closing(sqlite3.connect(str(database_path))) as destination:
                source.backup(destination)
            raise
        finally:
            connections.close_all()
            restoring = False
        return {"restored": name, "recovery": recovery["name"]}
