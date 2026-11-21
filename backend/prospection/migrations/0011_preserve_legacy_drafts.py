import hashlib
import json
from django.db import migrations

def preserve_legacy(apps, schema_editor):
    Draft=apps.get_model("prospection","EmailDraft")
    Version=apps.get_model("prospection","EmailDraftVersion")
    alias=schema_editor.connection.alias
    for draft in Draft.objects.using(alias).select_related("prospect").all().iterator():
        p=draft.prospect
        context={k:getattr(p,k) or "" for k in ("nom","ville","email","website")}
        payload={"subject":draft.subject,"body":draft.body,"template_id":draft.template_id,
                 "context":context,"evidence":{}}
        fingerprint=hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        Version.objects.using(alias).get_or_create(draft_id=draft.pk,number=1,defaults={
            "subject":draft.subject,"body":draft.body,"recipient":context["email"],
            "context":context,"evidence":{},"origin":"legacy","generator":"",
            "template_id_snapshot":draft.template_id,"fingerprint":fingerprint,
            "created_at":draft.updated_at})
        Draft.objects.using(alias).filter(pk=draft.pk).update(revision=1,origin="legacy")
    # Historical approvals are deliberately not attributed to any new snapshot.

class Migration(migrations.Migration):
    dependencies=[("prospection","0010_email_versions")]
    operations=[migrations.RunPython(preserve_legacy,migrations.RunPython.noop)]
