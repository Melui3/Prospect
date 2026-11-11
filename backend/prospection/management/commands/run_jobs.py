import logging
import time
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import close_old_connections
from prospection.jobs import recover_jobs, run_next_job
from prospection.activity import worker_activity
from prospection.backups import automatic_backup


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
        with worker_activity() as idle:
            if not idle:
                self.stdout.write("Maintenance en cours. Relance le worker apres la restauration.")
                return
            recover_jobs()
        last_sync = 0
        last_backup = 0
        while True:
            close_old_connections()
            with worker_activity() as idle:
                if idle:
                    if settings.DESKTOP_MODE and time.monotonic() - last_backup > 3600:
                        try:
                            automatic_backup()
                        except Exception:
                            logging.getLogger(__name__).exception("Sauvegarde automatique impossible.")
                        last_backup = time.monotonic()
                    run_next_job()
                    if time.monotonic() - last_sync > 300:
                        from prospection.mail import sync_delivery
                        try:
                            sync_delivery()
                        except Exception:
                            logging.getLogger(__name__).warning("Synchronisation des emails indisponible.")
                        last_sync = time.monotonic()
            if options["once"]:
                return
            time.sleep(1)
