from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import Campaign, Prospect, QualificationReview, SearchJob

REPEAT_INTERVAL_DAYS = {7, 14, 30}


class JobPaused(Exception):
    pass


def checkpoint(job, **values):
    if not SearchJob.objects.filter(pk=job.pk, status="running").exists():
        raise JobPaused()
    for key, value in values.items():
        setattr(job, key, value)
    job.save(update_fields=[*values, "updated_at"])


@transaction.atomic
def enqueue_search(campaign):
    active = campaign.jobs.filter(status__in=["queued", "running", "paused"]).first()
    if active:
        if active.status == "paused":
            active.status = "queued"
            active.stage = "Reprise programmee"
            active.error = ""
            active.attempts = 0
            active.next_run_at = timezone.now()
            active.save(update_fields=["status", "stage", "error", "attempts", "next_run_at", "updated_at"])
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
    Campaign.objects.filter(pk=campaign_id).update(next_search_at=next_search_at)


@transaction.atomic
def enqueue_due_scheduled_searches(now=None):
    now = now or timezone.now()
    campaigns = Campaign.objects.select_for_update().filter(
        repeat_days__in=REPEAT_INTERVAL_DAYS,
        next_search_at__lte=now,
    ).order_by("next_search_at", "pk")
    enqueued = 0
    for campaign in campaigns:
        if not Campaign.objects.filter(pk=campaign.pk, next_search_at__lte=now).exists():
            continue
        campaign.next_search_at = None
        campaign.save(update_fields=["next_search_at"])
        if campaign.jobs.filter(status__in=["queued", "running", "paused"]).exists():
            continue
        enqueue_search(campaign)
        enqueued += 1
    return enqueued


@transaction.atomic
def enqueue_enrichment(prospect):
    active = prospect.jobs.filter(status__in=["queued", "running", "paused"]).first()
    if active:
        return active
    return SearchJob.objects.create(prospect=prospect, kind="enrichment", total=1, payload={"force": True})


def enqueue_qualification(prospect):
    from .qualification import prospect_is_eligible

    if not prospect_is_eligible(prospect) or QualificationReview.objects.filter(prospect=prospect).exists():
        return None
    active = prospect.jobs.filter(kind="qualification", status__in=["queued", "running", "paused"]).first()
    if active:
        return active
    return SearchJob.objects.create(prospect=prospect, kind="qualification", total=1)


def process_search(job):
    from .services import OSM_TAGS, _get_city_coords, _query_overpass
    from .identity import capture_prospect
    from .enrichment import enrich_prospect
    payload = job.payload
    campaign = job.campaign
    if "elements" not in payload:
        checkpoint(job, stage="Recherche des entreprises")
        coords = _get_city_coords(campaign.ville)
        if not coords:
            raise ValueError(f"Ville introuvable : {campaign.ville}")
        elements = _query_overpass(OSM_TAGS.get(campaign.secteur.lower(), f'"shop"="{campaign.secteur}"'), *coords, campaign.rayon_km * 1000)
        payload = {"elements": elements, "capture_index": 0, "ids": [], "enrich_index": 0}
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
            enrich_prospect(item)
            enqueue_qualification(item)
        payload["enrich_index"] = index + 1
        with_email = Prospect.objects.filter(pk__in=payload["ids"]).exclude(email=None).exclude(email="").count()
        checkpoint(job, payload=payload, processed=index + 1, with_email=with_email)


def run_next_job():
    from .enrichment import enrich_prospect
    enqueue_due_scheduled_searches()
    with transaction.atomic():
        job = SearchJob.objects.filter(status="queued", next_run_at__lte=timezone.now()).order_by("created_at").first()
        if not job:
            return False
        job.status = "running"
        job.attempts += 1
        job.error = ""
        job.save(update_fields=["status", "attempts", "error", "updated_at"])
    if job.campaign:
        Campaign.objects.filter(pk=job.campaign_id).update(status="running", error_message="")
    try:
        if job.kind == "search":
            process_search(job)
        elif job.kind == "qualification":
            from .qualification import qualify_prospect
            qualify_prospect(job.prospect)
            checkpoint(job, processed=1)
        else:
            enrich_prospect(job.prospect, force=job.payload.get("force", False))
            if job.prospect.enrichment_status == "error":
                from .services import ProspectionTemporaryError
                raise ProspectionTemporaryError("Le site ne repond pas. Recherche d'email a retenter.")
            checkpoint(job, processed=1, with_email=int(bool(job.prospect.email)))
        checkpoint(job, stage="Terminee")
        completed = SearchJob.objects.filter(pk=job.pk, status="running").update(status="done", updated_at=timezone.now())
        if completed and job.campaign:
            Campaign.objects.filter(pk=job.campaign_id).update(status="done", error_message="")
            _set_next_search(job.campaign_id)
    except JobPaused:
        if job.campaign:
            state = SearchJob.objects.filter(pk=job.pk).values_list("status", flat=True).first()
            Campaign.objects.filter(pk=job.campaign_id).update(status=state or "paused")
    except Exception as exc:
        retry = job.attempts < 3 and not isinstance(exc, ValueError)
        changed = SearchJob.objects.filter(pk=job.pk, status="running").update(
            status="queued" if retry else "error", error=str(exc)[:1000],
            stage="Nouvelle tentative programmee" if retry else "Interrompue",
            next_run_at=timezone.now() + timedelta(seconds=30 * job.attempts), updated_at=timezone.now(),
        )
        if changed and job.campaign:
            Campaign.objects.filter(pk=job.campaign_id).update(status="queued" if retry else "error", error_message=str(exc)[:1000])
            if not retry:
                _set_next_search(job.campaign_id)
    return True


def recover_jobs():
    SearchJob.objects.filter(status="running").update(status="queued", stage="Reprise apres redemarrage", next_run_at=timezone.now())
    for campaign in Campaign.objects.filter(status="running"):
        if not campaign.jobs.filter(status__in=["queued", "paused"]).exists():
            job = enqueue_search(campaign)
            job.status = "paused"
            job.stage = "Ancienne recherche interrompue : reprise manuelle"
            job.save(update_fields=["status", "stage"])
            Campaign.objects.filter(pk=campaign.pk).update(status="paused")
