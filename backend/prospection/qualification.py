from urllib.parse import unquote, urlsplit

from bs4 import BeautifulSoup
from django.db import transaction
from django.utils import timezone

from .models import EmailDraft, EmailLog, Prospect, QualificationReview
from .consultations import ConsultationError
from .services import _get_public_page, _normalize_website_url, _normalized_words, _social_platform


CREATION_SUBJECT = "À propos du site web de {nom}"
CREATION_BODY = """Bonjour,

En recherchant {nom} à {ville}, je n'ai pas trouvé de site officiel associé à votre établissement.

Si vous n'en disposez pas encore, un site web pourrait compléter votre présence sur Google et les réseaux sociaux, en permettant à vos clients de découvrir votre activité, vos services et vos coordonnées au même endroit.

Je suis Nathaniel, développeur web indépendant chez NateOS. Je conçois des sites professionnels pour les commerces et petites entreprises, adaptés aux téléphones et pensés pour le référencement local.

Si ce projet peut vous intéresser, je peux vous proposer un devis gratuit et sans engagement.

Cordialement,

Nathaniel
NateOS"""

REFONT_SUBJECT = "Une piste pour la version mobile du site de {nom}"
REFONT_BODY = """Bonjour,

En consultant {website}, j’ai constaté que la page ne déclare pas comment elle doit s’adapter à la largeur de l’écran. Je peux vous proposer de vérifier son affichage sur téléphone et d’ajuster la mise en page si nécessaire.

Je suis Nathaniel, développeur web indépendant chez NateOS. Si cette amélioration vous intéresse, je peux vous proposer un devis gratuit et sans engagement.

Cordialement,

Nathaniel
NateOS"""


def _evidence(kind, source, detail, method, limits, url="", **values):
    return {
        "kind": kind, "source": source, "detail": detail, "url": url,
        "method": method, "limits": limits, "observed_at": timezone.now().isoformat(),
        "origin": "automatic",
        **values,
    }


def prospect_is_eligible(prospect):
    from .opposition import is_opposed
    if is_opposed(prospect.nom, prospect.ville, prospect.email, prospect.website):
        return False
    if prospect.merged_into_id or prospect.status != "new" or prospect.last_contacted_at:
        return False
    attempts = getattr(prospect, "has_outreach_attempt", None)
    if attempts is None:
        attempts = EmailLog.objects.filter(prospect=prospect).exists()
    return not attempts


def _clean(value):
    # The message is plain text. Keep inserted values on one line and format once.
    return " ".join((value or "").split())


def _identity(prospect):
    return {"name": _clean(prospect.nom), "city": _clean(prospect.ville)}


def _email(prospect):
    return _clean(prospect.email).casefold()


def _site(prospect):
    return _normalize_website_url(prospect.website or "")


def _active_evidence(review):
    return [item for item in review.evidence if not item.get("historical")]


def opportunity(review):
    prospect = review.prospect
    if review.status not in {"pending", "deferred", "approved"} or not _email(prospect):
        return None
    evidence = _active_evidence(review)
    contact = next((item for item in reversed(evidence) if item["kind"] == "corroborated_contact"), None)
    if not contact or contact.get("email") != _email(prospect) or contact.get("identity") != _identity(prospect):
        return None
    if not all(_identity(prospect).values()):
        return None
    automatic_discovery = any(item.get("run_id", "").startswith("discovery:") for item in evidence)
    commercial_signal = any(item["kind"] in {"third_party_menu", "dispersed_information"} for item in evidence)
    if not _clean(prospect.website) and any(item["kind"] == "public_search_no_official_site" for item in evidence) and (
        not automatic_discovery or commercial_signal
    ):
        return "creation"
    if _site(prospect) and any(
        item["kind"] == "missing_viewport" and item.get("input_website") == _site(prospect)
        for item in evidence
    ):
        return "refonte"
    return None


def review_bucket(review):
    if review.status in {"excluded", "rejected"} or not prospect_is_eligible(review.prospect):
        return "excluded"
    if review.status == "deferred":
        return "deferred"
    if review.status == "no_opportunity":
        return "no_opportunity"
    if review.status == "approved":
        return "approved"
    return "ready" if opportunity(review) else "enrich"


def draft_suggestion(review):
    kind = opportunity(review)
    if not kind:
        return None
    prospect = review.prospect
    site = next((row["url"] for row in reversed(_active_evidence(review)) if row["kind"] == "missing_viewport"), "")
    context = {
        "nom": _clean(prospect.nom), "ville": _clean(prospect.ville),
        "secteur": _clean(prospect.campaign.secteur) if prospect.campaign_id else "",
        "website": _clean(site),
    }
    subject, body = (CREATION_SUBJECT, CREATION_BODY) if kind == "creation" else (REFONT_SUBJECT, REFONT_BODY)
    body = body.format_map(context)
    if kind == "creation":
        specific = next((row.get("offer", "") for row in reversed(_active_evidence(review))
                         if row["kind"] == "commercial_pilot"), "")
        if specific:
            body = body.replace("\n\nJe suis Nathaniel", f"\n\n{specific}\n\nJe suis Nathaniel", 1)
    return {"subject": subject.format_map(context)[:200], "body": body}


