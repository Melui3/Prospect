"""Persisted consultation budgets and provider deadlines for the local worker."""
import hashlib
import json
import logging
import time
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import timedelta, timezone as datetime_timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .cache import cache_key, cached_value, store_value
from .models import SearchJob, ServiceCache

logger = logging.getLogger(__name__)
_current_job = ContextVar("consultation_job", default=None)
_execution_deadline = ContextVar("consultation_deadline", default=None)


class ConsultationError(Exception):
    def __init__(self, message, *, temporary=False, retry_at=None, deferred=False,
                 source="", http_status=None):
        super().__init__(message)
        self.temporary = temporary
        self.retry_at = retry_at
        self.deferred = deferred
        self.source = source
        self.http_status = http_status


@contextmanager
def job_consultations(job):
    from .run_limits import guard_job
    guard_job(job)
    token = _current_job.set(job)
    deadline_token = _execution_deadline.set(
        time.monotonic() + settings.ENRICHMENT_TOTAL_TIMEOUT)
    try:
        yield
    finally:
        _execution_deadline.reset(deadline_token)
        _current_job.reset(token)


def retry_after(value, now):
    try:
        seconds = int(value)
        return now + timedelta(seconds=max(0, seconds))
    except (TypeError, ValueError, OverflowError):
        try:
            date = parsedate_to_datetime(value)
            if date.tzinfo is None:
                date = date.replace(tzinfo=datetime_timezone.utc)
            return max(now, date)
        except (TypeError, ValueError, OverflowError):
            return now + timedelta(seconds=60)


def _save_payload(job):
    if not SearchJob.objects.filter(pk=job.pk, status="running").update(payload=job.payload):
        raise ConsultationError("Traitement suspendu avant consultation.", source="worker")


def _reserve(source, domain, minimum_interval=0):
    now = timezone.now()
    window = getattr(settings, "HTTP_BUDGET_WINDOW", 3600)
    limits = [
        ("source:" + source, getattr(settings, "HTTP_SOURCE_BUDGET", 60),
         getattr(settings, "HTTP_SOURCE_INTERVAL", 1.1)),
        ("domain:" + domain, getattr(settings, "HTTP_DOMAIN_BUDGET", 30),
         max(getattr(settings, "HTTP_DOMAIN_INTERVAL", 1.1), minimum_interval)),
    ]
    if source == "pages_jaunes":
        limits[0] = (limits[0][0], limits[0][1],
                     max(limits[0][2], settings.PAGES_JAUNES_DELAY_SECONDS))
    # Both counters are reserved before any external request.
    with transaction.atomic():
        entries = []
        for scope, budget, interval in limits:
            item, _ = ServiceCache.objects.get_or_create(
                key=cache_key("http-budget:" + scope),
                defaults={"value": {}, "expires_at": now + timedelta(seconds=window)},
            )
            value = dict(item.value)
            if item.expires_at <= now:
                value = {}
                item.expires_at = now + timedelta(seconds=window)
            deadline = timezone.datetime.fromisoformat(value["not_before"]) if value.get("not_before") else now
            if value.get("count", 0) >= budget:
                deadline = max(deadline, item.expires_at)
            if deadline > now:
                raise ConsultationError(
                    f"Consultation différée pour {source} ({domain}).",
                    temporary=True, deferred=True, retry_at=deadline, source=source,
                )
            entries.append((item, value, interval))
        for item, value, interval in entries:
            value["count"] = value.get("count", 0) + 1
            value["not_before"] = (now + timedelta(seconds=interval)).isoformat()
            item.value = value
            item.save(update_fields=["value", "expires_at"])


def _cooldown(source, domain, deadline):
    with transaction.atomic():
        for scope in ("source:" + source, "domain:" + domain):
            item = ServiceCache.objects.get(key=cache_key("http-budget:" + scope))
            value = dict(item.value)
            previous = timezone.datetime.fromisoformat(value["not_before"])
            value["not_before"] = max(previous, deadline).isoformat()
            item.value = value
            # Keep a provider deadline even when the budget window expires.
            item.expires_at = max(item.expires_at, deadline)
            item.save(update_fields=["value", "expires_at"])


def _cache_response(key, response):
    if key and len(response.content) <= 1024 * 1024:
        store_value(key, {
            "status": response.status_code, "url": response.url, "body": response.text,
            "observed_at": response.prospect_observed_at,
            "headers": {"Content-Type": response.headers.get("Content-Type", ""),
                        "Location": response.headers.get("Location", "")},
        }, hours=24)


