"""Controls for existing search jobs. No network, no independent execution engine."""
from datetime import timedelta
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone
from .models import Campaign, SearchJob

ACTIVE = ('queued', 'running', 'paused')

class JobPaused(Exception):
    pass


class PilotStopped(JobPaused):
    def __init__(self, root, reason):
        self.root_id = root.pk
        self.campaign_id = root.campaign_id
        super().__init__(reason)


def root_for(job):
    root_id = job.pk if job.kind == 'search' else job.parent_search_id
    return SearchJob.objects.filter(pk=root_id).first() if root_id else None


def guard_job(job, *, running=True):
    root = root_for(job)
    if root is None:
        return None
    if root.stopped_at is not None:
        raise PilotStopped(root, 'Campagne arrêtée. Ses travaux ne peuvent pas reprendre.')
    if root.pilot_deadline is not None and timezone.now() >= root.pilot_deadline:
        raise PilotStopped(root, 'Pilote arrêté : échéance absolue de 20 minutes atteinte.')
    if running and not SearchJob.objects.filter(pk=job.pk, status='running').exists():
        raise JobPaused()
    return root


def guard_current():
    from .consultations import _current_job
    job = _current_job.get()
    return guard_job(job) if job else None


@transaction.atomic
def schedule_pilot(campaign, start_at):
    if timezone.is_naive(start_at) or start_at <= timezone.now():
        raise ValueError('Une échéance future avec fuseau horaire est nécessaire.')
    Campaign.objects.filter(pk=campaign.pk).update(repeat_days=F('repeat_days'))
    if campaign.jobs.filter(pilot_deadline__isnull=False).exists() or campaign.jobs.filter(status__in=ACTIVE).exists():
        raise ValueError('Cette campagne a déjà un pilote ou des travaux actifs.')
    Campaign.objects.filter(pk=campaign.pk).update(repeat_days=0, next_search_at=None, status='queued')
    return SearchJob.objects.create(campaign=campaign, next_run_at=start_at,
        pilot_deadline=start_at+timedelta(minutes=20), stage='Pilote planifié, une occurrence')


def unresolved_children(campaign_id):
    captured = {pk for root in SearchJob.objects.filter(campaign_id=campaign_id, kind='search')
                for pk in root.payload.get('ids', [])}
    return SearchJob.objects.filter(parent_search=None, campaign=None,
        kind='qualification', prospect_id__in=captured, status__in=ACTIVE)


@transaction.atomic
def stop_campaign(campaign_id, reason='Campagne arrêtée explicitement'):
    if campaign_id is None:
        return []
    Campaign.objects.filter(pk=campaign_id).update(repeat_days=0, next_search_at=None, status='paused')
    root_ids = list(SearchJob.objects.filter(campaign_id=campaign_id, kind='search').values_list('pk', flat=True))
    now = timezone.now()
    SearchJob.objects.filter(pk__in=root_ids, stopped_at=None).update(stopped_at=now)
    SearchJob.objects.filter(Q(pk__in=root_ids) | Q(parent_search_id__in=root_ids),
        status__in=ACTIVE).update(status='paused', stage=reason[:80], updated_at=now)
    # Missing provenance is not inferred from a shared prospect or timestamps.
    # Return a diagnostic without rolling back the stop of the known family.
    return list(unresolved_children(campaign_id).values_list('pk', flat=True))


def expire_pilots():
    for campaign_id in SearchJob.objects.filter(kind='search', stopped_at=None,
            pilot_deadline__lte=timezone.now()).values_list('campaign_id', flat=True).distinct():
        stop_campaign(campaign_id, 'Pilote arrêté : échéance de 20 minutes')


def reserve_pilot_attempt():
    root = guard_current()
    if root is None or root.pilot_deadline is None:
        return
    changed = SearchJob.objects.filter(pk=root.pk, stopped_at=None,
        pilot_deadline__gt=timezone.now(), pilot_tavily_attempts__lt=5).update(
            pilot_tavily_attempts=F('pilot_tavily_attempts')+1)
    if not changed:
        raise PilotStopped(root, 'Pilote arrêté : plafond de 5 tentatives Tavily ou échéance atteint.')
