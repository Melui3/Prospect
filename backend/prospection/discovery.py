"""Bounded public discovery. Every accepted claim keeps its source and limits."""
import hashlib
import json
import re
from urllib.parse import quote, unquote, urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .consultations import ConsultationError
from .identity import normalized
from .models import Prospect, QualificationReview
from .opposition import is_opposed, persist_opposition
from .services import EMAIL_RE, REQUEST_HEADERS, _get_public_page, _is_probable_contact_email

NAME_STOP = {"le", "la", "les", "de", "du", "des", "et", "sarl", "sas", "eurl"}
ACTIVITIES = {
    "restaurant": {"restaurant", "restauration"},
    "boulangerie": {"boulangerie", "boulanger"},
    "coiffeur": {"coiffeur", "coiffure", "salon de coiffure"},
}
OPPOSITION = re.compile(
    r"(nous refusons (?:toute |la )?prospection commerciale|"
    r"aucune prospection commerciale|"
    r"merci de ne pas (?:nous )?contacter[^.]{0,50}(?:commercial|prospection))"
)


def _input(prospect):
    return {"id": prospect.pk, "name": prospect.nom, "city": prospect.ville,
            "address": prospect.adresse, "email": prospect.email, "website": prospect.website,
            "activity": prospect.campaign.secteur if prospect.campaign_id else prospect.raw_tags.get("amenity", "")}


def _save(job):
    from .jobs import checkpoint
    checkpoint(job, payload=job.payload)


def _add(job, kind, url, detail, limits, *, observed_at=None, **extra):
    state = job.payload["discovery"]
    company = state["input"]
    identity = hashlib.sha256(json.dumps(
        [job.pk, kind, url, detail, extra], sort_keys=True, default=str).encode()).hexdigest()[:24]
    row = {"id": identity, "run_id": f"discovery:{job.pk}", "kind": kind,
           "company": {"id": company["id"], "name": company["name"], "city": company["city"]},
           "source": urlsplit(url).hostname or "Prospect", "url": url,
           "observed_at": observed_at or timezone.now().isoformat(), "origin": "automatic",
           "method": "Lecture HTTP publique et recoupement du nom, de la commune et de l’activité.",
           "detail": detail, "limits": limits, **extra}
    if not any(e["id"] == identity for e in state["evidence"]):
        state["evidence"].append(row)


