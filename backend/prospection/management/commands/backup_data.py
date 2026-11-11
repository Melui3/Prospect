from django.core.management.base import BaseCommand
from prospection.backups import create_backup


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--reason", default="startup")

    def handle(self, *args, **options):
        backup = create_backup(options["reason"])
        self.stdout.write(f"Sauvegarde creee : {backup['name']}")
