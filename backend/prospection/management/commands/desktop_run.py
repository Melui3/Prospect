import socket
import sys
from threading import Event, Thread

from django.conf import settings
from django.core.management import BaseCommand, CommandError, call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.core.servers.basehttp import (
    ThreadedWSGIServer,
    WSGIRequestHandler,
    get_internal_wsgi_application,
)

from .run_jobs import Command as WorkerCommand


class DesktopServer(ThreadedWSGIServer):
    daemon_threads = False

    def server_bind(self):
        if sys.platform == "win32":
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class DesktopRequestHandler(WSGIRequestHandler):
    timeout = 5

    def handle(self):
        try:
            super().handle()
        except TimeoutError:
            self.close_connection = True


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("port", type=int)

    def handle(self, *args, **options):
        if not settings.DESKTOP_MODE or settings.DATABASES["default"]["ENGINE"] != "django.db.backends.sqlite3":
            raise CommandError("Le serveur bureau requiert la base SQLite locale.")
        self.check()
        with DesktopServer(
            ("127.0.0.1", options["port"]), DesktopRequestHandler, allow_reuse_address=False
        ) as server:
            # Reserve the port before touching the database or starting the worker.
            migrations = MigrationExecutor(connection)
            if migrations.migration_plan(migrations.loader.graph.leaf_nodes()):
                if migrations.loader.applied_migrations:
                    call_command("backup_data", reason="before-upgrade")
                call_command("migrate", interactive=False)

            server.set_app(get_internal_wsgi_application())
            server.timeout = 0.25
            stop = Event()
            worker = Thread(target=WorkerCommand().handle, kwargs={"stop_event": stop, "once": False})
            worker.start()
            # Closing the launcher's pipe also shuts down the service if the launcher exits.
            Thread(target=self.wait_for_stop, args=(stop,), daemon=True).start()
            try:
                while worker.is_alive() and not stop.is_set():
                    server.handle_request()
                if not stop.is_set():
                    raise CommandError("Le worker Prospect s'est arrete. Consulte le journal local.")
            finally:
                stop.set()
                worker.join()

    @staticmethod
    def wait_for_stop(stop):
        sys.stdin.readline()
        stop.set()