def _policy(job, url):
    state = job.payload["discovery"]
    parsed = urlsplit(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    if origin not in state["robots"]:
        robots_url = origin + "/robots.txt"
        try:
            response = _get_public_page(robots_url)
            rules = response.text
        except ConsultationError as exc:
            if exc.http_status not in {404, 410}:
                raise
            rules = ""
        state["robots"][origin] = rules
        _save(job)
    parser = RobotFileParser()
    parser.parse(state["robots"][origin].splitlines())
    agent = REQUEST_HEADERS["User-Agent"]
    if not parser.can_fetch(agent, url):
        raise ConsultationError("Consultation refusée par robots.txt.", source=origin)
    return parser.crawl_delay(agent) or 0


def _read(job, url, source="website"):
    return _get_public_page(url, before_request=lambda target: _policy(job, target), source=source)


def _search(job):
    state = job.payload["discovery"]
    company = state["input"]
    query = f'"{company["name"]}" "{company["city"]}" {company["activity"]} site officiel'
    from .search_providers import search
    try:
        result = search(query)
    except ConsultationError as exc:
        _add(job, "search_blocked", "https://api.tavily.com/search", str(exc),
             "Source de découverte indisponible. Aucun jugement sur l’entreprise ni absence de site n’est déduit.",
             http_status=exc.http_status, method="Appel de recherche autorisé, sans contournement des restrictions.")
        _save(job)
        raise
    state["search_url"] = result["source_url"]
    state["search_provider"] = result["provider"]
    state["search_completed"] = True
    state["search_at"] = result["observed_at"]
    _add(job, "public_search", result["source_url"],
         f"Recherche par nom, commune et activité terminée. {len(result['urls'])} lien(s) candidat(s).",
         "Résultats bornés à cette requête ; les extraits ne constituent pas des preuves. Un site non indexé peut exister.",
         observed_at=result["observed_at"], method="Tavily Search basic ; vérification indépendante des pages candidates.")
    return result["urls"]


def _focus(soup, company):
    words = set(normalized(company["name"]).split()) - NAME_STOP
    for article in soup.select("article"):
        title = article.find(["h1", "h2", "h3"])
        if title and words and words <= set(normalized(title.get_text(" ", strip=True)).split()):
            return article, words
    return soup.find("main") or soup.find("body") or soup, words


def _analyse_page(job, entry, response):
    state = job.payload["discovery"]
    company = state["input"]
    soup = BeautifulSoup(response.text, "html.parser")
    focus, name_words = _focus(soup, company)
    headings = [normalized(h.get_text(" ", strip=True)) for h in
                focus.find_all(["h1", "h2", "h3"] if focus.name == "article" else ["h1"])]
    text = normalized(focus.get_text(" ", strip=True))
    city_words = set(normalized(company["city"]).split())
    activity = normalized(company["activity"])
    activities = ACTIVITIES.get(activity, {activity}) - {""}
    activity_match = any(a in text for a in activities)
    name_match = bool(name_words) and any(name_words <= set(title.split()) for title in headings)
    city_match = bool(city_words) and city_words <= set(text.split())
    url = response.url
    host = (urlsplit(url).hostname or "").lower().removeprefix("www.")
    directory = any(host == d or host.endswith("." + d) for d in settings.DISCOVERY_DIRECTORY_HOSTS)
    inherited = bool(entry.get("official_root")) and urlsplit(entry["official_root"]).netloc == urlsplit(url).netloc
    matched = name_match and city_match and activity_match
    when = getattr(response, "prospect_observed_at", timezone.now().isoformat())
    if not matched and not inherited:
        state["ambiguous"] = True
        _add(job, "identity_uncertain", url,
             "L’identité complète de cet établissement n’est pas corroborée sur cette page.",
             "Les variantes de nom, communes absentes et pages ambiguës nécessitent une vérification.",
             observed_at=when)
        return []
    _add(job, "identity_corroborated", url, "Nom, commune et activité recoupés.",
         "Recoupement textuel déterministe. L’identité juridique et la propriété du domaine restent non certifiées.",
         observed_at=when)
    # A brand in a subdomain does not establish ownership of the parent domain.
    labels = host.split(".")
    domain_words = normalized(labels[-2] if len(labels) >= 2 else "").replace(" ", "")
    domain_match = bool(name_words) and all(word in domain_words for word in name_words)
    official = not directory and (domain_match or entry.get("linked_official") or inherited)
    if not directory and not official:
        state["ambiguous"] = True
        _add(job, "domain_uncertain", url, "Le rattachement du domaine à l’établissement reste incertain.",
             "La correspondance textuelle seule ne confirme pas le caractère officiel.", observed_at=when)
        return []
    emails = set()
    for link in focus.find_all("a", href=True):
        if link["href"].lower().startswith("mailto:"):
            emails.update(EMAIL_RE.findall(unquote(link["href"][7:].split("?", 1)[0])))
    emails.update(EMAIL_RE.findall(focus.get_text(" ", strip=True)))
    for email in sorted({e.casefold() for e in emails if _is_probable_contact_email(e)}):
        item = {"email": email, "url": url, "observed_at": when}
        if item not in state["contacts"]:
            state["contacts"].append(item)
    if OPPOSITION.search(text):
        _add(job, "commercial_opposition", url, "Refus explicite de prospection commerciale publié.",
             "Portée limitée à l’établissement et au contact corroborés.", observed_at=when)
        state["opposed"] = True
        state["opposition_site"] = url if official else None
        return []
    if official and not inherited:
        if url not in state["official"]:
            state["official"].append(url)
        _add(job, "official_site", url, "Site rattaché à l’établissement par son nom, sa commune, son activité et son domaine.",
             "Concordance publique. Aucun contrôle de propriété du domaine.", observed_at=when,
             requested_url=entry["url"])
        viewport = soup.find("meta", attrs={"name": lambda value: value and value.lower() == "viewport"})
        _add(job, "viewport" if viewport else "missing_viewport", url,
             "Balise viewport présente." if viewport else "La page ne déclare pas de balise viewport.",
             "Lecture HTML uniquement. L’affichage mobile n’a pas été testé.",
             observed_at=when, input_website=company["website"] or url)
    if directory:
        menu = next((h.get_text(" ", strip=True) for h in focus.find_all(["h2", "h3"])
                     if re.search(r"\b(carte|menu)\b", normalized(h.get_text(" ", strip=True)))), "")
        if menu:
            _add(job, "third_party_menu", url, f"Une section « {menu[:120]} » est publiée sur cette page tierce.",
                 "Fraîcheur de la carte et maîtrise éditoriale par le restaurant non établies.", observed_at=when)
        practical = any(re.search(r"\b(horaires|adresse|informations pratiques)\b",
                                 normalized(h.get_text(" ", strip=True))) for h in focus.find_all(["h2", "h3"]))
        if practical and host not in state["practical_sources"]:
            state["practical_sources"].append(host)
    extra = []
    for link in focus.find_all("a", href=True):
        target = urljoin(url, link["href"])
        parts = urlsplit(target)
        if parts.scheme not in {"http", "https"}:
            continue
        label = normalized(link.get_text(" ", strip=True))
        if directory and label in {"site officiel", "site web", "visiter le site web"}:
            extra.append({"url": target, "linked_official": True})
        elif official and parts.netloc == urlsplit(url).netloc and any(w in label for w in ["contact", "mentions legales"]):
            extra.append({"url": target, "official_root": entry.get("official_root") or url})
    return extra[:settings.DISCOVERY_EXTRA_PAGES]


def _finish(job, prospect):
    from .qualification import _save_review, _identity
    state = job.payload["discovery"]
    emails = {contact["email"] for contact in state["contacts"]}
    chosen = next(iter(emails)) if len(emails) == 1 else None
    contact_state = "not_found"
    if emails:
        contact_state = "corroborated" if chosen and (not prospect.email or prospect.email.casefold() == chosen) else "uncertain"
    if len(state["official"]) > 1:
        contact_state = "uncertain"
        state["ambiguous"] = True
    state["contact_state"] = contact_state
    if contact_state == "corroborated":
        contact = next(c for c in state["contacts"] if c["email"] == chosen)
        _add(job, "corroborated_contact", contact["url"], "Adresse professionnelle publiée sur une page d’identité corroborée.",
             "Adresse publiée et recoupée. La délivrabilité reste non testée.", observed_at=contact["observed_at"],
             email=chosen, identity=_identity(prospect))
    else:
        _add(job, "contact_uncertain" if contact_state == "uncertain" else "contact_not_found",
             state.get("search_url") or prospect.website or "",
             "Contact incertain." if contact_state == "uncertain" else "Contact professionnel non trouvé dans les pages consultées.",
             "Aucune adresse n’est déduite ou inventée.")
    if state.get("search_completed") and not state["official"] and not state.get("ambiguous"):
        _add(job, "public_search_no_official_site", state["search_url"],
             "Aucun site officiel corroboré dans les résultats et pages consultés.",
             "Un site non indexé ou hors de ce périmètre peut exister.", observed_at=state["search_at"])
    if len(state["practical_sources"]) >= 2:
        _add(job, "dispersed_information", state["search_url"],
             "Des informations pratiques figurent sur plusieurs sources tierces consultées.",
             "Leur cohérence, leur exhaustivité et le besoin de centralisation restent à confirmer.")
    with transaction.atomic():
        current = Prospect.objects.select_for_update().get(pk=prospect.pk)
        decision = QualificationReview.objects.select_for_update().filter(prospect=current).first()
        if decision and decision.status in {"approved", "rejected", "excluded", "deferred"} and not state.get("opposed"):
            state["completed_review_id"] = decision.pk
            _save(job)
            return decision
        if _input(current) != state["input"]:
            raise ValueError("La fiche a changé pendant la découverte. Une nouvelle vérification est nécessaire.")
        _save(job)  # Check that this task still owns the running state.
        discovered_site = state["official"][0] if len(state["official"]) == 1 else current.website
        opposed = state.get("opposed") or is_opposed(
            current.nom, current.ville, chosen or current.email, discovered_site)
        status, reasons = "unverified", ["Preuves commerciales ou contact insuffisants dans le périmètre consulté."]
        if opposed:
            proof = next((e for e in state["evidence"] if e["kind"] == "commercial_opposition"), None)
            if proof is None:
                _add(job, "commercial_opposition", "",
                     "Opposition enregistrée correspondant à cet établissement ou à ce contact.",
                     "Rapprochement avec les clés d’exclusion conservées dans Prospect.")
                proof = state["evidence"][-1]
            persist_opposition(current, proof, email=chosen,
                               website=state.get("opposition_site") or discovered_site)
            current.status = "do_not_contact"
            current.next_followup_at = None
            current.save(update_fields=["status", "next_followup_at"])
            status, reasons = "excluded", ["Opposition commerciale conservée."]
        else:
            if len(state["official"]) == 1 and not state.get("ambiguous") and not current.website:
                current.website = state["official"][0]
                current.has_website = True
                current.save(update_fields=["website", "has_website"])
            if contact_state == "corroborated" and not current.email:
                current.email = chosen
                current.email_source = contact["url"]
                current.email_verified_at = timezone.datetime.fromisoformat(contact["observed_at"])
                current.enrichment_status = "found"
                current.save(update_fields=["email", "email_source", "email_verified_at", "enrichment_status"])
            kinds = {e["kind"] for e in state["evidence"]}
            creation = not current.website and not state.get("ambiguous") and "public_search_no_official_site" in kinds and bool(
                kinds & {"third_party_menu", "dispersed_information"})
            technical = bool(current.website) and "missing_viewport" in kinds
            if contact_state == "corroborated" and (creation or technical):
                status = "pending"
                reasons = ["Observation publique documentée et contact corroboré. Pertinence commerciale à examiner."]
        review = _save_review(current, status, reasons, state["evidence"],
                              priority="medium" if status == "pending" else "low")
        state["completed_review_id"] = review.pk
        _save(job)
        prospect.refresh_from_db()
        return review


def discover_prospect(job):
    from .qualification import prospect_is_eligible, _save_review
    prospect = job.prospect
    state = job.payload.get("discovery")
    if state and state.get("completed_review_id"):
        return QualificationReview.objects.get(pk=state["completed_review_id"])
    existing = QualificationReview.objects.filter(prospect=prospect).first()
    if existing and existing.status in {"approved", "rejected", "excluded", "deferred"}:
        return existing
    if not prospect_is_eligible(prospect):
        return _save_review(prospect, "excluded", ["Fiche exclue avant recherche."], [])
    if state is None:
        state = {"input": _input(prospect), "evidence": [], "robots": {}, "official": [],
                 "contacts": [], "practical_sources": [], "index": 0, "pages": None}
        job.payload["discovery"] = state
        _save(job)
    if _input(prospect) != state["input"]:
        raise ValueError("La fiche a changé pendant la découverte.")
    if state["pages"] is None:
        candidates = [prospect.website] if prospect.website else _search(job)
        state["pages"] = [{"url": u} for u in candidates]
        _save(job)
    maximum = settings.DISCOVERY_MAX_CANDIDATES * (1 + settings.DISCOVERY_EXTRA_PAGES)
    while state["index"] < len(state["pages"]):
        entry = state["pages"][state["index"]]
        try:
            response = _read(job, entry["url"])
            extra = _analyse_page(job, entry, response)
        except ConsultationError as exc:
            _add(job, "site_inaccessible", entry["url"],
                 f"Consultation impossible. {exc}",
                 "Ce blocage ne démontre ni défaut durable du site ni besoin commercial.",
                 http_status=exc.http_status, method="Tentative HTTP et contrôle des restrictions de robots.txt.")
            _save(job)
            if exc.http_status in {404, 410}:
                state["ambiguous"] = True
                extra = []
            else:
                raise
        for candidate in extra:
            if len(state["pages"]) >= maximum:
                state["ambiguous"] = True
                break
            if not any(p["url"] == candidate["url"] for p in state["pages"]):
                state["pages"].append(candidate)
        state["index"] += 1
        _save(job)
        if state.get("opposed"):
            break
    return _finish(job, prospect)
