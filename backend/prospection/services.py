"""
Services métier :
  - scraping OSM (Overpass) + enrichissement Pages Jaunes
  - envoi d'emails
"""

import time
import hashlib
import json
import logging
import re
import unicodedata
import threading
import ipaddress
import socket
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from django.conf import settings
from django.utils import timezone
from .consultations import ConsultationError, request

logger = logging.getLogger(__name__)

REQUEST_HEADERS = {
    "User-Agent": "prospect-app/1.0",
    "Accept": "application/json",
}
_geocoding_lock = threading.Lock()
_last_geocoding_at = 0

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


class ProspectionTemporaryError(RuntimeError):
    pass

# ── Tags OSM connus ────────────────────────────────────────────
OSM_TAGS = {
    "commerce": '"shop"',
    "institut de beaute": '"shop"="beauty"',
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
        '"office"="association"',
        '"club"',
        '"amenity"="community_centre"',
        '"amenity"="social_facility"',
        '"operator:type"="association"',
    ],
}


def _get_city_coords(ville: str) -> tuple[str, str] | None:
    global _last_geocoding_at
    from .cache import cached_value, store_value
    cache_name = f"city:{ville.strip().lower()}"
    cached = cached_value(cache_name)
    if cached:
        return tuple(cached)
    try:
        with _geocoding_lock:
            time.sleep(max(0, 1.1 - (time.monotonic() - _last_geocoding_at)))
            _last_geocoding_at = time.monotonic()
            resp = request("GET",
                "https://nominatim.openstreetmap.org/search", source="nominatim",
                params={"q": ville, "format": "json", "limit": 1},
                headers=REQUEST_HEADERS,
                timeout=10,
            )
        resp.raise_for_status()
        data = resp.json()
        if not data:
            return None
        coords = [data[0]["lat"], data[0]["lon"]]
        store_value(cache_name, coords, hours=720)
        return tuple(coords)
    except ConsultationError:
        raise
    except Exception as exc:
        logger.error("Nominatim error: %s", exc)
        raise ProspectionTemporaryError("Le service de localisation ne repond pas. Nouvelle tentative programmee.") from exc


def _validate_overpass_response(response):
    try:
        data = response.json()
    except ValueError as exc:
        raise ConsultationError("Réponse Overpass non JSON.", temporary=True, source="overpass") from exc
    if (not isinstance(data, dict) or not isinstance(data.get("elements"), list)
            or data.get("remark") or any(
                not isinstance(row, dict) or row.get("type") not in ("node", "way", "relation")
                or not isinstance(row.get("id"), int) for row in data.get("elements", [])
            )):
        raise ConsultationError("Réponse Overpass inexploitable.", temporary=True, source="overpass")


def _query_overpass(tag_filters: str | list[str], lat: str, lon: str, rayon_m: int) -> list[dict]:
    if isinstance(tag_filters, str):
        tag_filters = [tag_filters]

    deadline = time.monotonic() + settings.OVERPASS_TOTAL_TIMEOUT
    elements_by_key = {}
    for element in _query_overpass_filters(tag_filters, lat, lon, rayon_m, deadline):
        elements_by_key[(element["type"], element["id"])] = element
    return list(elements_by_key.values())


def _query_overpass_filters(
    tag_filters: list[str],
    lat: str,
    lon: str,
    rayon_m: int,
    deadline: float,
) -> list[dict]:
    from .consultations import _current_job
    from .jobs import checkpoint

    endpoints = list(dict.fromkeys(settings.OVERPASS_ENDPOINTS))
    if not endpoints:
        raise ValueError("Aucun point d'accès Overpass configuré.")
    signature = hashlib.sha256(json.dumps(
        [tag_filters, lat, lon, rayon_m, endpoints], sort_keys=True,
    ).encode()).hexdigest()
    job = _current_job.get()
    state = job.payload.get("overpass", {}) if job else {}
    if state.get("signature") != signature:
        state = {"signature": signature, "next_endpoint": 0, "failures": []}

    def save_cursor(index):
        state["next_endpoint"] = index
        if job:
            job.payload["overpass"] = state
            checkpoint(job, payload=job.payload)

    query_parts = []
    for tag_filter in tag_filters:
        query_parts.append(f"node[{tag_filter}](around:{rayon_m},{lat},{lon});")
        query_parts.append(f"way[{tag_filter}](around:{rayon_m},{lat},{lon});")

    for index in range(state["next_endpoint"], len(endpoints)):
        endpoint = endpoints[index]
        remaining_seconds = deadline - time.monotonic()
        if remaining_seconds <= 0:
            break
        query_timeout = min(settings.OVERPASS_TIMEOUT, max(1, int(remaining_seconds)))
        query = "\n".join([
            f"[out:json][timeout:{query_timeout}];", "(", *query_parts, ");", "out tags;",
        ])
        try:
            resp = request("POST",
                endpoint, source="overpass",
                validate_response=_validate_overpass_response,
                data=query.encode("utf-8"),
                headers={**REQUEST_HEADERS, "Content-Type": "text/plain; charset=utf-8"},
                timeout=min(settings.OVERPASS_ENDPOINT_TIMEOUT,
                            settings.OVERPASS_TIMEOUT + 5, remaining_seconds),
            )
        except ConsultationError as exc:
            cause = exc.__cause__
            # Only transport outages allow fallback, never provider restrictions.
            if (not exc.temporary or exc.deferred or exc.retry_at or exc.http_status
                    or not isinstance(cause, (requests.Timeout, requests.ConnectionError))
                    or isinstance(cause, requests.exceptions.SSLError)):
                raise
            host = urlparse(endpoint).hostname
            reason = type(cause).__name__
            state["failures"] = (state["failures"] + [{
                "host": host, "reason": reason, "at": timezone.now().isoformat(),
            }])[-30:]
            save_cursor(index + 1)
            logger.warning("Overpass transport failure host=%s reason=%s next_endpoint=%s",
                           host, reason, index + 1)
            continue
        save_cursor(0)
        return resp.json()["elements"]

    if state["next_endpoint"] >= len(endpoints):
        save_cursor(0)
    raise ConsultationError(
        "Overpass temporairement indisponible : délai global atteint ou points d'accès injoignables. "
        "Une reprise bornée sera programmée par le worker.", temporary=True, source="overpass",
    )


