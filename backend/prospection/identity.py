import hashlib
import re
import unicodedata

from django.db import transaction
from django.utils import timezone

from .models import Prospect


def normalized(value):
    value = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def identity_key(name, city, address=""):
    return hashlib.sha256("|".join(normalized(v) for v in (name, city, address)).encode()).hexdigest()


@transaction.atomic
def capture_prospect(campaign, element):
    tags = element.get("tags", {})
    name = tags.get("name", "").strip()[:200]
    if not name:
        return None
    city = (tags.get("addr:city") or campaign.ville)[:100]
    address = " ".join(filter(None, [tags.get("addr:housenumber"), tags.get("addr:street")]))[:300]
    external = f"{element['type']}:{element['id']}" if element.get("id") is not None else ""
    key = identity_key(name, city, address)
    candidates = Prospect.objects.filter(merged_into=None)
    item = candidates.filter(external_id=external).first() if external else None
    if item is None:
        item = candidates.filter(identity_key=key).first()
    from .services import _extract_email, _normalize_website_url
    email = _extract_email(tags.get("email") or tags.get("contact:email") or "") or ""
    website = _normalize_website_url(tags.get("website") or tags.get("contact:website") or "") or ""
    website = website if len(website) <= 500 else ""
    email = email if len(email) <= 254 else ""
    phone = (tags.get("phone") or tags.get("contact:phone") or "")[:50]
    if item is None:
        item = Prospect.objects.create(
            campaign=campaign, identity_key=key, external_id=external,
            nom=name, ville=city, adresse=address, telephone=phone,
            email=email or None, website=website or None, has_website=bool(website),
            email_source="OpenStreetMap" if email else "",
            email_verified_at=timezone.now() if email else None,
            enrichment_status="found" if email else "pending", raw_tags=tags,
        )
    else:
        changed = []
        for field, value in [("email", email), ("website", website), ("telephone", phone), ("external_id", external)]:
            if value and not getattr(item, field):
                setattr(item, field, value)
                changed.append(field)
        if "email" in changed:
            item.email_source = "OpenStreetMap"
            item.email_verified_at = timezone.now()
            item.enrichment_status = "found"
            changed.extend(["email_source", "email_verified_at", "enrichment_status"])
        if "website" in changed:
            item.has_website = True
            changed.append("has_website")
        if changed:
            item.save(update_fields=changed)
    item.campaigns.add(campaign)
    return item
