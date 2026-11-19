from django.core.management.base import BaseCommand, CommandError
from prospection.private_config import PrivateSettingsProtectionError, desktop_access_token, load_settings
from django.conf import settings


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--existing", action="store_true")

    def handle(self, *args, **options):
        # Captured by the launcher, never redirected to the server log.
        try:
            if options["existing"]:
                token = settings.OWNER_ACCESS_TOKEN or load_settings().get("desktop_access_token")
                if not token:
                    raise CommandError("Aucun jeton Windows existant. Les reglages ont ete preserves.")
            else:
                token = desktop_access_token()
        except PrivateSettingsProtectionError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(token)
