"""Bounded administrative discovery through the public Recherche d'entreprises API.

Registry records are leads, never commercial evidence or verified contacts.
"""
import hashlib
import json
import math
import re
from urllib.parse import urlencode
from django.db import transaction
from django.utils import timezone
from .consultations import ConsultationError, request
from .identity import normalized
from .run_limits import guard_current

URL = 'https://recherche-entreprises.api.gouv.fr/near_point'
SOURCE = 'recherche_entreprises'
MAX_PAGES = 4
PER_PAGE = 25
NAF_CODES = {
    'restaurant': ('56.10A', '56.10B', '56.10C'),
    'boulangerie': ('10.71C',),
    'coiffeur': ('96.02A',),
}
LEGAL_FIELDS = ('siren', 'nom_complet', 'nom_raison_sociale', 'etat_administratif',
    'statut_diffusion', 'opposition_diffusion_commerciale', 'date_mise_a_jour')
LOCAL_FIELDS = ('siret', 'nom_commercial', 'liste_enseignes', 'adresse', 'code_postal',
    'libelle_commune', 'latitude', 'longitude', 'activite_principale',
    'etat_administratif', 'statut_diffusion_etablissement', 'date_mise_a_jour')


def activity_codes(sector):
    value = sector.strip().upper()
    if re.fullmatch(r'[0-9]{2}\.[0-9]{2}[A-Z]', value):
        return (value,)
    codes = NAF_CODES.get(normalized(sector))
    if not codes:
        raise ValueError('Secteur sans correspondance NAF vérifiée. Recherche arrêtée sans élargissement de périmètre.')
    return codes


def _validate(response, expected_page):
    try:
        data = response.json()
    except ValueError as exc:
        raise ConsultationError('Réponse Recherche d’entreprises non JSON.', temporary=True, source=SOURCE) from exc
    if (not isinstance(data, dict) or not isinstance(data.get('results'), list)
            or any(type(data.get(k)) is not int or data[k] < 0
                   for k in ('page', 'total_pages', 'total_results'))
            or data['page'] < 1 or data['page'] != expected_page):
        raise ConsultationError('Réponse Recherche d’entreprises inexploitable.', temporary=True, source=SOURCE)
    per_page = data.get('per_page', PER_PAGE)
    total, pages = data['total_results'], data['total_pages']
    valid_pages = {0, 1} if total == 0 else {math.ceil(total / per_page)} if type(per_page) is int and per_page > 0 else set()
    expected_rows = max(0, min(per_page, total-(data['page']-1)*per_page)) if type(per_page) is int else -1
    if (type(per_page) is not int or not 1 <= per_page <= PER_PAGE
            or pages not in valid_pages or (total > 0 and data['page'] > pages)
            or len(data['results']) != expected_rows):
        raise ConsultationError('Comptage et pagination Recherche d’entreprises incohérents.', temporary=True, source=SOURCE)
    clean = {k: data[k] for k in ('page', 'total_pages', 'total_results')}
    clean['results'] = []
    for row in data['results']:
        if (not isinstance(row, dict) or not isinstance(row.get('matching_etablissements'), list)
                or any(not isinstance(e, dict) for e in row['matching_etablissements'])):
            raise ConsultationError('Établissements de la réponse inexploitable.', temporary=True, source=SOURCE)
        unit = {k: row.get(k) for k in LEGAL_FIELDS}
        unit['matching_etablissements'] = [{k: e.get(k) for k in LOCAL_FIELDS}
                                          for e in row['matching_etablissements']]
        clean['results'].append(unit)
    # Whitelist in memory. The registry raw-response HTTP cache is disabled;
    # only accepted normalized records are checkpointed in the existing job.
    response._content = json.dumps(clean, ensure_ascii=False).encode('utf-8')
    response.encoding = 'utf-8'


def _distance(lat, lon, latitude, longitude):
    try:
        a, b = float(latitude), float(longitude)
        if not math.isfinite(a) or not math.isfinite(b) or not -90 <= a <= 90 or not -180 <= b <= 180:
            return None
    except (ValueError, TypeError):
        return None
    x, y = math.radians(a-lat), math.radians(b-lon)
    h = math.sin(x/2)**2 + math.cos(math.radians(lat))*math.cos(math.radians(a))*math.sin(y/2)**2
    return 6371.0088 * 2 * math.asin(math.sqrt(min(1, max(0, h))))


