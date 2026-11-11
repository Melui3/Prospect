from bs4 import BeautifulSoup
from django.db import transaction
from django.utils import timezone

from .models import EmailDraft, EmailLog, Prospect, QualificationReview
from .services import _get_public_page, _normalize_website_url


def _evidence(kind, source, detail, url="", observed_at=None):
    return {
        "kind": kind,
        "source": source,
        "detail": detail,
        "url": url,
        "observed_at": (observed_at or timezone.now()).isoformat(),
    }


def prospect_is_eligible(prospect):
    if prospect.merged_into_id or prospect.status != "new":
        return False
    # Any recorded attempt may have an uncertain delivery result, so keep it
    # out of a fresh outreach queue rather than risk contacting it twice.
    return not EmailLog.objects.filter(prospect=prospect).exists() and not prospect.last_contacted_at


def _draft_for_review(review):
    prospect = review.prospect
    observed = review.checked_at.strftime("%d/%m/%Y")
    observation = " ".join(review.reasons)
    subject = f"Une question au sujet de {prospect.nom}"
    body = (
        f"Bonjour {prospect.nom},\n\n"
        f"Lors d'une verification rapide le {observed}, j'ai observe le point suivant : {observation}\n\n"
        "Cette verification est limitee aux sources indiquees dans la fiche. "
        "Si ce sujet vous interesse, je peux vous envoyer une piste concrete par email.\n\n"
        "Bonne journee,\nNate"
    )
    EmailDraft.objects.get_or_create(prospect=prospect, defaults={"subject": subject, "body": body})


@transaction.atomic
def qualify_prospect(prospect):
    checked_at = timezone.now()
    existing = QualificationReview.objects.filter(prospect=prospect).first()
    if existing and existing.status in ["approved", "rejected", "deferred", "excluded"]:
        return existing
    if not prospect_is_eligible(prospect):
        return QualificationReview.objects.update_or_create(
            prospect=prospect,
            defaults={
                "status": "excluded",
                "priority": "low",
                "reasons": ["Fiche deja contactee, fermee, fusionnee ou exclue."],
                "evidence": [],
                "checked_at": checked_at,
            },
        )[0]

    evidence = []
    reasons = []
    website = _normalize_website_url(prospect.website or "")
    if not website:
        source = "OpenStreetMap" if prospect.external_id else "Fiche Prospect locale"
        evidence.append(_evidence(
            "website_not_listed",
            source,
            f"Aucune adresse de site n'etait renseignee dans cette source consultee. Cela ne prouve pas que l'entreprise n'a pas de site.",
            observed_at=checked_at,
        ))
        reasons.append(f"Aucun site n'est reference dans la fiche {source} consultee.")
        priority = "medium"
        status = "pending"
    else:
        try:
            response = _get_public_page(website)
            final_url = response.url or website
            status_code = int(response.status_code)
            evidence.append(_evidence(
                "http_response",
                "Requete HTTP publique",
                f"Le site a renvoye HTTP {status_code}.",
                final_url,
                checked_at,
            ))
            if status_code >= 400:
                reasons.append(f"La page consultee a renvoye HTTP {status_code} le {checked_at.strftime('%d/%m/%Y')}.")
                priority = "high"
                status = "pending"
            else:
                soup = BeautifulSoup(response.text or "", "html.parser")
                title = soup.title.get_text(" ", strip=True) if soup.title else ""
                if title:
                    evidence.append(_evidence("page_title", "HTML de la page", f"Titre detecte : {title[:180]}.", final_url, checked_at))
                else:
                    reasons.append("Aucun titre de page HTML n'a ete detecte sur la page consultee.")
                    evidence.append(_evidence("missing_title", "HTML de la page", "Aucun element <title> detecte.", final_url, checked_at))

                viewport = soup.find("meta", attrs={"name": lambda value: isinstance(value, str) and value.lower() == "viewport"})
                if viewport:
                    evidence.append(_evidence("viewport", "HTML de la page", "La balise meta viewport est presente.", final_url, checked_at))
                else:
                    reasons.append("La balise meta viewport n'a pas ete detectee sur la page consultee.")
                    evidence.append(_evidence("missing_viewport", "HTML de la page", "Aucune balise meta viewport detectee; le rendu mobile n'a pas ete teste.", final_url, checked_at))

                contact_links = []
                for link in soup.find_all("a", href=True):
                    href = link["href"].strip()
                    label = link.get_text(" ", strip=True).lower()
                    if any(word in f"{href.lower()} {label}" for word in ("contact", "contacter", "mentions")):
                        contact_links.append(href)
                if contact_links:
                    evidence.append(_evidence("contact_link", "Liens de la page", f"{len(contact_links)} lien(s) de contact ou de mentions detecte(s).", final_url, checked_at))
                else:
                    reasons.append("Aucun lien de contact ou de mentions n'a ete repere sur la page consultee.")
                    evidence.append(_evidence("missing_contact_link", "Liens de la page", "Aucun lien contenant contact, contacter ou mentions detecte; les autres moyens de contact n'ont pas ete verifies.", final_url, checked_at))

                priority = "medium" if len(reasons) >= 2 else "low"
                status = "pending" if reasons else "no_opportunity"
        except Exception as exc:
            evidence.append(_evidence(
                "site_unverified",
                "Verification HTTP",
                f"Verification impossible ({type(exc).__name__}); aucun probleme du site n'est conclu.",
                website,
                checked_at,
            ))
            reasons = ["Le site n'a pas pu etre verifie; aucun probleme n'est conclu."]
            priority = "low"
            status = "unverified"

    review, _ = QualificationReview.objects.update_or_create(
        prospect=prospect,
        defaults={"status": status, "priority": priority, "reasons": reasons, "evidence": evidence, "checked_at": checked_at},
    )
    if review.status == "pending":
        _draft_for_review(review)
    return review
