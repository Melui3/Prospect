"""
Services métier :
  - scraping OSM (Overpass) + enrichissement Pages Jaunes
  - envoi d'emails
"""

import time
import logging
import re
import unicodedata
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

logger = logging.getLogger(__name__)

REQUEST_HEADERS = {
    "User-Agent": "prospect-app/1.0",
    "Accept": "application/json",
}

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
CONTACT_LINK_KEYWORDS = (
    "contact",
    "contacter",
    "mentions",
    "legal",
    "legales",
    "association",
    "bureau",
    "equipe",
)
SOCIAL_DOMAINS = {
    "facebook.com": "Facebook",
    "instagram.com": "Instagram",
    "linkedin.com": "LinkedIn",
    "linktr.ee": "Linktree",
    "helloasso.com": "HelloAsso",
}
SOCIAL_SEARCH_TARGETS = (
    "facebook",
    "instagram",
    "linkedin",
    "helloasso",
    "linktree",
)
BLOCKED_SOCIAL_PATH_PARTS = (
    "/share",
    "/sharer",
    "/login",
    "/accounts/",
    "/about/",
    "/privacy",
    "/help",
    "/explore/",
    "/tags/",
    "/reel/",
    "/reels/",
    "/p/",
    "/posts/",
    "/photos/",
    "/watch",
    "/events/",
    "/groups/",
    "/marketplace/",
    "/e/reg/",
)
SOCIAL_RESULT_STOPWORDS = {
    "www",
    "http",
    "https",
    "com",
    "fr",
    "net",
    "org",
    "the",
    "les",
    "des",
    "une",
    "pour",
    "avec",
    "chez",
}


class SocialSearchRateLimited(RuntimeError):
    pass

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
    "association": [
        '"operator:type"="association"',
        '"amenity"="community_centre"',
        '"club"',
        '"office"="association"',
        '"amenity"="social_facility"',
    ],
}


def _get_city_coords(ville: str) -> tuple[str, str] | None:
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": ville, "format": "json", "limit": 1},
            headers=REQUEST_HEADERS,
            timeout=10,
        )
        data = resp.json()
        if not data:
            return None
        return data[0]["lat"], data[0]["lon"]
    except Exception as exc:
        logger.error("Nominatim error: %s", exc)
        return None


def _query_overpass(tag_filters: str | list[str], lat: str, lon: str, rayon_m: int) -> list[dict]:
    if isinstance(tag_filters, str):
        tag_filters = [tag_filters]

    deadline = time.monotonic() + settings.OVERPASS_TOTAL_TIMEOUT
    elements_by_key = {}
    errors = []

    for tag_filter in tag_filters:
        if time.monotonic() >= deadline:
            errors.append("temps total Overpass depasse")
            break

        try:
            for element in _query_overpass_filter(tag_filter, lat, lon, rayon_m, deadline):
                element_key = (element.get("type"), element.get("id"))
                elements_by_key[element_key] = element
        except Exception as exc:
            logger.warning("Overpass filter error for %s: %s", tag_filter, exc)
            errors.append(str(exc))

    if elements_by_key:
        return list(elements_by_key.values())

    if errors:
        raise RuntimeError("Erreur Overpass : " + " | ".join(errors))

    return []


