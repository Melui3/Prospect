from datetime import timedelta
import logging
import random

from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from .consultations import ConsultationError, job_consultations
from .models import Campaign, Prospect, QualificationReview, SearchJob
from .run_limits import JobPaused, PilotStopped, guard_job, expire_pilots, stop_campaign

logger = logging.getLogger(__name__)
REPEAT_INTERVAL_DAYS = {7, 14, 30}
OUTCOME_LABELS = {
    "verified": "Succès vérifié",
    "no_results": "Aucun résultat dans le périmètre interrogé",
    "insufficient_evidence": "Preuves insuffisantes",
    "temporary_error": "Erreur temporaire",
    "excluded": "Opposition ou exclusion",
    "permanent_error": "Échec définitif documenté",
    "unrecorded": "Résultat historique non qualifié",
}


def job_outcome(job):
    return job.payload.get("outcome", "unrecorded")


def record_outcome(job, outcome, **details):
    job.payload["outcome"] = outcome
    event = {"at": timezone.now().isoformat(), "outcome": outcome, **details}
    job.payload["events"] = (job.payload.get("events", []) + [event])[-30:]
    checkpoint(job, payload=job.payload)



def checkpoint(job, **values):
    guard_job(job)
    if not SearchJob.objects.filter(pk=job.pk, status="running").exists():
        raise JobPaused()
    for key, value in values.items():
        setattr(job, key, value)
    job.save(update_fields=[*values, "updated_at"])


@transaction.atomic
def enqueue_search(campaign):
    # Acquire the campaign write lock before checking for an active job on SQLite.
    Campaign.objects.filter(pk=campaign.pk).update(status=F("status"))
    if campaign.jobs.filter(pilot_deadline__isnull=False).exists():
        raise ValueError("Un pilote ne peut avoir qu'une occurrence par campagne.")
    active = campaign.jobs.filter(status__in=["queued", "running", "paused"]).first()
    if active and active.stopped_at:
        raise ValueError("Cette campagne est arrêtée ; aucun redémarrage implicite.")
    if active:
        if active.status == "paused":
            active.status = "queued"
            active.stage = "Reprise programmee"
            active.error = ""
            active.save(update_fields=["status", "stage", "error", "updated_at"])
            Campaign.objects.filter(pk=campaign.pk).update(status="queued", error_message="")
        return active
    job = SearchJob.objects.create(campaign=campaign)
    campaign.status = "queued"
    campaign.error_message = ""
    campaign.launched_at = timezone.now()
    campaign.next_search_at = None
    campaign.save(update_fields=["status", "error_message", "launched_at", "next_search_at"])
    return job


def _set_next_search(campaign_id, anchor=None):
    campaign = Campaign.objects.filter(pk=campaign_id).only("pk", "repeat_days").first()
    if not campaign:
        return
    next_search_at = None
    if campaign.repeat_days in REPEAT_INTERVAL_DAYS:
        next_search_at = (anchor or timezone.now()) + timedelta(days=campaign.repeat_days)
    Campaign.objects.filter(pk=campaign_id, repeat_days=campaign.repeat_days).update(next_search_at=next_search_at)


@transaction.atomic
def enqueue_due_scheduled_searches(now=None):
    now = now or timezone.now()
    campaigns = Campaign.objects.select_for_update().filter(
        repeat_days__in=REPEAT_INTERVAL_DAYS,
        next_search_at__lte=now,
    ).order_by("next_search_at", "pk")
    enqueued = 0
    for campaign in campaigns:
        if campaign.jobs.filter(Q(stopped_at__isnull=False) | Q(pilot_deadline__isnull=False)).exists():
            Campaign.objects.filter(pk=campaign.pk).update(repeat_days=0, next_search_at=None)
            continue
        if not Campaign.objects.filter(pk=campaign.pk, next_search_at__lte=now).exists():
            continue
        if campaign.jobs.filter(status__in=["queued", "running", "paused"]).exists():
            continue
        campaign.next_search_at = None
        campaign.save(update_fields=["next_search_at"])
        enqueue_search(campaign)
        enqueued += 1
    return enqueued


@transaction.atomic
def enqueue_enrichment(prospect):
    active = prospect.jobs.filter(status__in=["queued", "running", "paused"]).first()
    if active:
        return active
    return SearchJob.objects.create(prospect=prospect, kind="enrichment", total=1, payload={"force": True})


@transaction.atomic
def enqueue_qualification(prospect, *, discover=False, recheck=False, parent_search=None):
    from .qualification import prospect_is_eligible

    if parent_search:
        guard_job(parent_search)
    if not prospect_is_eligible(prospect):
        return None
    existing = QualificationReview.objects.filter(prospect=prospect).first()
    if existing and not (discover and recheck and existing.status in {"pending", "unverified"}):
        return None
    active = prospect.jobs.filter(kind="qualification", status__in=["queued", "running", "paused"]).first()
    if active:
        return active
    child = SearchJob.objects.create(prospect=prospect, kind="qualification", total=1,
        parent_search=parent_search, payload={"discover": discover})
    if parent_search:
        guard_job(parent_search)
    return child


