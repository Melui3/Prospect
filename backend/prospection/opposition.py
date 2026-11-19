"""Persistent suppression keys outlive a contact row."""
from datetime import datetime, timezone as datetime_timezone
from urllib.parse import urlsplit

from django.conf import settings
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.utils import timezone

from .cache import cache_key
from .identity import normalized
from .models import Prospect, ServiceCache

UNTIL_REVIEW = datetime(9999, 1, 1, tzinfo=datetime_timezone.utc)


def _keys(name, city, email, website):
    keys = []
    business = " ".join(w for w in normalized(name).split() if w not in {"sarl", "sas", "eurl", "sasu"})
    if business and normalized(city):
        keys.append("company:" + business + "|" + normalized(city))
    if email:
        keys.append("email:" + email.strip().casefold())
    host = (urlsplit(website or "").hostname or "").lower().removeprefix("www.")
    shared_hosts = set(settings.DISCOVERY_DIRECTORY_HOSTS) | {"facebook.com", "instagram.com", "linkedin.com"}
    if host and not any(host == domain or host.endswith("." + domain) for domain in shared_hosts):
        keys.append("domain:" + host)
    return [cache_key("commercial-opposition:" + key) for key in keys]


def persist_opposition(prospect, evidence=None, *, email=None, website=None):
    value = {"reason": "Opposition commerciale de l’établissement ou du contact.",
             "source": evidence.get("url", "") if evidence else "Statut Ne plus contacter",
             "observed_at": evidence.get("observed_at") if evidence else timezone.now().isoformat(),
             "origin": evidence.get("origin", "human") if evidence else "human"}
    for key in _keys(prospect.nom, prospect.ville,
                     email if email is not None else prospect.email,
                     website if website is not None else prospect.website):
        ServiceCache.objects.get_or_create(key=key, defaults={"value": value, "expires_at": UNTIL_REVIEW})


def is_opposed(name, city, email=None, website=None):
    keys = set(_keys(name, city, email, website))
    if keys and ServiceCache.objects.filter(key__in=keys).exists():
        return True
    # Old rows are also respected without migrating or rewriting the existing data.
    for p in Prospect.objects.filter(status="do_not_contact").only("nom", "ville", "email", "website"):
        if keys.intersection(_keys(p.nom, p.ville, p.email, p.website)):
            return True
    return False


@receiver(post_save, sender=Prospect)
@receiver(pre_delete, sender=Prospect)
def remember_opposition(sender, instance, **kwargs):
    if instance.status == "do_not_contact":
        persist_opposition(instance)