def _query_overpass_filter(
    tag_filter: str,
    lat: str,
    lon: str,
    rayon_m: int,
    deadline: float,
) -> list[dict]:
    remaining_seconds = max(1, int(deadline - time.monotonic()))
    query_timeout = min(settings.OVERPASS_TIMEOUT, remaining_seconds)
    query = f"""
    [out:json][timeout:{query_timeout}];
    (
      node[{tag_filter}](around:{rayon_m},{lat},{lon});
      way[{tag_filter}](around:{rayon_m},{lat},{lon});
    );
    out tags;
    """
    errors = []

    for endpoint in settings.OVERPASS_ENDPOINTS:
        remaining_seconds = deadline - time.monotonic()
        if remaining_seconds <= 0:
            break

        try:
            resp = requests.post(
                endpoint,
                data=query.encode("utf-8"),
                headers={**REQUEST_HEADERS, "Content-Type": "text/plain; charset=utf-8"},
                timeout=max(1, min(settings.OVERPASS_TIMEOUT + 5, remaining_seconds)),
            )
            resp.raise_for_status()
            return resp.json().get("elements", [])
        except Exception as exc:
            logger.warning("Overpass error on %s: %s", endpoint, exc)
            errors.append(f"{endpoint}: {exc}")

    raise RuntimeError("Erreur Overpass : " + " | ".join(errors))


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
        resp = requests.get(url, headers=headers, timeout=settings.PAGES_JAUNES_TIMEOUT)
        soup = BeautifulSoup(resp.text, "html.parser")
        for link in soup.find_all("a", href=True):
            if "mailto:" in link["href"]:
                return link["href"].replace("mailto:", "").strip()
    except Exception as exc:
        logger.warning("Pages Jaunes error for %s: %s", nom, exc)
    return None


# ── Prospection principale ─────────────────────────────────────

def _find_social_from_tags(tags: dict) -> tuple[str | None, str]:
    for key in (
        "contact:facebook",
        "facebook",
        "social:facebook",
        "contact:instagram",
        "instagram",
        "social:instagram",
        "contact:linkedin",
        "linkedin",
        "social:linkedin",
    ):
        value = (tags.get(key) or "").strip()
        if not value:
            continue

        social_url = _normalize_social_url(value, key)
        platform = _social_platform(social_url)
        if social_url and platform:
            return social_url, platform

    return None, ""


def _find_social_web(nom: str, ville: str) -> tuple[str | None, str]:
    query = f'"{nom}" "{ville}" {" ".join(SOCIAL_SEARCH_TARGETS)}'

    try:
        resp = requests.get(
            "https://search.brave.com/search",
            params={"q": query, "source": "web"},
            headers={
                **REQUEST_HEADERS,
                "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
                ),
            },
            timeout=settings.SOCIAL_SEARCH_TIMEOUT,
        )
        if resp.status_code == 429:
            raise SocialSearchRateLimited("Brave Search rate limit")
        resp.raise_for_status()
    except SocialSearchRateLimited:
        raise
    except Exception as exc:
        logger.debug("Social search error for %s: %s", nom, exc)
        return None, ""

    seen_urls = set()
    soup = BeautifulSoup(resp.text, "html.parser")
    for link in soup.find_all("a", href=True):
        url = _canonical_social_url(_unwrap_search_result_url(link["href"]))
        if not url or url in seen_urls:
            continue

        seen_urls.add(url)
        platform = _social_platform(url)
        if not platform or not _is_probable_social_profile(url):
            continue

        result_text = link.get_text(" ", strip=True)
        if not _social_result_matches_name(nom, result_text, url):
            continue

        return url, platform

    return None, ""


def _normalize_social_url(value: str, key: str = "") -> str | None:
    value = value.strip()
    if not value:
        return None

    if value.startswith("@"):
        if "instagram" in key:
            value = f"https://www.instagram.com/{value.lstrip('@')}"
        elif "facebook" in key:
            value = f"https://www.facebook.com/{value.lstrip('@')}"
        elif "linkedin" in key:
            value = f"https://www.linkedin.com/company/{value.lstrip('@')}"
    elif (
        key
        and not value.startswith(("http://", "https://"))
        and "/" not in value
        and "." not in value
    ):
        if "instagram" in key:
            value = f"https://www.instagram.com/{value}"
        elif "facebook" in key:
            value = f"https://www.facebook.com/{value}"
        elif "linkedin" in key:
            value = f"https://www.linkedin.com/company/{value}"

    if not value.startswith(("http://", "https://")):
        value = f"https://{value}"

    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None

    return value


def _unwrap_search_result_url(url: str) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    if "uddg" in query:
        return unquote(query["uddg"][0])
    return url