def process_search(job):
    from .services import OSM_TAGS, _get_city_coords, _query_overpass
    from .identity import capture_prospect
    from .enrichment import enrich_prospect
    payload = job.payload
    campaign = job.campaign
    if "elements" not in payload:
        checkpoint(job, stage="Recherche des entreprises")
        provider = payload.get("company_discovery_provider")
        if provider is None:
            provider = "overpass" if payload.get("overpass") or payload.get("http_sources", {}).get("overpass") else "recherche_entreprises"
            payload["company_discovery_provider"] = provider
            checkpoint(job, payload=payload)
        if provider == "overpass":
            # Already-started historical jobs retain their source and progress.
            coords = _get_city_coords(campaign.ville)
            if not coords:
                raise ValueError(f"Ville introuvable : {campaign.ville}")
            elements = _query_overpass(OSM_TAGS.get(campaign.secteur.lower(), f'"shop"="{campaign.secteur}"'), *coords, campaign.rayon_km * 1000)
        elif provider == "recherche_entreprises":
            from .company_discovery import discover_companies
            elements = discover_companies(job)
        else:
            raise ValueError("Fournisseur de découverte historique inconnu : reprise bloquée.")
        if job.pilot_deadline is not None:
            payload["pilot_omitted_count"] = max(0, len(elements)-5) + payload.get("company_discovery", {}).get("limit_omitted", 0)
            elements = elements[:5]
        payload.update({"elements": elements, "capture_index": 0, "ids": [], "enrich_index": 0})
        checkpoint(job, payload=payload, total=len(elements), stage="Enregistrement des pistes")
    for index in range(payload["capture_index"], len(payload["elements"])):
        checkpoint(job, stage="Enregistrement des pistes")
        item = capture_prospect(campaign, payload["elements"][index])
        if item and item.pk not in payload["ids"]:
            payload["ids"].append(item.pk)
        payload["capture_index"] = index + 1
        checkpoint(job, payload=payload)
    checkpoint(job, total=len(payload["ids"]), stage="Recherche des emails")
    for index in range(payload["enrich_index"], len(payload["ids"])):
        checkpoint(job, stage="Recherche des emails")
        item = Prospect.objects.filter(pk=payload["ids"][index], merged_into=None).first()
        if item:
            from .qualification import prospect_is_eligible
            if prospect_is_eligible(item):
                enqueue_qualification(item, discover=True, parent_search=job)
            else:
                payload.setdefault("excluded_ids", [])
                if item.pk not in payload["excluded_ids"]:
                    payload["excluded_ids"].append(item.pk)
        payload["enrich_index"] = index + 1
        with_email = Prospect.objects.filter(pk__in=payload["ids"]).exclude(email=None).exclude(email="").count()
        checkpoint(job, payload=payload, processed=index + 1, with_email=with_email)


def run_next_job():
    expire_pilots()
    enqueue_due_scheduled_searches()
    now = timezone.now()
    ready = SearchJob.objects.filter(status="queued", next_run_at__lte=now)
    job_id = ready.order_by("created_at", "pk").values_list("pk", flat=True).first()
    if job_id is None:
        return False
    # Keep the read outside a write transaction. SQLite cannot always upgrade
    # a read transaction when the desktop API is writing to the same database.
    claimed = ready.filter(pk=job_id).update(
        status="running", error="",
        stage="En cours", updated_at=now,
    )
    if not claimed:
        return False
    job = SearchJob.objects.get(pk=job_id)
    if job.campaign:
        Campaign.objects.filter(pk=job.campaign_id).update(status="running", error_message="")
    try:
        with job_consultations(job):
            _process_job(job)
    except PilotStopped as exc:
        stop_campaign(exc.campaign_id, str(exc))
    except JobPaused:
        if job.campaign:
            state = SearchJob.objects.filter(pk=job.pk).values_list("status", flat=True).first()
            Campaign.objects.filter(pk=job.campaign_id).update(status=state or "paused")
    except Exception as exc:
        deferred = isinstance(exc, ConsultationError) and exc.deferred
        temporary = (
            exc.temporary if isinstance(exc, ConsultationError) else not isinstance(exc, ValueError)
        )
        attempts = job.attempts + (0 if deferred else 1)
        retry = temporary and attempts < 3
        delay = min(900, 30 * 2 ** min(attempts, 5)) + random.uniform(0, 5)
        deadline = timezone.now() + timedelta(seconds=delay)
        if isinstance(exc, ConsultationError) and exc.retry_at:
            deadline = exc.retry_at if deferred else max(deadline, exc.retry_at)
        outcome = "temporary_error" if retry else "permanent_error"
        event = {"at": timezone.now().isoformat(), "outcome": outcome,
                 "source": getattr(exc, "source", ""), "http_status": getattr(exc, "http_status", None),
                 "reason": str(exc)[:1000], "retry_at": deadline.isoformat() if retry else None}
        job.payload["events"] = (job.payload.get("events", []) + [event])[-30:]
        job.payload["outcome"] = outcome
        changed = SearchJob.objects.filter(pk=job.pk, status="running").update(
            status="queued" if retry else "error", error=str(exc)[:1000], attempts=attempts,
            stage=OUTCOME_LABELS[outcome], payload=job.payload,
            next_run_at=deadline, updated_at=timezone.now(),
        )
        logger.warning("Tâche %s résultat=%s source=%s HTTP=%s reprise=%s",
                       job.pk, outcome, event["source"], event["http_status"], event["retry_at"])
        if changed and job.campaign:
            Campaign.objects.filter(pk=job.campaign_id).update(
                status="queued" if retry else "error", error_message=str(exc)[:1000])
            if not retry:
                _set_next_search(job.campaign_id)
    return True


