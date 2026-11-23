"""Interchangeable discovery transport. Results are candidates, never commercial proof."""
import calendar
from datetime import timedelta
from urllib.parse import urlsplit, urlunsplit

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .cache import cache_key, cached_value, store_value
from .consultations import ConsultationError, request
from .models import ServiceCache

TAVILY_URL = 'https://api.tavily.com/search'


@transaction.atomic
def _reserve_tavily_credit():
    # Ledger keys contain the calendar period, not the cache TTL: cleanup must not
    # reset spending in the middle of a month. Reserve uncertain/failed calls too.
    from .run_limits import reserve_pilot_attempt
    reserve_pilot_attempt()
    now = timezone.now()
    local = timezone.localtime(now)
    tomorrow = (local + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    next_month = (local.replace(day=calendar.monthrange(local.year, local.month)[1]) + timedelta(days=1)).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0)
    periods = [('day', local.strftime('%Y-%m-%d'), settings.TAVILY_DAILY_LIMIT, tomorrow),
               ('month', local.strftime('%Y-%m'), settings.TAVILY_MONTHLY_LIMIT, next_month)]
    with transaction.atomic():
        rows = []
        for period, identifier, limit, until in periods:
            item, _ = ServiceCache.objects.get_or_create(key=cache_key(f'tavily-credit:{period}:{identifier}'),
                defaults={'value': {'count': 0}, 'expires_at': next_month + timedelta(days=370)})
            # Obtain a write lock before the read, including on SQLite.
            ServiceCache.objects.filter(pk=item.pk).update(expires_at=F('expires_at'))
            item.refresh_from_db()
            count = item.value.get('count', 0)
            if limit <= 0 or count >= limit:
                raise ConsultationError(f'Budget Tavily {"journalier" if period == "day" else "mensuel"} atteint. Aucune recherche effectuée.',
                    temporary=True, deferred=True, retry_at=until, source='tavily_search')
            rows.append((item, count))
        for item, count in rows:
            item.value = {'count': count + 1}
            item.save(update_fields=['value'])


def _tavily(query):
    if not settings.TAVILY_API_KEY.strip():
        raise ConsultationError('Clé Tavily absente. Configure le compte gratuit avant toute recherche autorisée.', source='tavily_search')
    payload = {'query': query, 'search_depth': 'basic', 'topic': 'general',
               'max_results': min(20, max(1, settings.DISCOVERY_MAX_CANDIDATES)),
               'include_answer': False, 'include_raw_content': False,
               'include_images': False, 'auto_parameters': False}
    key = 'discovery:tavily:basic:v1:' + query + ':' + str(payload['max_results'])
    saved = cached_value(key)
    if saved:
        return saved
    try:
        response = request('POST', TAVILY_URL, source='tavily_search',
            headers={'Authorization': 'Bearer ' + settings.TAVILY_API_KEY}, json=payload,
            timeout=15, before_send=_reserve_tavily_credit)
    except ConsultationError as exc:
        if exc.http_status in {401, 403, 432, 433}:
            reason = 'Clé ou accès Tavily refusé.' if exc.http_status in {401, 403} else 'Quota du compte Tavily atteint.'
            raise ConsultationError(reason + ' Recherche arrêtée ; aucune facturation ni bascule de fournisseur automatique.',
                                    source='tavily_search', http_status=exc.http_status) from exc
        raise
    try:
        data = response.json()
        results = data['results']
        if not isinstance(results, list) or any(not isinstance(row, dict) or not isinstance(row.get('url'), str) for row in results):
            raise ValueError()
    except (ValueError, KeyError, TypeError):
        raise ConsultationError('Réponse Tavily inexploitable. Aucun résultat commercial ne peut être déduit.', source='tavily_search') from None
    urls = []
    for row in results:
        try:
            p = urlsplit(row['url'])
            if p.scheme not in {'http', 'https'} or not p.hostname or p.username or p.password:
                continue
            candidate = urlunsplit((p.scheme, p.netloc, p.path or '/', p.query, ''))
        except ValueError:
            continue
        if candidate not in urls:
            urls.append(candidate)
    result = {'provider': 'tavily', 'source_url': TAVILY_URL,
              'observed_at': response.prospect_observed_at, 'urls': urls[:payload['max_results']]}
    store_value(key, result, hours=24)
    return result


PROVIDERS = {'tavily': _tavily}


def search(query):
    from .run_limits import guard_current
    guard_current()
    if not settings.DISCOVERY_ENABLED:
        raise ConsultationError('Découverte externe désactivée. Une autorisation de recherche réelle et la configuration Tavily sont nécessaires.', source='discovery_search')
    provider = PROVIDERS.get(settings.DISCOVERY_PROVIDER)
    if provider is None:
        raise ConsultationError('Fournisseur de découverte non configuré. Aucun fournisseur de secours automatique.', source='discovery_search')
    return provider(query)