def _canonical_social_url(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None

    netloc = parsed.netloc.lower()
    if netloc.startswith("m.facebook.com"):
        netloc = netloc.replace("m.facebook.com", "www.facebook.com", 1)

    path = parsed.path.rstrip("/")
    query = parsed.query if path.endswith("/profile.php") else ""

    return parsed._replace(
        scheme="https",
        netloc=netloc,
        path=path or "/",
        params="",
        query=query,
        fragment="",
    ).geturl()


def _social_platform(url: str | None) -> str:
    if not url:
        return ""

    netloc = urlparse(url).netloc.lower().removeprefix("www.").removeprefix("m.")
    for domain, platform in SOCIAL_DOMAINS.items():
        if netloc == domain or netloc.endswith(f".{domain}"):
            return platform
    return ""


def _is_probable_social_profile(url: str) -> bool:
    parsed = urlparse(url)
    platform = _social_platform(url)
    path = parsed.path.lower()
    if any(part in path for part in BLOCKED_SOCIAL_PATH_PARTS):
        return False
    if path in {"", "/"}:
        return False

    segments = [part for part in path.split("/") if part]
    if platform == "Instagram" and len(segments) != 1:
        return False
    if platform == "LinkedIn" and not path.startswith("/company/"):
        return False
    if platform == "HelloAsso" and not path.startswith("/associations/"):
        return False

    return True


def _social_result_matches_name(nom: str, result_text: str, url: str) -> bool:
    name_words = _important_words(nom)
    if not name_words:
        return True

    haystack_words = _normalized_words(f"{result_text} {url}")
    required_matches = 1 if len(name_words) == 1 else 2
    matches = 0

    for word in name_words:
        if _word_matches_any(word, haystack_words):
            matches += 1
        if matches >= required_matches:
            return True

    return False


def _important_words(value: str) -> list[str]:
    unique_words = []
    for word in _normalized_words(value):
        if word in SOCIAL_RESULT_STOPWORDS or word in unique_words:
            continue
        unique_words.append(word)
    return unique_words


def _normalized_words(value: str) -> list[str]:
    folded = unicodedata.normalize("NFKD", value or "")
    ascii_value = folded.encode("ascii", "ignore").decode("ascii")
    return [
        word
        for word in re.split(r"[^a-z0-9]+", ascii_value.lower())
        if len(word) >= 3
    ]


def _word_matches_any(word: str, haystack_words: list[str]) -> bool:
    return any(
        word == candidate
        or (len(word) >= 4 and word in candidate)
        or (len(candidate) >= 4 and candidate in word)
        for candidate in haystack_words
    )


def _find_email_on_website(website: str) -> str | None:
    start_url = _normalize_website_url(website)
    if not start_url:
        return None

    parsed_start = urlparse(start_url)
    base_url = f"{parsed_start.scheme}://{parsed_start.netloc}"
    urls_to_visit = [start_url]
    urls_to_visit.extend(
        urljoin(base_url, path)
        for path in (
            "/contact",
            "/contactez-nous",
            "/nous-contacter",
            "/mentions-legales",
            "/mentions-legales.html",
        )
    )
    visited = set()

    while urls_to_visit and len(visited) < settings.WEBSITE_EMAIL_MAX_PAGES:
        url = urls_to_visit.pop(0)
        if url in visited:
            continue

        visited.add(url)

        try:
            resp = requests.get(
                url,
                headers=REQUEST_HEADERS,
                timeout=settings.WEBSITE_EMAIL_TIMEOUT,
                allow_redirects=True,
            )
            resp.raise_for_status()
        except Exception as exc:
            logger.debug("Website email lookup error for %s: %s", url, exc)
            continue

        email = _extract_email(resp.text)
        if email:
            return email

        if len(visited) == 1:
            urls_to_visit.extend(_extract_contact_links(resp.text, resp.url, base_url))

    return None


def _normalize_website_url(website: str) -> str | None:
    website = (website or "").strip()
    if not website or website.startswith("mailto:"):
        return None

    if not website.startswith(("http://", "https://")):
        website = f"https://{website}"

    parsed = urlparse(website)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None

    return website


def _extract_contact_links(html: str, current_url: str, base_url: str) -> list[str]:
    parsed_base = urlparse(base_url)
    links = []

    soup = BeautifulSoup(html, "html.parser")
    for link in soup.find_all("a", href=True):
        href = link["href"].strip()
        text = link.get_text(" ", strip=True).lower()

        if href.startswith("mailto:"):
            continue

        haystack = f"{href} {text}".lower()
        if not any(keyword in haystack for keyword in CONTACT_LINK_KEYWORDS):
            continue

        url = urljoin(current_url, href)
        parsed_url = urlparse(url)
        if parsed_url.netloc != parsed_base.netloc:
            continue

        links.append(url)

    return links


def _extract_email(text: str) -> str | None:
    normalized = re.sub(r"\s*(\[at\]|\(at\)|arobase)\s*", "@", text, flags=re.IGNORECASE)
    normalized = re.sub(
        r"\s*(\[dot\]|\(dot\)|\[point\]|\(point\)|point)\s*",
        ".",
        normalized,
        flags=re.IGNORECASE,
    )

    for email in EMAIL_RE.findall(normalized):
        email = email.strip(".,;:()[]{}<>").lower()
        if _is_probable_contact_email(email):
            return email

    return None


def _is_probable_contact_email(email: str) -> bool:
    if email.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")):
        return False
    if email.startswith(("example@", "test@", "email@")):
        return False
    return True


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
    enrichment_deadline = time.monotonic() + settings.ENRICHMENT_TOTAL_TIMEOUT
    website_email_lookups_left = settings.WEBSITE_EMAIL_MAX_LOOKUPS
    social_search_lookups_left = settings.SOCIAL_SEARCH_MAX_LOOKUPS
    pages_jaunes_lookups_left = settings.PAGES_JAUNES_MAX_LOOKUPS

    created_total = 0
    created_with_email = 0

    for element in elements:
        tags = element.get("tags", {})
        nom = tags.get("name", "").strip()
        if not nom:
            continue

        website = tags.get("website") or tags.get("contact:website") or None
        email = tags.get("email") or tags.get("contact:email") or None
        social_url, social_platform = _find_social_from_tags(tags)

        if (
            not email
            and website
            and website_email_lookups_left > 0
            and time.monotonic() < enrichment_deadline
        ):
            email = _find_email_on_website(website)
            website_email_lookups_left -= 1

        # On garde les structures avec site uniquement si le site donne un email.
        if website and not email:
            continue

        if (
            not website
            and not social_url
            and social_search_lookups_left > 0
            and time.monotonic() < enrichment_deadline
        ):
            try:
                social_url, social_platform = _find_social_web(nom, campaign.ville)
            except SocialSearchRateLimited:
                logger.info("Social search rate limited; disabling for this campaign")
                social_search_lookups_left = 0
            else:
                social_search_lookups_left -= 1

        # Enrichissement Pages Jaunes si pas d'email
        if (
            not email
            and pages_jaunes_lookups_left > 0
            and time.monotonic() < enrichment_deadline
        ):
            email = _find_email_pages_jaunes(nom, campaign.ville)
            pages_jaunes_lookups_left -= 1
            if settings.PAGES_JAUNES_DELAY_SECONDS > 0:
                time.sleep(settings.PAGES_JAUNES_DELAY_SECONDS)

        telephone = tags.get("phone") or tags.get("contact:phone") or ""

        prospect, created = Prospect.objects.get_or_create(
            campaign=campaign,
            nom=nom,
            defaults={
                "adresse": tags.get("addr:street", ""),
                "ville": tags.get("addr:city", campaign.ville),
                "telephone": telephone,
                "email": email or None,
                "website": website,
                "has_website": bool(website),
                "social_url": social_url,
                "social_platform": social_platform,
            },
        )

        if not created:
            update_fields = []
            if email and not prospect.email:
                prospect.email = email
                update_fields.append("email")
            if website and not prospect.website:
                prospect.website = website
                prospect.has_website = True
                update_fields.extend(["website", "has_website"])
            if telephone and not prospect.telephone:
                prospect.telephone = telephone
                update_fields.append("telephone")
            if social_url and not prospect.social_url:
                prospect.social_url = social_url
                prospect.social_platform = social_platform
                update_fields.extend(["social_url", "social_platform"])
            if update_fields:
                prospect.save(update_fields=update_fields)

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
