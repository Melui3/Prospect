"""Read-only explanations: never promote or rewrite historical observations."""
from .selection import _valid_evidence
from django.conf import settings
from django.utils import timezone

LABELS = {
    'not_evaluated': 'Consulte la sélection actuelle pour connaître le classement de cette fiche.',
    'decision_or_status': 'Une décision humaine ou le statut de la fiche empêche la sélection.',
    'exclusion_or_outreach': 'Fiche exclue, déjà contactée ou non disponible pour une nouvelle sollicitation.',
    'contact_invalid': 'Adresse professionnelle absente ou invalide.',
    'contact_unverified_or_stale': 'Aucune preuve recevable et récente ne corrobore le contact actuel.',
    'business_evidence_insufficient_or_stale': 'Observation commerciale recevable absente, périmée ou incompatible avec la fiche actuelle.',
    'human_decision_or_contacted_duplicate': 'Une décision humaine ou un contact antérieur protège cette entreprise, y compris ses doublons.',
    'duplicate': 'Une autre fiche de la même entreprise a été retenue.',
    'held_by_limit': 'Dossier recevable au-delà des cinq places disponibles.',
}


def diagnostic(review, code):
    active = [e for e in review.evidence if isinstance(e, dict) and not e.get('historical')]
    valid = _valid_evidence(review, timezone.now(), settings.SELECTION_EVIDENCE_MAX_AGE_DAYS)
    missing_origin = sum(e.get('origin') not in {'automatic','human','assisted'} for e in active)
    return {'code': code, 'label': LABELS.get(code, 'Dossier retenu dans la sélection actuelle.'),
            'active_proof_count': len(active), 'usable_proof_count': len(valid),
            'missing_origin_count': missing_origin,
            'historical_recovery': ('Reprise non automatique : une origine, une date, une source et une méthode démontrables sont nécessaires. '
                                    'Les anciennes propositions ne valent pas admission dans la sélection actuelle.') if len(valid) < len(active) else ''}
