from django.utils import timezone
from django.db import transaction
from .models import Prospect, ProspectEvent
from .services import _find_email_on_website, _find_email_pages_jaunes


def enrich_prospect(prospect, force=False):
    if prospect.email and not force:
        return
    email, source = None, ""
    failed = False
    try:
        if prospect.website:
            email, source = _find_email_on_website(prospect.website, with_source=True, force=force)
        if not email and not prospect.email:
            email = _find_email_pages_jaunes(prospect.nom, prospect.ville)
            if email:
                source = "Pages Jaunes"
    except Exception:
        failed = True
    # A lookup can take several seconds; do not overwrite edits made in the meantime.
    with transaction.atomic():
        current = Prospect.objects.filter(pk=prospect.pk).first()
        if not current:
            return
        if email and not current.email:
            current.email = email
            current.email_source = source
            current.email_verified_at = timezone.now()
            ProspectEvent.objects.create(prospect=current, kind="enrichment", message=f"Email trouve : {email} ({source})")
        current.enrichment_status = "found" if current.email else "error" if failed else "not_found"
        current.enriched_at = timezone.now()
        current.save(update_fields=["email", "email_source", "email_verified_at", "enrichment_status", "enriched_at"])
        prospect.email = current.email
        prospect.enrichment_status = current.enrichment_status
