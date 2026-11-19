"""Read-only commercial shortlist with explicit, dated evidence criteria."""
import hashlib
import ipaddress
import json
from collections import Counter
from datetime import timedelta
from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db.models import Exists, OuterRef
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .identity import normalized
from .models import EmailLog, Prospect
from .qualification import _identity, _site, prospect_is_eligible

LIMIT = 5
POLICY_VERSION = "2026-11-19"
SERVICES_URL = "https://nathaniel-dev.fr/services/"
SERVICES_VERIFIED_AT = "2026-11-19"
SIGNALS = [
    ("third_party_menu", "Carte publiée chez un tiers", "landing-page", "Landing page",
     "Une page dédiée peut présenter la carte et les informations de contact. Le besoin reste à confirmer."),
    ("dispersed_information", "Informations pratiques sur plusieurs sources", "site-vitrine", "Site vitrine",
     "Un site vitrine peut réunir les informations pratiques. Leur dispersion ne prouve pas une difficulté pour les clients."),
    ("missing_viewport", "Indicateur HTML d’adaptation mobile à vérifier", "site-vitrine", "Site vitrine",
     "La prestation inclut le responsive. L’observation justifie une vérification ciblée, sans démontrer un défaut visuel."),
]


def _public_url(url):
    try:
        parts = urlsplit(url or "")
        host = parts.hostname or ""
        if parts.scheme not in {"http", "https"} or not host or parts.username or parts.password:
            return False
        if host == "localhost" or host.endswith((".local", ".localhost", ".internal")) or "." not in host:
            return False
        try:
            return ipaddress.ip_address(host).is_global
        except ValueError:
            return True
    except (ValueError, TypeError):
        return False


def _valid_evidence(review, now, max_age_days):
    rows = []
    for item in review.evidence:
        if not isinstance(item, dict) or item.get("historical"):
            continue
        if item.get("origin") not in {"automatic", "human", "assisted"}:
            continue
        if not _public_url(item.get("url")) or not all(item.get(k) for k in ("source", "detail", "method", "limits")):
            continue
        try:
            date = parse_datetime(item.get("observed_at", ""))
        except (TypeError, ValueError):
            continue
        if date is None or timezone.is_naive(date) or not now-timedelta(days=max_age_days) <= date <= now:
            continue
        company = item.get("company")
        if item.get("origin") == "automatic" and not company:
            continue
        if company and (company.get("id") != review.prospect_id or
                        normalized(company.get("name")) != normalized(review.prospect.nom) or
                        normalized(company.get("city")) != normalized(review.prospect.ville)):
            continue
        rows.append((item, date))
    return rows


def _evaluate(review, now, max_age_days):
    if review.status != "pending":
        return None, "decision_or_status"
    if not prospect_is_eligible(review.prospect):
        return None, "exclusion_or_outreach"
    try:
        validate_email(review.prospect.email or "")
    except ValidationError:
        return None, "contact_invalid"
    rows = _valid_evidence(review, now, max_age_days)
    contacts = [(e, date) for e, date in rows if e.get("kind") == "corroborated_contact" and
                (e.get("email") or "").casefold() == (review.prospect.email or "").casefold() and
                e.get("identity") == _identity(review.prospect)]
    if not contacts:
        return None, "contact_unverified_or_stale"
    contact = max(contacts, key=lambda row: row[1])
    for order, (kind, label, service_id, service_title, fit) in enumerate(SIGNALS):
        supporting = [(e, date) for e, date in rows if e.get("kind") == kind]
        if not supporting:
            continue
        supporting = [max(supporting, key=lambda row: row[1])]
        if kind == "missing_viewport":
            if not _site(review.prospect) or supporting[0][0].get("input_website") != _site(review.prospect):
                continue
        else:
            searches = [(e, date) for e, date in rows if e.get("kind") == "public_search_no_official_site"]
            if review.prospect.website or not searches:
                continue
            supporting.append(max(searches, key=lambda row: row[1]))
        supporting.append(contact)
        oldest = min(date for _, date in supporting)
        source_count = len({urlsplit(e["url"]).hostname.lower().removeprefix("www.")
                            for e, _ in supporting if e.get("kind") != "public_search_no_official_site"})
        proof = []
        for e, _ in supporting:
            reference = e.get("id") or hashlib.sha256(json.dumps(
                [e.get("kind"), e["url"], e["observed_at"], e["detail"]],
                sort_keys=True).encode()).hexdigest()[:24]
            proof.append({"id": reference, "kind": e["kind"], "source": e["source"],
                          "url": e["url"], "observed_at": e["observed_at"],
                          "detail": e["detail"], "origin": e["origin"]})
        info = {
            "signal": label,
            "service": {"id": service_id, "title": service_title, "url": SERVICES_URL,
                        "verified_at": SERVICES_VERIFIED_AT},
            "fit": fit, "source_count": source_count,
            "oldest_required_evidence_at": oldest.isoformat(),
            "reasons": [label, f"Contact publié et corroboré. {source_count} source(s) distincte(s) hors moteur de recherche.",
                        f"Les preuves nécessaires ont au plus {max_age_days} jours."],
            "limits": list(dict.fromkeys(e["limits"] for e, _ in supporting)),
            "evidence": proof,
        }
        return ((order, -source_count, -oldest.timestamp(), review.pk), info), None
    return None, "business_evidence_insufficient_or_stale"


