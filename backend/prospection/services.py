"""
Services métier :
  - scraping OSM (Overpass) + enrichissement Pages Jaunes
  - envoi d'emails
"""

import time
import logging

import requests
from bs4 import BeautifulSoup
from django.core.mail import send_mail
from django.utils import timezone

logger = logging.getLogger(__name__)

# ── Tags OSM connus ────────────────────────────────────────────
OSM_TAGS = {
    "boulangerie": '"shop"="bakery"',
    "restaurant": '"amenity"="restaurant"',
    "coiffeur": '"shop"="hairdresser"',
    "pharmacie": '"amenity"="pharmacy"',
    "plombier": '"craft"="plumber"',
    "electricien": '"craft"="electrician"',
    "garage": '"shop"="car_repair"',
    "fleuriste": '"shop"="florist"',
    "epicerie": '"shop"="convenience"',
    "opticien": '"shop"="optician"',
    "dentiste": '"amenity"="dentist"',
    "veterinaire": '"amenity"="veterinary"',
    "avocat": '"office"="lawyer"',
    "comptable": '"office"="accountant"',
    "architecte": '"office"="architect"',
}


def _get_city_coords(ville: str) -> tuple[str, str] | None:
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": ville, "format": "json", "limit": 1},
            headers={"User-Agent": "prospect-app/1.0"},
            timeout=10,
        )
        data = resp.json()
        if not data:
            return None
        return data[0]["lat"], data[0]["lon"]
    except Exception as exc:
        logger.error("Nominatim error: %s", exc)
        return None


def _query_overpass(tag: str, lat: str, lon: str, rayon_m: int) -> list[dict]:
    query = f"""
    [out:json][timeout:30];
    node[{tag}](around:{rayon_m},{lat},{lon});
    out body;
    """
    try:
        resp = requests.get(
            "https://overpass-api.de/api/interpreter",
            params={"data": query},
            timeout=40,
        )
        return resp.json().get("elements", [])
    except Exception as exc:
        logger.error("Overpass error: %s", exc)
        return []


def _find_email_pages_jaunes(nom: str, ville: str) -> str | None:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        )
    }
    url = (
        f"https://www.pagesjaunes.fr/pagesblanches/recherche"
        f"?quoiqui={requests.utils.quote(nom)}&ou={requests.utils.quote(ville)}"
    )
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        for link in soup.find_all("a", href=True):
            if "mailto:" in link["href"]:
                return link["href"].replace("mailto:", "").strip()
    except Exception as exc:
        logger.warning("Pages Jaunes error for %s: %s", nom, exc)
    return None


# ── Prospection principale ─────────────────────────────────────

def run_prospection(campaign) -> dict:
    """
    Scrape OSM + enrichit via Pages Jaunes, enregistre les Prospect en base.
    Retourne un dict de stats.
    """
    from .models import Prospect  # import local pour éviter les imports circulaires

    tag = OSM_TAGS.get(campaign.secteur.lower(), f'"shop"="{campaign.secteur}"')
    coords = _get_city_coords(campaign.ville)

    if not coords:
        raise ValueError(f"Ville introuvable : {campaign.ville}")

    lat, lon = coords
    rayon_m = campaign.rayon_km * 1000
    elements = _query_overpass(tag, lat, lon, rayon_m)

    created_total = 0
    created_with_email = 0

    for element in elements:
        tags = element.get("tags", {})
        nom = tags.get("name", "").strip()
        if not nom:
            continue

        website = tags.get("website") or tags.get("contact:website") or None
        email = tags.get("email") or tags.get("contact:email") or None

        # On ne garde que ceux sans site (nos vrais prospects)
        if website:
            continue

        # Enrichissement Pages Jaunes si pas d'email
        if not email:
            email = _find_email_pages_jaunes(nom, campaign.ville)
            time.sleep(0.4)  # politesse serveur

        prospect, _ = Prospect.objects.get_or_create(
            campaign=campaign,
            nom=nom,
            defaults={
                "adresse": tags.get("addr:street", ""),
                "ville": tags.get("addr:city", campaign.ville),
                "telephone": tags.get("phone") or tags.get("contact:phone") or "",
                "email": email or None,
                "website": None,
                "has_website": False,
            },
        )
        created_total += 1
        if prospect.email:
            created_with_email += 1

    return {
        "total": created_total,
        "with_email": created_with_email,
    }


# ── Envoi d'email ──────────────────────────────────────────────

def send_prospect_email(prospect, template) -> dict:
    """
    Envoie un email à un prospect via le template donné.
    Retourne {"success": bool, "error": str}.
    """
    from .models import EmailLog

    if not prospect.email:
        return {"success": False, "error": "Prospect sans email."}

    subject, body = template.render(prospect)

    log = EmailLog(
        prospect=prospect,
        template=template,
        subject=subject,
        body=body,
    )

    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=None,  # utilise DEFAULT_FROM_EMAIL
            recipient_list=[prospect.email],
            fail_silently=False,
        )
        log.success = True
        log.save()

        # Met à jour le statut du prospect
        prospect.status = "contacted"
        prospect.save(update_fields=["status"])

        return {"success": True, "error": ""}
    except Exception as exc:
        log.success = False
        log.error_message = str(exc)
        log.save()
        logger.error("Email send error to %s: %s", prospect.email, exc)
        return {"success": False, "error": str(exc)}