def request(method, url, *, source, minimum_interval=0, before_send=None,
            validate_response=None, cache_response=True, **kwargs):
    from .run_limits import guard_current
    root = guard_current()
    domain = (urlsplit(url).hostname or "").lower()
    job = _current_job.get()
    fingerprint = hashlib.sha256(json.dumps(
        [method, url, kwargs.get("params"), str(kwargs.get("data", "")), kwargs.get("json")],
        sort_keys=True, default=str,
    ).encode()).hexdigest()
    key = f"http-response:{job.pk}:{fingerprint}" if job and cache_response else ""
    saved = cached_value(key) if key else None
    if saved and saved.get("observed_at"):
        response = requests.Response()
        response.status_code = saved["status"]
        response.url = saved["url"]
        response.headers.update(saved["headers"])
        response._content = saved["body"].encode("utf-8")
        response.encoding = "utf-8"
        response.prospect_observed_at = saved.get("observed_at", timezone.now().isoformat())
        if response.status_code in {404, 410}:
            raise ConsultationError(f"{source} ({domain}) répond HTTP {response.status_code}.",
                                    source=source, http_status=response.status_code)
        if validate_response:
            try:
                validate_response(response)
            except ConsultationError:
                ServiceCache.objects.filter(key=cache_key(key)).delete()
                raise
        return response
    if job and job.payload.get("http_count", 0) >= getattr(settings, "HTTP_JOB_BUDGET", 500):
        raise ConsultationError("Budget total de consultation atteint pour cette tâche.", source=source)
    source_setting = {
        "website": "WEBSITE_EMAIL_MAX_LOOKUPS",
        "pages_jaunes": "PAGES_JAUNES_MAX_LOOKUPS",
        "social_search": "SOCIAL_SEARCH_MAX_LOOKUPS",
        "discovery_search": "DISCOVERY_SEARCH_MAX_QUERIES",
    }.get(source)
    counts = job.payload.get("http_sources", {}) if job else {}
    if job and source_setting and counts.get(source, 0) >= getattr(settings, source_setting):
        raise ConsultationError(f"Budget de consultation {source} épuisé pour cette tâche.",
                                source=source)
    deadline = _execution_deadline.get()
    if deadline is not None:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ConsultationError("Durée de consultation atteinte pour ce passage.",
                                    temporary=True, deferred=True,
                                    retry_at=timezone.now() + timedelta(seconds=60), source=source)
        kwargs["timeout"] = min(kwargs.get("timeout", remaining), remaining)
    if root and root.pilot_deadline:
        kwargs["timeout"] = min(kwargs.get("timeout", 1200),
                                (root.pilot_deadline-timezone.now()).total_seconds())
    _reserve(source, domain, minimum_interval)
    if job:
        job.payload["http_count"] = job.payload.get("http_count", 0) + 1
        counts[source] = counts.get(source, 0) + 1
        job.payload["http_sources"] = counts
        _save_payload(job)
    if before_send is not None:
        before_send()
    guard_current()
    try:
        kwargs.setdefault("allow_redirects", False)
        response = requests.request(method, url, **kwargs)
    except requests.RequestException as exc:
        logger.warning("Consultation réseau indisponible source=%s domaine=%s type=%s",
                       source, domain, type(exc).__name__)
        raise ConsultationError(f"Réseau indisponible pour {source} ({domain}).",
                                temporary=True, source=source) from exc
    guard_current()
    response.prospect_observed_at = timezone.now().isoformat()
    code = response.status_code
    if code == 429 or code >= 500:
        deadline = retry_after(response.headers.get("Retry-After"), timezone.now())
        _cooldown(source, domain, deadline)
        logger.warning("Consultation temporairement refusée source=%s domaine=%s HTTP=%s",
                       source, domain, code)
        raise ConsultationError(f"{source} ({domain}) répond HTTP {code}.",
                                temporary=True, retry_at=deadline, source=source, http_status=code)
    if 300 <= code < 400 and source != "website":
        raise ConsultationError(
            f"Redirection de {source} à vérifier avant de poursuivre.", source=source, http_status=code)
    if code >= 400:
        if code in {404, 410}:
            _cache_response(key, response)
        raise ConsultationError(f"{source} ({domain}) répond HTTP {code}.",
                                source=source, http_status=code)
    if 200 <= code < 300 or source == "website" and code in {301, 302, 303, 307, 308}:
        if validate_response:
            validate_response(response)
        _cache_response(key, response)
    return response
