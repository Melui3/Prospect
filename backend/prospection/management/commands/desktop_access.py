from django.core.management.base import BaseCommand
from prospection.private_config import desktop_access_token


class Command(BaseCommand):
    def handle(self, *args, **options):
        # Captured by the launcher, never redirected to the server log.
        self.stdout.write(desktop_access_token())