def _duplicate_keys(prospect):
    keys = [("record", prospect.pk)]
    name = " ".join(w for w in normalized(prospect.nom).split() if w not in {"sarl", "sas", "eurl", "sasu"})
    if name and normalized(prospect.ville):
        keys.append(("company", name, normalized(prospect.ville)))
    if prospect.email:
        keys.append(("email", prospect.email.strip().casefold()))
    if prospect.external_id:
        keys.append(("external", prospect.external_id))
    if prospect.merged_into_id:
        keys.append(("record", prospect.merged_into_id))
    host = (urlsplit(prospect.website or "").hostname or "").lower().removeprefix("www.")
    shared = set(settings.DISCOVERY_DIRECTORY_HOSTS) | {
        "facebook.com", "instagram.com", "linkedin.com", "github.io", "wixsite.com", "wordpress.com", "blogspot.com"}
    if host and not any(host == domain or host.endswith("." + domain) for domain in shared):
        keys.append(("domain", host))
    return keys


def _duplicate_groups(prospects):
    neighbours = {p.pk: set() for p in prospects}
    seen = {}
    for prospect in prospects:
        for key in _duplicate_keys(prospect):
            prior = seen.setdefault(key, prospect.pk)
            neighbours[prospect.pk].add(prior)
            neighbours[prior].add(prospect.pk)
    groups = {}
    for pk in neighbours:
        if pk in groups:
            continue
        pending = [pk]
        while pending:
            member = pending.pop()
            if member in groups:
                continue
            groups[member] = pk
            pending.extend(neighbours[member] - groups.keys())
    return groups


def select_opportunities(reviews, *, now=None):
    now = now or timezone.now()
    max_age_days = settings.SELECTION_EVIDENCE_MAX_AGE_DAYS
    prospects = list(Prospect.objects.annotate(
        has_outreach_attempt=Exists(EmailLog.objects.filter(prospect_id=OuterRef("pk")))))
    groups = _duplicate_groups(prospects)
    decisions = {r.prospect_id: r.status for r in reviews}
    protected = set()
    for p in prospects:
        if (p.status != "new" or p.last_contacted_at or p.has_outreach_attempt or
                decisions.get(p.pk) in {"approved", "rejected", "deferred", "excluded"}):
            protected.add(groups[p.pk])
    omitted = Counter()
    eligible = []
    for review in reviews:
        if groups.get(review.prospect_id) in protected:
            omitted["human_decision_or_contacted_duplicate"] += 1
            continue
        result, reason = _evaluate(review, now, max_age_days)
        if result is None:
            omitted[reason] += 1
        else:
            key, info = result
            eligible.append((key, review, info))
    eligible.sort(key=lambda row: row[0])
    unique = []
    used = set()
    for _, review, info in eligible:
        group = groups[review.prospect_id]
        if group in used:
            omitted["duplicate"] += 1
            continue
        used.add(group)
        unique.append((review, info))
    chosen = unique[:LIMIT]
    metadata = {}
    for rank, (review, info) in enumerate(chosen, start=1):
        metadata[review.pk] = {**info, "rank": rank}
    policy = {
        "limit": LIMIT, "selected_count": len(chosen), "eligible_count": len(eligible),
        "unique_count": len(unique), "held_by_limit": max(0, len(unique)-LIMIT),
        "omitted_counts": dict(omitted), "max_evidence_age_days": max_age_days,
        "policy_version": POLICY_VERSION, "services_url": SERVICES_URL,
        "criteria": [
            "Carte tierce, puis informations dispersées, puis indicateur HTML limité.",
            "À signal égal, nombre de sources distinctes hors moteur de recherche.",
            "Puis fraîcheur de la plus ancienne preuve nécessaire, puis identifiant stable.",
        ],
    }
    return [review for review, _ in chosen], metadata, policy