def _find_email_pages_jaunes(nom: str, ville: str) -> str | None:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        )
    }
    url = (
        f"https://www.pagesjaunes.fr/annuaire/chercherlespros"
        f"?quoiqui={requests.utils.quote(nom)}&ou={requests.utils.quote(ville)}"
    )
    try:
        resp = request("GET", url, source="pages_jaunes", headers=headers, timeout=settings.PAGES_JAUNES_TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for result in soup.select("article, .bi-bloc"):
            if not _social_result_matches_name(nom, result.get_text(" ", strip=True), ""):
                continue
            for link in result.find_all("a", href=True):
                if link["href"].lower().startswith("mailto:"):
                    email = _extract_email(unquote(link["href"][7:]).split("?")[0])
                    if email:
                        return email
    except ConsultationError:
        raise
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
        resp = request("GET",
            "https://search.brave.com/search", source="social_search",
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
    except ConsultationError:
        raise
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


def _find_email_on_website(website: str, with_source=False, force=False):
    from .cache import cached_value, store_value
    start_url = _normalize_website_url(website)
    if not start_url:
        return (None, "") if with_source else None

    cached = None if force else cached_value(f"website:{start_url}")
    if cached is not None:
        return (cached["email"], cached["source"]) if with_source else cached["email"]

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
    successful_pages = 0

    while urls_to_visit and len(visited) < settings.WEBSITE_EMAIL_MAX_PAGES:
        url = urls_to_visit.pop(0)
        if url in visited:
            continue

        visited.add(url)

        try:
            resp = _get_public_page(url)
            resp.raise_for_status()
        except ConsultationError as exc:
            if exc.http_status in {404, 410}:
                continue
            raise
        except Exception as exc:
            logger.debug("Website email lookup error for %s: %s", url, exc)
            continue
        successful_pages += 1

        email = _extract_email(resp.text)
        if email:
            store_value(f"website:{start_url}", {"email": email, "source": resp.url}, hours=336)
            return (email, resp.url) if with_source else email

        if len(visited) == 1:
            redirected_base = f"{urlparse(resp.url).scheme}://{urlparse(resp.url).netloc}"
            urls_to_visit = _extract_contact_links(resp.text, resp.url, redirected_base) + urls_to_visit

    if not successful_pages:
        raise ProspectionTemporaryError("Site indisponible. Recherche d'email a retenter.")
    store_value(f"website:{start_url}", {"email": None, "source": ""}, hours=24)
    return (None, "") if with_source else None


def _get_public_page(url, *, before_request=None, source="website"):
    # OSM URLs are untrusted: never let a remote listing reach local services.
    for _ in range(5):
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Adresse de site invalide.")
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
        if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
            raise ValueError("Les sites locaux et prives ne peuvent pas etre analyses.")
        minimum_interval = before_request(url) if before_request else 0
        response = request("GET", url, source=source, headers=REQUEST_HEADERS,
                           timeout=settings.WEBSITE_EMAIL_TIMEOUT, allow_redirects=False,
                           minimum_interval=minimum_interval)
        if response.status_code not in [301, 302, 303, 307, 308]:
            return response
        url = urljoin(url, response.headers.get("Location", ""))
    raise ValueError("Trop de redirections.")


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
    """Queue the persistent search and return its current counters."""
    from .jobs import enqueue_search
    job = enqueue_search(campaign)
    return {"job_id": job.pk, "status": job.status,
            "total": job.total, "with_email": job.with_email}


def send_prospect_email(prospect, template) -> dict:
    """
    Envoie un email à un prospect via le template donné.
    Retourne {"success": bool, "error": str}.
    """
    from uuid import uuid4
    from .mail import send_message
    try:
        subject, body = template.render(prospect)
        send_message(prospect, subject, body, str(uuid4()), template)
        return {"success": True, "error": ""}
    except Exception as exc:
        return {"success": False, "error": str(exc)}