def _process_job(job):
    from .enrichment import enrich_prospect

    if job.kind == "search":
        process_search(job)
        outcome = "no_results"
        if job.payload.get("ids"):
            all_excluded = set(job.payload["ids"]) <= set(job.payload.get("excluded_ids", []))
            outcome = "excluded" if all_excluded else "insufficient_evidence"
        administrative = job.payload.get("company_discovery", {})
        if not job.payload.get("ids") and administrative.get("returned_units", 0):
            rejections = administrative.get("rejections", {})
            excluded = set(rejections) <= {"commercial_opposition", "existing_opposition", "diffusion_restricted_or_unknown"}
            outcome = "excluded" if rejections and excluded else "insufficient_evidence"
        final_stage = ("Recherche terminée, qualification séparée" if outcome == "insufficient_evidence" and job.payload.get("ids")
                       else OUTCOME_LABELS[outcome])
    elif job.kind == "qualification":
        from .qualification import opportunity, qualify_prospect
        if job.payload.get("discover"):
            from .discovery import discover_prospect
            review = discover_prospect(job)
        else:
            review = qualify_prospect(job.prospect)
        final_stage = {
            "pending": "Proposition a examiner",
            "excluded": "Fiche exclue",
            "no_opportunity": "Aucun signal pertinent",
            "unverified": "À enrichir",
        }.get(review.status, "Qualification deja decidee")
        outcome = "insufficient_evidence"
        if review.status in {"excluded", "rejected"}:
            outcome = "excluded"
        elif opportunity(review):
            outcome = "verified"
        from .drafts import prepare_selected_missing
        guard_job(job)
        root = job.parent_search
        job.payload["draft_preparation"] = prepare_selected_missing(
            prospect_ids=root.payload.get("ids", []) if root and root.pilot_deadline else None)
        checkpoint(job, processed=1)
    elif job.kind == "enrichment":
        enrich_prospect(job.prospect, force=job.payload.get("force", False))
        if job.prospect.enrichment_status == "error":
            from .services import ProspectionTemporaryError
            raise ProspectionTemporaryError("Le site ne repond pas. Recherche d'email a retenter.")
        outcome = "verified" if job.prospect.email else "no_results"
        final_stage = "Email trouvé, qualification séparée" if job.prospect.email else "Aucun email trouvé dans le périmètre"
        checkpoint(job, processed=1, with_email=int(bool(job.prospect.email)))
    else:
        raise ValueError("Type de tâche inconnu.")
    record_outcome(job, outcome)
    checkpoint(job, stage=final_stage)
    completed = SearchJob.objects.filter(pk=job.pk, status="running").update(status="done", updated_at=timezone.now())
    if completed and job.campaign:
        Campaign.objects.filter(pk=job.campaign_id).update(status="done", error_message="")
        _set_next_search(job.campaign_id)



def recover_jobs():
    expire_pilots()
    # Preserve provider deadlines and retry budgets across worker restarts.
    for job in SearchJob.objects.filter(status="running", attempts__gte=3):
        job.payload["outcome"] = "permanent_error"
        job.payload["events"] = (job.payload.get("events", []) + [{
            "at": timezone.now().isoformat(), "outcome": "permanent_error",
            "reason": "Budget de tentatives épuisé avant le redémarrage.",
        }])[-30:]
        SearchJob.objects.filter(pk=job.pk, status="running").update(
            status="error", stage=OUTCOME_LABELS["permanent_error"], payload=job.payload,
            error="Budget de tentatives épuisé avant le redémarrage.", updated_at=timezone.now())
    SearchJob.objects.filter(status="running").update(
        status="queued", stage="Reprise apres redemarrage", updated_at=timezone.now())
    for campaign in Campaign.objects.filter(status="running"):
        latest = campaign.jobs.order_by("-created_at", "-pk").first()
        if latest:
            Campaign.objects.filter(pk=campaign.pk).update(status=latest.status, error_message=latest.error)
        else:
            job = enqueue_search(campaign)
            job.status = "paused"
            job.stage = "Ancienne recherche interrompue : reprise manuelle"
            job.save(update_fields=["status", "stage"])
            Campaign.objects.filter(pk=campaign.pk).update(status="paused")
