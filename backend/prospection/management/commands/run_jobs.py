import logging
import sqlite3
import time
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import OperationalError, close_old_connections
from prospection.jobs import recover_jobs, run_next_job
from prospection.activity import worker_activity
from prospection.backups import automatic_backup

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")

    def handle(self, *args, **options):
        with worker_activity(".worker.lock") as acquired:
            if not acquired:
                self.stdout.write("Un worker est deja actif.")
                return
            self.run_worker(options)

    def run_worker(self, options):
        should_stop = options.get("stop_event")
        needs_recovery = True
        last_sync = 0
        last_backup = 0
        while should_stop is None or not should_stop.is_set():
            close_old_connections()
            with worker_activity() as idle:
                if idle:
                    if settings.DESKTOP_MODE and time.monotonic() - last_backup > 3600:
                        try:
                            automatic_backup()
                        except Exception:
                            logger.exception("Sauvegarde automatique impossible.")
                        last_backup = time.monotonic()
                    try:
                        if needs_recovery:
                            recover_jobs()
                            needs_recovery = False
                        run_next_job()
                    except OperationalError as exc:
                        code = getattr(exc.__cause__, "sqlite_errorcode", None)
                        if code is None or (code & 0xff) not in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
                            raise
                        logger.warning("Base SQLite occupee. Le worker reessaiera au prochain passage.")
                        needs_recovery = True
                        if options["once"]:
                            raise
                    else:
                        if time.monotonic() - last_sync > 300:
                            from prospection.mail import sync_delivery
                            try:
                                sync_delivery()
                            except Exception:
                                logger.warning("Synchronisation des emails indisponible.")
                            last_sync = time.monotonic()
            if options["once"]:
                return
            if should_stop is None:
                time.sleep(1)
            else:
                should_stop.wait(1)
