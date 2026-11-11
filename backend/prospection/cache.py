import hashlib
from datetime import timedelta

from django.utils import timezone

from .models import ServiceCache


def cache_key(value):
    return hashlib.sha256(value.encode()).hexdigest()


def cached_value(key):
    item = ServiceCache.objects.filter(key=cache_key(key), expires_at__gt=timezone.now()).first()
    return item.value if item else None


def store_value(key, value, hours=24):
    ServiceCache.objects.update_or_create(
        key=cache_key(key), defaults={"value": value, "expires_at": timezone.now() + timedelta(hours=hours)},
    )
