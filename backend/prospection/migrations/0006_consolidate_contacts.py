import hashlib
import re
import unicodedata
from django.db import migrations


def consolidate(apps, schema_editor):
    Prospect = apps.get_model("prospection", "Prospect")
    EmailLog = apps.get_model("prospection", "EmailLog")
    known = {}
    ranks = {"new": 0, "ignored": 1, "contacted": 2, "replied": 3}
    def normal(value):
        text = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode().lower()
        return re.sub(r"[^a-z0-9]+", " ", text).strip()
    for item in Prospect.objects.using(schema_editor.connection.alias).order_by("id"):
        key = hashlib.sha256("|".join(normal(v) for v in (item.nom, item.ville, item.adresse)).encode()).hexdigest()
        master = known.get(key)
        if master:
            if item.campaign_id:
                master.campaigns.add(item.campaign_id)
            for field in ["email", "website", "telephone"]:
                if not getattr(master, field) and getattr(item, field):
                    setattr(master, field, getattr(item, field))
            if ranks.get(item.status, 0) > ranks.get(master.status, 0):
                master.status = item.status
            master.has_website = bool(master.website)
            master.enrichment_status = "found" if master.email else "pending"
            master.email_source = "Import existant" if master.email else ""
            master.save()
            EmailLog.objects.filter(prospect_id=item.pk).update(prospect_id=master.pk)
            item.merged_into_id = master.pk
            item.save(update_fields=["merged_into"])
        else:
            item.identity_key = key
            item.enrichment_status = "found" if item.email else "pending"
            item.email_source = "Import existant" if item.email else ""
            item.save(update_fields=["identity_key", "enrichment_status", "email_source"])
            if item.campaign_id:
                item.campaigns.add(item.campaign_id)
            known[key] = item
    for log in EmailLog.objects.select_related("prospect").all():
        log.recipient = log.prospect.email or ""
        log.delivery_status = "sent" if log.success else "error"
        log.save(update_fields=["recipient", "delivery_status"])


class Migration(migrations.Migration):
    dependencies = [("prospection", "0005_personal_workflow")]
    operations = [migrations.RunPython(consolidate, migrations.RunPython.noop)]
