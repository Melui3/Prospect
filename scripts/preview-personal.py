"""Isolated UI fixture. No real contacts, credentials or email delivery."""
import argparse
import os
import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
os.environ["DATABASE_URL"] = ""
os.environ["DESKTOP_MODE"] = "True"
os.environ["DEBUG"] = "False"

import django
from django.conf import settings

directory = ROOT / "backend" / ".qa"
directory.mkdir(exist_ok=True)
settings.DATABASES["default"]["NAME"] = directory / "prospect.sqlite3"
settings.BASE_DIR = directory
settings.BACKUP_DIR = directory / "backups"
settings.SERVE_FRONTEND = True
settings.FRONTEND_DIST_DIR = ROOT / "backend" / "desktop_static"
settings.OWNER_ACCESS_TOKEN = ""
settings.REQUIRE_OWNER_TOKEN = False
settings.DESKTOP_AUTO_AUTH = False
settings.DEMO_MODE = False
settings.ALLOWED_HOSTS = ["127.0.0.1", "localhost"]
settings.BREVO_API_KEY = ""
settings.EMAIL_HOST_USER = ""
settings.DEFAULT_FROM_EMAIL = "Prospect QA <qa@sender.example>"
settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
django.setup()

from django.core.management import call_command
from django.utils import timezone
from prospection.identity import capture_prospect
from prospection.models import Campaign, EmailLog


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8767)
    args = parser.parse_args()
    call_command("migrate", interactive=False, verbosity=0)
    if not Campaign.objects.exists():
        campaign = Campaign.objects.create(secteur="restaurant", ville="Rennes", rayon_km=8, status="done")
        for number in range(85):
            item = capture_prospect(campaign, {"type": "node", "id": number, "tags": {
                "name": "Atelier QA" if number == 0 else f"Entreprise fictive {number:03}",
                "addr:city": "Rennes", "addr:street": f"{number} Rue Exemple",
                "email": f"contact{number}@entreprise.example" if number % 3 == 0 else "",
                "website": "https://entreprise.example" if number % 2 == 0 else "",
            }})
            if number == 0:
                item.notes = "Projet de site, a rappeler en debut de semaine."
                item.priority = "high"
                item.status = "interested"
                item.next_followup_at = timezone.now() - timedelta(days=1)
                item.save()
                EmailLog.objects.create(prospect=item, subject="Premier contact QA", body="Bonjour, ceci est un historique fictif.", recipient=item.email, source="manual", delivery_status="manual")
    call_command("runserver", f"127.0.0.1:{args.port}", use_reloader=False)


if __name__ == "__main__":
    main()