def _normalise(unit, entry, *, lat, lon, radius, codes, when, source_url, state):
    def reject(reason):
        state['rejections'][reason] = state['rejections'].get(reason, 0) + 1
        return None
    siren, siret = unit.get('siren'), entry.get('siret')
    if (not isinstance(siren, str) or not re.fullmatch(r'[0-9]{9}', siren)
            or not isinstance(siret, str) or not re.fullmatch(r'[0-9]{14}', siret)
            or not siret.startswith(siren)):
        return reject('identifier_unverified')
    if unit.get('etat_administratif') != 'A' or entry.get('etat_administratif') != 'A':
        return reject('inactive_or_unknown')
    if unit.get('statut_diffusion') != 'O' or entry.get('statut_diffusion_etablissement') != 'O':
        return reject('diffusion_restricted_or_unknown')
    if entry.get('activite_principale') not in codes:
        return reject('local_activity_mismatch')
    distance = _distance(lat, lon, entry.get('latitude'), entry.get('longitude'))
    if distance is None or distance > radius:
        return reject('outside_radius_or_unlocated')
    brand = entry.get('nom_commercial')
    brands = entry.get('liste_enseignes')
    if not isinstance(brand, str) or not brand.strip():
        brand = next((s for s in brands if isinstance(s, str) and s.strip()), '') if isinstance(brands, list) else ''
    name = brand or unit.get('nom_raison_sociale') or unit.get('nom_complet')
    city, address = entry.get('libelle_commune'), entry.get('adresse')
    if not all(isinstance(v, str) and v.strip() for v in (name, city, address)):
        return reject('identity_incomplete')
    if unit.get('opposition_diffusion_commerciale') is True:
        from .models import Prospect
        from .opposition import persist_opposition
        with transaction.atomic():
            guard_current()
            persist_opposition(Prospect(nom=name, ville=city), {
                'url': source_url, 'observed_at': when, 'origin': 'automatic'})
            guard_current()
        return reject('commercial_opposition')
    if unit.get('opposition_diffusion_commerciale') is not False:
        return reject('commercial_opposition_unknown')
    from .opposition import is_opposed
    if is_opposed(name, city):
        return reject('existing_opposition')
    street = address.strip()
    postal = entry.get('code_postal')
    if isinstance(postal, str) and postal:
        street = re.sub(r'\s+'+re.escape(postal)+r'\s+'+re.escape(city.strip())+r'$', '', street, flags=re.I)
    provenance = {'provider': SOURCE, 'url': source_url, 'observed_at': when,
        'attribution': 'API Recherche d’entreprises (DINUM), Sirene (Insee), RNE (INPI)',
        'origin': 'automatic', 'siren': siren, 'siret': siret,
        'naf': entry['activite_principale'], 'distance_km': round(distance, 6),
        'source_updated_at': entry.get('date_mise_a_jour') or unit.get('date_mise_a_jour'),
        'method': 'Recherche géographique puis vérification établissement, NAF et statuts de diffusion.',
        'limits': 'Donnée administrative géocodée ; activité réelle, besoin commercial et coordonnées de contact non vérifiés.'}
    return {'type': 'siret', 'id': siret, 'tags': {'name': name.strip(),
        'addr:city': city.strip(), 'addr:street': street, 'siret': siret,
        'company_discovery': provenance}}


def discover_companies(job):
    from .jobs import checkpoint
    from .services import _get_city_coords
    campaign = job.campaign
    codes = activity_codes(campaign.secteur)
    if not 0 < campaign.rayon_km <= 50:
        raise ValueError('Rayon Recherche d’entreprises hors limites : 0 < rayon ≤ 50 km.')
    state = job.payload.get('company_discovery')
    if state:
        coords = state['center']
    else:
        coords = _get_city_coords(campaign.ville)
        if not coords:
            raise ValueError('Commune introuvable ; aucune recherche d’entreprise effectuée.')
    lat, lon = map(float, coords)
    if not math.isfinite(lat) or not math.isfinite(lon) or not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise ValueError('Centre géographique inexploitable.')
    limit = 5 if job.pilot_deadline is not None else 100
    signature = hashlib.sha256(json.dumps([campaign.secteur, campaign.ville, campaign.rayon_km,
        codes, lat, lon, limit], ensure_ascii=False).encode()).hexdigest()
    if state and state.get('signature') != signature:
        raise ValueError('Périmètre modifié pendant la découverte. Aucune reprise sur un autre périmètre.')
    if not state:
        state = {'signature': signature, 'center': [lat, lon], 'next_page': 1,
            'elements': [], 'rejections': {}, 'returned_units': 0, 'complete': False,
            'scope_truncated': False, 'limit_omitted': 0, 'unvisited_api_pages': 0, 'provider': SOURCE}
        job.payload['company_discovery'] = state
        checkpoint(job, payload=job.payload)
    if state['complete']:
        return state['elements']
    while state['next_page'] <= MAX_PAGES:
        checkpoint(job, stage='Découverte administrative des établissements')
        page = state['next_page']
        params = {'lat': lat, 'long': lon, 'radius': campaign.rayon_km,
            'activite_principale': ','.join(codes), 'page': page, 'per_page': PER_PAGE,
            'limite_matching_etablissements': 100, 'page_etablissements': 1,
            'minimal': True, 'include': 'matching_etablissements'}
        response = request('GET', URL, source=SOURCE, params=params,
            headers={'User-Agent': 'Prospect/1.0 (local company discovery)', 'Accept': 'application/json'},
            timeout=15, minimum_interval=1.1, validate_response=lambda r: _validate(r, page),
            cache_response=False)
        data = response.json()
        if data['page'] != page:
            raise ConsultationError('Pagination Recherche d’entreprises incohérente.', temporary=True, source=SOURCE)
        source_url = URL+'?'+urlencode(params)
        when = response.prospect_observed_at
        state['returned_units'] += len(data['results'])
        known = {e['id'] for e in state['elements']}
        for unit in data['results']:
            if len(unit['matching_etablissements']) >= 100:
                state['scope_truncated'] = True
            for entry in unit['matching_etablissements']:
                element = _normalise(unit, entry, lat=lat, lon=lon, radius=campaign.rayon_km,
                    codes=codes, when=when, source_url=source_url, state=state)
                if element and element['id'] not in known:
                    known.add(element['id'])
                    if len(state['elements']) < limit:
                        state['elements'].append(element)
                    else:
                        state['limit_omitted'] += 1
        state['next_page'] += 1
        more = page < data['total_pages']
        if len(state['elements']) >= limit or page >= MAX_PAGES or not more:
            state['complete'] = True
            state['unvisited_api_pages'] = max(0, data['total_pages']-page)
            state['scope_truncated'] = state['scope_truncated'] or more or state['limit_omitted'] > 0
        checkpoint(job, payload=job.payload)
        if state['complete']:
            break
    return state['elements']
