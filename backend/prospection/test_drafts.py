from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from .models import EmailDraft, EmailLog, Prospect, QualificationReview
from . import test_selection as selection_fixtures

@override_settings(DESKTOP_AUTO_AUTH=False, OWNER_ACCESS_TOKEN="", REQUIRE_OWNER_TOKEN=False,
                   EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class DraftVersionTests(TestCase):
    setUp = selection_fixtures.CommercialSelectionTests.setUp
    candidate = selection_fixtures.CommercialSelectionTests.candidate

    def endpoint(self, q, suffix="draft"):
        return f"/api/personal/contacts/{q.prospect_id}/{suffix}/"

    def generate(self, q, version=0):
        return self.client.post(self.endpoint(q,"generate-draft"), {"expected_revision":version},format="json")

    def approve(self, q, revision):
        return self.client.post(f"/api/personal/qualification/{q.pk}/approve/",
                                {"revision":revision},format="json")

    def test_three_signals_produce_distinct_supported_messages_and_portfolio(self):
        texts=[]
        for kind in ["third_party_menu","dispersed_information","missing_viewport"]:
            q=self.candidate(kind)
            result=self.generate(q)
            self.assertEqual(result.status_code,200,result.data)
            data=result.data
            texts.append(data["body"])
            self.assertIn(q.prospect.nom,data["subject"])
            self.assertIn("https://nathaniel-dev.fr/",data["body"])
            self.assertIn("NateOS",data["body"])
            self.assertTrue(data["versions"][0]["evidence"])
            self.assertNotIn("vous n'avez pas de site",data["body"])
            self.assertEqual(data["origin"],"conditional")
        self.assertEqual(len(set(texts)),3)
        self.assertIn("carte",texts[0])
        self.assertIn("réunir",texts[1])
        self.assertIn("ne suffit pas",texts[2])

    def test_refuses_insufficient_stale_and_decided_prospects(self):
        for kind,age,status in [("website_not_listed",1,"pending"),
                                ("third_party_menu",40,"pending"),
                                ("third_party_menu",1,"rejected"),
                                ("third_party_menu",1,"deferred")]:
            q=self.candidate(kind,age=age,status=status)
            self.assertEqual(self.generate(q).status_code,409)
        self.assertFalse(EmailDraft.objects.exists())

    def test_regeneration_keeps_legacy_and_creates_even_identical_version(self):
        q=self.candidate()
        d=EmailDraft.objects.create(prospect=q.prospect,subject="Ancien",body="Texte humain")
        self.assertEqual(self.generate(q,d.revision).status_code,200)
        d.refresh_from_db()
        self.assertEqual(d.versions.get(number=1).body,"Texte humain")
        self.assertEqual(self.generate(q,d.revision).status_code,200)
        d.refresh_from_db()
        self.assertEqual(d.revision,3)
        self.assertEqual(d.versions.count(),3)

    def test_edit_invalidates_approval_and_preserves_approved_text(self):
        q=self.candidate()
        d=self.generate(q).data
        self.assertEqual(self.approve(q,d["revision"]).status_code,200)
        result=self.client.put(self.endpoint(q),{"subject":d["subject"],"body":"Texte relu",
                               "expected_revision":d["revision"]},format="json")
        self.assertEqual(result.status_code,200,result.data)
        self.assertIsNone(result.data["approved_revision"])
        q.refresh_from_db();self.assertEqual(q.status,"pending")
        self.assertEqual(result.data["versions"][0]["body"],"Texte relu")
        self.assertEqual(result.data["versions"][1]["body"],d["body"])

    def test_noop_save_preserves_version_and_approval(self):
        q=self.candidate();d=self.generate(q).data;self.approve(q,d["revision"])
        result=self.client.put(self.endpoint(q),{"subject":d["subject"],"body":d["body"],
                               "expected_revision":d["revision"]},format="json")
        self.assertEqual(result.data["revision"],d["revision"])
        self.assertEqual(result.data["approved_revision"],d["revision"])

    def test_stale_editor_and_stale_approval_are_rejected(self):
        q=self.candidate();d=self.generate(q).data
        self.generate(q,d["revision"])
        self.assertEqual(self.approve(q,d["revision"]).status_code,409)
        edit=self.client.put(self.endpoint(q),{"body":"Perdu","expected_revision":d["revision"]},format="json")
        self.assertEqual(edit.status_code,409)
        self.assertNotEqual(EmailDraft.objects.get(prospect=q.prospect).body,"Perdu")

    def test_unapproved_version_never_reaches_transport(self):
        q=self.candidate();d=self.generate(q).data
        with patch("prospection.mail.EmailMessage.send") as smtp,patch("prospection.mail.brevo_key") as brevo:
            r=self.client.post(self.endpoint(q,"send-email"),{**d,"confirmed":True},format="json",
                               HTTP_IDEMPOTENCY_KEY="blocked")
            self.assertEqual(r.status_code,409)
            smtp.assert_not_called();brevo.assert_not_called()
        self.assertFalse(EmailLog.objects.exists())

    def test_only_exact_approved_version_can_send_to_fake_transport(self):
        from django.core import mail
        q=self.candidate();d=self.generate(q).data;self.approve(q,d["revision"])
        with patch("prospection.mail.brevo_key",return_value=""),patch("prospection.mail.sender_address",return_value="nate@sender.example"):
            r=self.client.post(self.endpoint(q,"send-email"),
                {"subject":d["subject"],"body":d["body"],"revision":d["revision"],"confirmed":True},
                format="json",HTTP_IDEMPOTENCY_KEY="fake-only")
        self.assertEqual(r.status_code,200,r.data)
        self.assertEqual(mail.outbox[0].body,d["body"])
        self.assertEqual(mail.outbox[0].to,[q.prospect.email])
        self.assertEqual(EmailLog.objects.get().draft_revision,d["revision"])

    def test_recipient_change_blocks_approved_version(self):
        q=self.candidate();d=self.generate(q).data;self.approve(q,d["revision"])
        Prospect.objects.filter(pk=q.prospect_id).update(email="changed@business.example")
        from .mail import MailError,send_message
        q.prospect.refresh_from_db()
        with self.assertRaises(MailError),patch("prospection.mail.EmailMessage.send") as smtp:
            send_message(q.prospect,d["subject"],d["body"],"changed",approval_confirmed=True,revision=d["revision"])
        smtp.assert_not_called()

    def test_model_save_versions_direct_edits_and_snapshots_are_immutable(self):
        q=self.candidate();d=self.generate(q).data;self.approve(q,d["revision"])
        draft=EmailDraft.objects.get(prospect=q.prospect)
        draft.body="Changement direct";draft.save(update_fields=["body"])
        self.assertEqual(draft.revision,2)
        self.assertIsNone(draft.approved_revision)
        snap=draft.versions.get(number=1);snap.body="Altération"
        with self.assertRaises(ValueError):snap.save()

    def test_worker_prepares_selected_missing_drafts_and_preserves_existing(self):
        from .drafts import prepare_selected_missing
        q=self.candidate();old=self.candidate("dispersed_information")
        EmailDraft.objects.create(prospect=old.prospect,subject="Ancien",body="À préserver")
        result=prepare_selected_missing()
        self.assertEqual(result["created"],1)
        self.assertTrue(EmailDraft.objects.filter(prospect=q.prospect).exists())
        self.assertEqual(EmailDraft.objects.get(prospect=old.prospect).body,"À préserver")
        self.assertEqual(prepare_selected_missing()["created"],0)

    def test_generation_respects_top_five_and_duplicate_exclusions(self):
        for _ in range(6):self.candidate()
        rows=list(QualificationReview.objects.order_by("pk"))
        self.assertEqual(self.generate(rows[0]).status_code,409)
        p=rows[-1].prospect;p.status="do_not_contact";p.save()
        self.assertEqual(self.generate(rows[-1]).status_code,409)

    def test_rejected_or_opposed_draft_cannot_be_edited(self):
        q=self.candidate();d=self.generate(q).data
        q.status="rejected";q.save()
        r=self.client.put(self.endpoint(q),{"body":"Contournement","expected_revision":d["revision"]},format="json")
        self.assertEqual(r.status_code,409)

    def test_modified_proof_blocks_approval(self):
        q=self.candidate();d=self.generate(q).data
        q.refresh_from_db();q.evidence[-1]["detail"]="Nouvelle observation";q.save()
        self.assertEqual(self.approve(q,d["revision"]).status_code,409)

    def test_missing_revision_and_get_are_read_only(self):
        q=self.candidate();d=self.generate(q).data
        self.assertEqual(self.approve(q,None).status_code,409)
        self.assertEqual(self.client.put(self.endpoint(q),{"body":"Perdu"},format="json").status_code,409)
        before=list(EmailDraft.objects.values())
        self.client.get(self.endpoint(q));self.client.get("/api/personal/qualification/")
        self.assertEqual(list(EmailDraft.objects.values()),before)

    def test_changed_proof_after_approval_blocks_send_preparation(self):
        q=self.candidate();d=self.generate(q).data;self.approve(q,d["revision"])
        q.refresh_from_db();q.evidence[-1]["method"]="Autre méthode";q.save()
        result=self.client.post(self.endpoint(q,"validate-draft"),
            {"subject":d["subject"],"body":d["body"],"revision":d["revision"]},format="json")
        self.assertEqual(result.status_code,409)
        self.assertFalse(EmailLog.objects.exists())

    def test_expired_proof_after_approval_blocks_transport(self):
        q=self.candidate();d=self.generate(q).data;self.approve(q,d["revision"])
        with patch("prospection.drafts.timezone.now",return_value=timezone.now()+timedelta(days=31)):
            result=self.client.post(self.endpoint(q,"validate-draft"),
                {"subject":d["subject"],"body":d["body"],"revision":d["revision"]},format="json")
        self.assertEqual(result.status_code,409)

    def test_editing_then_restoring_text_does_not_restore_old_approval(self):
        q=self.candidate();d=self.generate(q).data;self.approve(q,d["revision"])
        draft=EmailDraft.objects.get(prospect=q.prospect)
        original=draft.body;draft.body="Temporaire";draft.save()
        draft.body=original;draft.save()
        self.assertEqual(draft.revision,3)
        self.assertIsNone(draft.approved_revision)
        self.assertIsNotNone(draft.versions.get(number=1).approved_at)

    def test_protected_sending_version_cannot_be_modified(self):
        q=self.candidate();d=self.generate(q).data;self.approve(q,d["revision"])
        def isolated_transport(*args,**kwargs):
            edit=self.client.put(self.endpoint(q),{"body":"Trop tard","expected_revision":d["revision"]},format="json")
            self.assertEqual(edit.status_code,409)
            changed=self.client.patch(f"/api/personal/contacts/{q.prospect_id}/",
                                     {"email":"other@business.example"},format="json")
            self.assertEqual(changed.status_code,400)
            return 1
        with patch("prospection.mail.brevo_key",return_value=""),patch("prospection.mail.sender_address",return_value="nate@sender.example"),patch("prospection.mail.EmailMessage.send",side_effect=isolated_transport):
            result=self.client.post(self.endpoint(q,"send-email"),
                {"subject":d["subject"],"body":d["body"],"revision":d["revision"],"confirmed":True},
                format="json",HTTP_IDEMPOTENCY_KEY="claimed")
        self.assertEqual(result.status_code,200,result.data)
        draft=EmailDraft.objects.get(prospect=q.prospect)
        self.assertEqual(draft.body,d["body"]);self.assertIsNone(draft.sending_revision)

    def test_contact_api_edit_creates_version_and_invalidates_approval(self):
        q=self.candidate();d=self.generate(q).data;self.approve(q,d["revision"])
        result=self.client.patch(f"/api/personal/contacts/{q.prospect_id}/",
                                 {"email":"other@business.example"},format="json")
        self.assertEqual(result.status_code,200,result.data)
        draft=EmailDraft.objects.get(prospect=q.prospect)
        self.assertEqual(draft.revision,2);self.assertIsNone(draft.approved_revision)

    def test_explicit_reopen_removes_bound_approval_before_regeneration(self):
        q=self.candidate();d=self.generate(q).data;self.approve(q,d["revision"])
        self.assertEqual(self.generate(q,d["revision"]).status_code,409)
        result=self.client.post(f"/api/personal/qualification/{q.pk}/reopen/")
        self.assertEqual(result.status_code,200,result.data)
        self.assertIsNone(EmailDraft.objects.get(prospect=q.prospect).approved_revision)
        self.assertEqual(self.generate(q,d["revision"]).status_code,200)

    def test_legacy_migration_preserves_exact_existing_text_and_decisions(self):
        import importlib
        from django.apps import apps
        from django.db import connection
        from unittest.mock import Mock
        q=self.candidate(status="approved")
        draft=EmailDraft.objects.create(prospect=q.prospect,subject="Objet humain",body="Ancien texte humain")
        draft.versions.all().delete()
        before=list(EmailDraft.objects.values("subject","body","state","updated_at","sent_at","template_id"))
        migration=importlib.import_module("prospection.migrations.0011_preserve_legacy_drafts")
        migration.preserve_legacy(apps,Mock(connection=connection))
        migration.preserve_legacy(apps,Mock(connection=connection))
        self.assertEqual(list(EmailDraft.objects.values("subject","body","state","updated_at","sent_at","template_id")),before)
        draft.refresh_from_db();q.refresh_from_db()
        self.assertEqual(draft.versions.count(),1)
        self.assertEqual(draft.versions.get().body,"Ancien texte humain")
        self.assertIsNone(draft.approved_revision)
        self.assertEqual(q.status,"approved")

    def test_recorded_observation_is_used_and_origin_is_retained(self):
        q=self.candidate()
        q.evidence[-1]["detail"]="La carte du midi figure dans une rubrique dédiée."
        q.evidence[-1]["origin"]="assisted";q.save()
        d=self.generate(q).data
        self.assertIn("La carte du midi figure",d["body"])
        self.assertTrue(any(r["origin"]=="assisted" for r in d["evidence_snapshot"]["records"]))

    def test_later_human_decision_on_duplicate_blocks_preparation(self):
        q=self.candidate();d=self.generate(q).data;self.approve(q,d["revision"])
        self.candidate(email=q.prospect.email,status="rejected")
        result=self.client.post(self.endpoint(q,"validate-draft"),
            {"subject":d["subject"],"body":d["body"],"revision":d["revision"]},format="json")
        self.assertEqual(result.status_code,409)