@transaction.atomic
def _save_review(prospect, status, reasons, evidence, priority="low", preserve_deferred=False):
    existing = QualificationReview.objects.select_for_update().filter(prospect=prospect).first()
    if existing and existing.status in {"approved", "rejected", "excluded"}:
        return existing
    if existing and existing.status == "deferred":
        if not preserve_deferred:
            return existing
        status = "deferred"
    if not prospect_is_eligible(prospect):
        status = "excluded"
        reasons = ["Fiche déjà contactée, fermée, fusionnée ou exclue."]
    history = [{**item, "historical": True} for item in existing.evidence] if existing else []
    review, _ = QualificationReview.objects.update_or_create(
        prospect=prospect,
        defaults={"status": status, "priority": priority, "reasons": reasons,
                  "evidence": history + evidence, "checked_at": timezone.now()},
    )
    suggestion = draft_suggestion(review)
    if suggestion:
        EmailDraft.objects.get_or_create(prospect=prospect, defaults=suggestion)
    return review


def record_creation_search(prospect, *, search_url, contact_url, method, limits, origin="human"):
    evidence = [
        _evidence("public_search_no_official_site", "Recherche publique consignée",
                  "Aucun site officiel associé à cet établissement dans les résultats consultés.",
                  method, limits, search_url),
        _evidence("corroborated_contact", "Source publique du contact", "Adresse professionnelle corroborée.",
                  "Vérification par l’utilisateur de l’identité du commerce et de l’adresse publiée.",
                  "L’adresse publiée ne garantit pas la réception du message.", contact_url,
                  email=_email(prospect), identity=_identity(prospect)),
    ]
    for item in evidence:
        item["origin"] = origin
    return _save_review(prospect, "pending", ["Recherche publique documentée et contact corroboré."],
                        evidence, priority="medium", preserve_deferred=True)


def _check_listed_page(prospect, website):
    response = _get_public_page(website)
    url = response.url or website
    code = int(response.status_code)
    evidence = [_evidence("http_response", "Page publique", f"Réponse HTTP {code}.",
                          "Requête HTTP sur la page renseignée.", "Une seule page consultée.", url)]
    if not 200 <= code < 300 or _social_platform(url):
        return "unverified", ["La page ne permet pas de vérifier le site de l’établissement."], evidence
    soup = BeautifulSoup(response.text or "", "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    visible_words = set(_normalized_words(f"{title} {soup.get_text(' ', strip=True)}"))
    identity_words = set(_normalized_words(prospect.nom))
    same_host = (urlsplit(url).hostname or "").removeprefix("www.") == (urlsplit(website).hostname or "").removeprefix("www.")
    if not same_host or not identity_words or not identity_words <= visible_words or not soup.find("html"):
        return "unverified", ["L’identité de l’établissement n’a pas pu être corroborée sur cette page."], evidence
    addresses = {
        unquote(link["href"][7:].split("?", 1)[0]).strip().casefold()
        for link in soup.find_all("a", href=True) if link["href"].lower().startswith("mailto:")
    }
    if not _email(prospect) or _email(prospect) not in addresses:
        return "unverified", ["Email manquant ou adresse non corroborée sur la page publique."], evidence
    evidence.append(_evidence("corroborated_contact", "Page publique du site", "Adresse publiée sur la page.",
                              "Correspondance exacte avec un lien mailto et contrôle du nom affiché.",
                              "Une seule page consultée. La délivrabilité n’a pas été testée.", url,
                              email=_email(prospect), identity=_identity(prospect)))
    viewport = soup.find("meta", attrs={"name": lambda value: value and value.lower() == "viewport"})
    if viewport:
        evidence.append(_evidence("viewport", "HTML de la page", "Balise viewport présente.",
                                  "Lecture du HTML public.", "Affichage mobile et autres pages non testés.", url))
        return "no_opportunity", ["Aucune anomalie commerciale démontrée par les vérifications effectuées."], evidence
    evidence.append(_evidence("missing_viewport", "HTML de la page", "La page ne déclare pas de balise viewport.",
                              "Lecture du HTML public.", "Affichage mobile et autres pages non testés.", url,
                              input_website=website))
    return "pending", ["La page consultée ne déclare pas de balise viewport."], evidence


def qualify_prospect(prospect: Prospect, *, recheck=False):
    existing = QualificationReview.objects.filter(prospect=prospect).first()
    if existing and (
        existing.status in {"approved", "rejected", "excluded"}
        or existing.status == "deferred" and not recheck
        or opportunity(existing) == "creation"
    ):
        return existing
    if not prospect_is_eligible(prospect):
        return _save_review(prospect, "excluded", [], [])
    website = _site(prospect)
    if not website:
        listed = bool(_clean(prospect.website))
        evidence = [_evidence("site_unverified" if listed else "website_not_listed", "Fiche Prospect",
                              "Adresse renseignée inexploitable." if listed else "Champ site web vide.",
                              "Lecture de la fiche.", "Ce relevé ne prouve pas l’absence de site officiel.")]
        reasons = ["Une recherche publique est nécessaire pour identifier le site officiel."]
        if not _email(prospect):
            reasons.insert(0, "Email manquant.")
        return _save_review(prospect, "unverified", reasons, evidence, preserve_deferred=recheck)
    try:
        status, reasons, evidence = _check_listed_page(prospect, website)
    except ConsultationError:
        raise
    except Exception as exc:
        status, reasons = "unverified", ["La page publique n’a pas pu être vérifiée."]
        evidence = [_evidence("site_unverified", "Page publique", f"Vérification indisponible ({type(exc).__name__}).",
                              "Requête HTTP sur la page renseignée.", "Aucun problème du site n’est établi.", website)]
    # The network request happens outside the write transaction.
    return _save_review(prospect, status, reasons, evidence, priority="medium" if status == "pending" else "low",
                        preserve_deferred=recheck)
