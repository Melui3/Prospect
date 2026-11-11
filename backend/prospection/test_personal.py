import importlib
import os
import sqlite3
import tempfile
from datetime import timedelta
from pathlib import Path
from contextlib import closing
from unittest.mock import Mock, patch

import requests
from django.apps import apps
from django.conf import settings
from django.core import mail
from django.db import connection
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from .activity import worker_activity
from .backups import automatic_backup, create_backup, restore_backup, validate_backup
from .enrichment import enrich_prospect
from .identity import capture_prospect, identity_key
from . import jobs as prospection_jobs
from .jobs import JobPaused, checkpoint, enqueue_search, recover_jobs, run_next_job
from .mail import MailError, send_message, sync_delivery
from .models import Campaign, EmailDraft, EmailLog, Prospect, QualificationReview, SearchJob
from .qualification import qualify_prospect
from .private_config import protect, save_private_settings, load_settings
from .services import ProspectionTemporaryError, _find_email_on_website, _get_city_coords, _get_public_page


def element(number=1, **tags):
    return {"id": number, "type": "node", "tags": {"name": "Atelier Test", "addr:city": "Rennes", "addr:street": "Rue Test", **tags}}


class DiscoveryTests(TestCase):
    def setUp(self):
        self.campaign = Campaign.objects.create(secteur="restaurant", ville="Rennes")

    def test_site_without_email_is_kept(self):
        item = capture_prospect(self.campaign, element(website="https://atelier.example"))
        self.assertTrue(item.has_website)
        self.assertIsNone(item.email)
        self.assertEqual(self.campaign.total_prospects, 1)

    def test_global_duplicate_preserves_status_and_notes(self):
        item = capture_prospect(self.campaign, element())
        item.status, item.notes = "replied", "Contact important"
        item.save()
        other = Campaign.objects.create(secteur="commerce", ville="Rennes")
        again = capture_prospect(other, element(email="contact@atelier.example"))
        self.assertEqual(item.pk, again.pk)
        self.assertEqual(again.status, "replied")
        self.assertEqual(again.notes, "Contact important")
        self.assertEqual(again.campaigns.count(), 2)
        self.assertEqual(other.prospects_with_email, 1)

    def test_deleting_campaign_keeps_contact_and_history(self):
        item = capture_prospect(self.campaign, element())
        EmailLog.objects.create(prospect=item, subject="Test", body="Test")
        self.campaign.delete()
        item.refresh_from_db()
        self.assertIsNone(item.campaign)
        self.assertEqual(item.email_logs.count(), 1)

    def test_existing_records_consolidated_without_deleting_rows(self):
        a = Prospect.objects.create(campaign=self.campaign, nom="Test", ville="Rennes", status="new")
        other = Campaign.objects.create(secteur="commerce", ville="Rennes")
        b = Prospect.objects.create(campaign=other, nom="TEST", ville="rennes", status="replied", email="contact@test.example")
        log = EmailLog.objects.create(prospect=b, subject="Test", body="Test")
        migration = importlib.import_module("prospection.migrations.0006_consolidate_contacts")
        migration.consolidate(apps, Mock(connection=connection))
        a.refresh_from_db(); b.refresh_from_db(); log.refresh_from_db()
        self.assertEqual(a.status, "replied")
        self.assertEqual(a.email, b.email)
        self.assertEqual(b.merged_into_id, a.pk)
        self.assertEqual(log.prospect_id, a.pk)
        self.assertEqual(a.campaigns.count(), 2)

    @patch("prospection.enrichment._find_email_pages_jaunes", return_value=None)
    def test_lookup_does_not_overwrite_concurrent_manual_edit(self, pages):
        item = capture_prospect(self.campaign, element(website="https://atelier.example"))
        def lookup(*args, **kwargs):
            Prospect.objects.filter(pk=item.pk).update(email="manuel@atelier.example", email_source="Saisie manuelle")
            return "autre@atelier.example", "https://atelier.example/contact"
        with patch("prospection.enrichment._find_email_on_website", side_effect=lookup):
            enrich_prospect(item)
        item.refresh_from_db()
        self.assertEqual(item.email, "manuel@atelier.example")
        self.assertEqual(item.email_source, "Saisie manuelle")

    @override_settings(WEBSITE_EMAIL_MAX_PAGES=2)
    def test_actual_contact_link_precedes_guessed_paths_and_is_cached(self):
        home = Mock(status_code=200, url="https://atelier.example/", text='<a href="/equipe/contact.html">Contact</a>')
        contact = Mock(status_code=200, url="https://atelier.example/equipe/contact.html", text="bonjour@atelier.example")
        with patch("prospection.services._get_public_page", side_effect=[home, contact]) as get:
            result = _find_email_on_website("https://atelier.example/", with_source=True)
            self.assertEqual(result, ("bonjour@atelier.example", contact.url))
            self.assertEqual(get.call_args_list[1].args[0], contact.url)
            self.assertEqual(_find_email_on_website("https://atelier.example/", with_source=True), result)
            self.assertEqual(get.call_count, 2)

    def test_unavailable_website_is_not_cached_as_no_email(self):
        with patch("prospection.services._get_public_page", side_effect=requests.Timeout) as get:
            for _ in range(2):
                with self.assertRaises(ProspectionTemporaryError):
                    _find_email_on_website("https://down.example")
            self.assertGreater(get.call_count, settings.WEBSITE_EMAIL_MAX_PAGES)

    def test_local_and_redirected_private_websites_are_rejected(self):
        public = [(2, 1, 6, "", ("8.8.8.8", 443))]
        local = [(2, 1, 6, "", ("127.0.0.1", 80))]
        with patch("prospection.services.socket.getaddrinfo", return_value=local):
            with self.assertRaises(ValueError):
                _get_public_page("http://localhost/")
        redirect = Mock(status_code=302, headers={"Location": "http://127.0.0.1:8765/api/personal/contacts/"})
        with patch("prospection.services.socket.getaddrinfo", side_effect=[public, local]), patch("prospection.services.requests.get", return_value=redirect) as get:
            with self.assertRaises(ValueError):
                _get_public_page("https://site.example/")
            self.assertEqual(get.call_count, 1)

    def test_geocoding_failure_is_retryable_and_success_cached(self):
        with patch("prospection.services.time.sleep"), patch("prospection.services.requests.get", side_effect=requests.Timeout):
            with self.assertRaises(ProspectionTemporaryError):
                _get_city_coords("VilleTest")
        response = Mock(); response.json.return_value = [{"lat": "48", "lon": "-1"}]
        with patch("prospection.services.time.sleep"), patch("prospection.services.requests.get", return_value=response) as get:
            self.assertEqual(_get_city_coords("VilleTest"), ("48", "-1"))
            self.assertEqual(_get_city_coords("VilleTest"), ("48", "-1"))
            self.assertEqual(get.call_count, 1)

    def test_invalid_listed_url_is_unverified_not_reported_as_missing(self):
        item = Prospect.objects.create(nom="Atelier Test", ville="Rennes", website="javascript:alert(1)")
        review = qualify_prospect(item)
        self.assertEqual(review.status, "unverified")
        self.assertEqual(review.evidence[0]["kind"], "site_unverified")

    @patch("prospection.qualification._get_public_page")
    def test_site_checks_store_observed_signals_and_timestamp(self, get_page):
        get_page.return_value = Mock(status_code=200, url="https://atelier.example/", text="<title>Atelier</title><a href='/contact'>Contact</a>")
        item = Prospect.objects.create(nom="Atelier", ville="Rennes", website="https://atelier.example")
        review = qualify_prospect(item)
        self.assertEqual(review.status, "pending")
        self.assertEqual(review.priority, "low")
        self.assertTrue(any(row["kind"] == "http_response" and row["url"] == "https://atelier.example/" for row in review.evidence))
        self.assertTrue(all(row["observed_at"] for row in review.evidence))
        self.assertTrue(any("viewport" in reason.lower() for reason in review.reasons))

    def test_missing_site_evidence_does_not_claim_no_site_exists(self):
        item = Prospect.objects.create(nom="Atelier", ville="Rennes")
        review = qualify_prospect(item)
        self.assertEqual(review.status, "pending")
        self.assertEqual(review.evidence[0]["kind"], "website_not_listed")
        self.assertIn("ne prouve pas", review.evidence[0]["detail"])

    def test_contacted_or_previously_sent_prospect_is_excluded(self):
        item = Prospect.objects.create(nom="Atelier", ville="Rennes", email="contact@test.example", status="contacted")
        review = qualify_prospect(item)
        self.assertEqual(review.status, "excluded")
        self.assertFalse(review.reasons == [])

    def test_uncertain_prior_email_attempt_is_excluded(self):
        item = Prospect.objects.create(nom="Atelier", ville="Rennes", email="contact@test.example")
        EmailLog.objects.create(prospect=item, subject="Test", body="Test", success=False, delivery_status="uncertain")
        review = qualify_prospect(item)
        self.assertEqual(review.status, "excluded")


class JobTests(TestCase):
    def setUp(self):
        self.campaign = Campaign.objects.create(secteur="restaurant", ville="Rennes")

    def test_repeated_launch_reuses_job(self):
        job = enqueue_search(self.campaign)
        self.assertEqual(enqueue_search(self.campaign).pk, job.pk)

    def test_due_repeating_campaign_enqueues_only_one_search(self):
        self.campaign.repeat_days = 7
        self.campaign.next_search_at = timezone.now() - timedelta(minutes=1)
        self.campaign.save(update_fields=["repeat_days", "next_search_at"])

        self.assertEqual(prospection_jobs.enqueue_due_scheduled_searches(), 1)
        job = SearchJob.objects.get(campaign=self.campaign)
        self.assertEqual(job.status, "queued")
        self.campaign.refresh_from_db()
        self.assertIsNone(self.campaign.next_search_at)
        self.assertEqual(prospection_jobs.enqueue_due_scheduled_searches(), 0)
        self.assertEqual(self.campaign.jobs.count(), 1)

    @patch("prospection.services._query_overpass", return_value=[])
    @patch("prospection.services._get_city_coords", return_value=("48", "-1"))
    def test_worker_automatically_runs_a_due_repeating_campaign(self, coords, overpass):
        self.campaign.repeat_days = 7
        self.campaign.next_search_at = timezone.now() - timedelta(minutes=1)
        self.campaign.save(update_fields=["repeat_days", "next_search_at"])

        self.assertTrue(run_next_job())
        job = SearchJob.objects.get(campaign=self.campaign)
        self.assertEqual(job.status, "done")
        self.assertEqual(job.attempts, 1)
        self.campaign.refresh_from_db()
        self.assertGreater(self.campaign.next_search_at, timezone.now() + timedelta(days=6))
        overpass.assert_called_once()

    @patch("prospection.services._query_overpass", return_value=[])
    @patch("prospection.services._get_city_coords", return_value=("48", "-1"))
    def test_completed_repeating_campaign_schedules_next_search(self, coords, overpass):
        self.campaign.repeat_days = 7
        self.campaign.save(update_fields=["repeat_days"])
        enqueue_search(self.campaign)

        self.assertTrue(run_next_job())
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.status, "done")
        self.assertGreater(self.campaign.next_search_at, timezone.now() + timedelta(days=6))
        self.assertLess(self.campaign.next_search_at, timezone.now() + timedelta(days=8))
        self.assertFalse(SearchJob.objects.filter(campaign=self.campaign, status="queued").exists())

    @patch("prospection.enrichment.enrich_prospect")
    @patch("prospection.services._query_overpass", return_value=[element(website="https://atelier.example")])
    @patch("prospection.services._get_city_coords", return_value=("48", "-1"))
    def test_job_discovers_then_enriches(self, coords, overpass, enrich):
        job = enqueue_search(self.campaign)
        self.assertTrue(run_next_job())
        job.refresh_from_db()
        self.assertEqual(job.status, "done")
        self.assertEqual(job.processed, 1)
        self.assertEqual(job.payload["capture_index"], 1)
        self.assertTrue(Prospect.objects.get().has_website)
        enrich.assert_called_once()

    @patch("prospection.enrichment.enrich_prospect")
    @patch("prospection.services._query_overpass", return_value=[element()])
    @patch("prospection.services._get_city_coords", return_value=("48", "-1"))
    def test_search_queues_qualification_without_sending_email(self, coords, overpass, enrich):
        job = enqueue_search(self.campaign)
        run_next_job()
        qualification_job = SearchJob.objects.get(kind="qualification")
        self.assertEqual(qualification_job.status, "queued")
        self.assertTrue(run_next_job())
        qualification_job.refresh_from_db()
        self.assertEqual(qualification_job.status, "done")
        review = QualificationReview.objects.get(prospect=qualification_job.prospect)
        self.assertEqual(review.status, "pending")
        self.assertFalse(EmailLog.objects.exists())

    @patch("prospection.enrichment.enrich_prospect")
    @patch("prospection.services._query_overpass")
    def test_resume_uses_saved_results_instead_of_requery(self, overpass, enrich):
        item = capture_prospect(self.campaign, element())
        job = SearchJob.objects.create(campaign=self.campaign, payload={"elements": [element()], "capture_index": 1, "ids": [item.pk], "enrich_index": 0})
        run_next_job()
        overpass.assert_not_called()
        job.refresh_from_db()
        self.assertEqual(job.status, "done")

    def test_pause_cannot_be_overwritten_by_checkpoint(self):
        job = SearchJob.objects.create(campaign=self.campaign, status="paused")
        with self.assertRaises(JobPaused):
            checkpoint(job, processed=1)
        job.refresh_from_db()
        self.assertEqual(job.processed, 0)

    @patch("prospection.services._get_city_coords", side_effect=ProspectionTemporaryError("Temporaire"))
    def test_temporary_failure_is_queued_with_backoff(self, coords):
        job = enqueue_search(self.campaign)
        run_next_job(); job.refresh_from_db()
        self.assertEqual(job.status, "queued")
        self.assertGreater(job.next_run_at, timezone.now())
        job.attempts = 2; job.next_run_at = timezone.now(); job.save()
        run_next_job(); job.refresh_from_db()
        self.assertEqual(job.status, "error")

    def test_restart_recovers_job_but_does_not_auto_launch_old_campaign(self):
        job = SearchJob.objects.create(campaign=self.campaign, status="running", payload={"capture_index": 1})
        legacy = Campaign.objects.create(secteur="restaurant", ville="Rennes", status="running")
        recover_jobs(); job.refresh_from_db(); legacy.refresh_from_db()
        self.assertEqual(job.status, "queued")
        self.assertEqual(job.payload, {"capture_index": 1})
        self.assertEqual(legacy.status, "paused")


@override_settings(DESKTOP_MODE=True, DESKTOP_AUTO_AUTH=False, DEMO_MODE=False, REQUIRE_OWNER_TOKEN=False, OWNER_ACCESS_TOKEN="")
class PersonalApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.campaign = Campaign.objects.create(secteur="restaurant", ville="Rennes")
        self.item = capture_prospect(self.campaign, element(email="contact@test.example"))

    def test_search_pagination_and_campaign_filter(self):
        response = self.client.get("/api/personal/contacts/", {"search": "Atelier", "campaign": self.campaign.pk, "page_size": 1})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], self.item.pk)

    def test_notes_status_and_manual_email_are_saved_in_history(self):
        response = self.client.patch(f"/api/personal/contacts/{self.item.pk}/", {"notes": "A rappeler", "status": "interested", "email": "manuel@test.example"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.item.refresh_from_db()
        self.assertEqual(self.item.email_source, "Saisie manuelle")
        self.assertEqual(self.item.events.count(), 1)

    def test_closed_contact_cannot_get_followup(self):
        self.item.status = "do_not_contact"; self.item.save()
        response = self.client.patch(f"/api/personal/contacts/{self.item.pk}/", {"next_followup_at": timezone.now().isoformat()}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["next_followup_at"])

    def test_duplicate_manual_contact_returns_validation_error(self):
        response = self.client.post("/api/personal/contacts/", {"nom": self.item.nom, "ville": self.item.ville, "adresse": self.item.adresse}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_today_counts_followups_and_excludes_closed(self):
        self.item.next_followup_at = timezone.now() - timedelta(days=1); self.item.save()
        self.assertEqual(self.client.get("/api/personal/today/").data["due_count"], 1)
        self.item.status = "won"; self.item.save()
        self.assertEqual(self.client.get("/api/personal/today/").data["due_count"], 0)

    def test_campaign_radius_validation_and_pause_resume(self):
        self.assertEqual(self.client.post("/api/personal/campaigns/", {"secteur": "restaurant", "ville": "Rennes", "rayon_km": 100}, format="json").status_code, 400)
        response = self.client.post(f"/api/personal/campaigns/{self.campaign.pk}/launch/")
        self.assertEqual(response.status_code, 202)
        job_id = response.data["id"]
        self.assertEqual(self.client.post(f"/api/personal/jobs/{job_id}/pause/").data["status"], "paused")
        self.assertEqual(self.client.post(f"/api/personal/jobs/{job_id}/resume/").data["status"], "queued")

    def test_existing_campaign_can_enable_and_disable_recurrence(self):
        enabled = self.client.post(f"/api/personal/campaigns/{self.campaign.pk}/schedule/", {"repeat_days": 14}, format="json")
        self.assertEqual(enabled.status_code, 200)
        self.assertEqual(enabled.data["repeat_days"], 14)
        self.assertIsNotNone(enabled.data["next_search_at"])

        invalid = self.client.post(f"/api/personal/campaigns/{self.campaign.pk}/schedule/", {"repeat_days": 5}, format="json")
        self.assertEqual(invalid.status_code, 400)

        disabled = self.client.post(f"/api/personal/campaigns/{self.campaign.pk}/schedule/", {"repeat_days": 0}, format="json")
        self.assertEqual(disabled.status_code, 200)
        self.assertEqual(disabled.data["repeat_days"], 0)
        self.assertIsNone(disabled.data["next_search_at"])

    def test_foreign_origins_and_missing_owner_token_are_denied(self):
        self.assertEqual(self.client.get("/api/personal/contacts/", HTTP_ORIGIN="https://evil.example").status_code, 403)
        with override_settings(OWNER_ACCESS_TOKEN="test-owner", REQUIRE_OWNER_TOKEN=True):
            self.assertEqual(self.client.get("/api/personal/contacts/").status_code, 403)
            self.assertEqual(self.client.get("/api/personal/contacts/", HTTP_X_OWNER_TOKEN="test-owner").status_code, 200)

    def test_malformed_message_does_not_raise_500(self):
        QualificationReview.objects.create(prospect=self.item, status="approved")
        EmailDraft.objects.create(prospect=self.item)
        response = self.client.post(f"/api/personal/contacts/{self.item.pk}/send-email/", {"subject": [], "body": None, "confirmed": True}, format="json", HTTP_IDEMPOTENCY_KEY="fake")
        self.assertEqual(response.status_code, 400)

    def test_qualification_queue_is_available_in_the_personal_app(self):
        response = self.client.get("/api/personal/qualification/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)

    def test_qualification_queue_orders_high_priority_first(self):
        high = QualificationReview.objects.create(prospect=self.item, status="pending", priority="high")
        medium_item = Prospect.objects.create(nom="Moyen", ville="Rennes", email="moyen@test.example")
        low_item = Prospect.objects.create(nom="Faible", ville="Rennes", email="faible@test.example")
        medium = QualificationReview.objects.create(prospect=medium_item, status="pending", priority="medium")
        low = QualificationReview.objects.create(prospect=low_item, status="pending", priority="low")
        response = self.client.get("/api/personal/qualification/")
        self.assertEqual([item["id"] for item in response.data["results"]], [high.pk, medium.pk, low.pk])

    def test_qualification_queue_excludes_any_prior_email_attempt(self):
        review = QualificationReview.objects.create(prospect=self.item, status="pending")
        EmailLog.objects.create(prospect=self.item, subject="Test", body="Test", success=False, delivery_status="uncertain")
        response = self.client.get("/api/personal/qualification/")
        self.assertNotIn(review.pk, [item["id"] for item in response.data["results"]])

    def test_email_draft_is_saved_and_read_from_the_server(self):
        review = qualify_prospect(self.item)
        review.status = "approved"
        review.save(update_fields=["status"])
        saved = self.client.put(
            f"/api/personal/contacts/{self.item.pk}/draft/",
            {"subject": "Question pour Atelier Test", "body": "Observation verifiee."},
            format="json",
        )
        self.assertEqual(saved.status_code, 200)
        loaded = self.client.get(f"/api/personal/contacts/{self.item.pk}/draft/")
        self.assertEqual(loaded.data["body"], "Observation verifiee.")

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", DEFAULT_FROM_EMAIL="Test <test@sender.example>")
    def test_approved_candidate_still_needs_saved_draft_and_explicit_final_confirmation(self):
        review = qualify_prospect(self.item)
        review.status = "approved"
        review.save(update_fields=["status"])
        fake_log = EmailLog(prospect=self.item, subject="Question", body="Bonjour", recipient=self.item.email)
        with patch("prospection.personal_api.send_message", return_value=fake_log) as send:
            unsaved = self.client.post(
                f"/api/personal/contacts/{self.item.pk}/send-email/",
                {"subject": "Question", "body": "Bonjour", "confirmed": True},
                format="json",
                HTTP_IDEMPOTENCY_KEY="unsaved",
            )
        self.assertEqual(unsaved.status_code, 409)
        send.assert_not_called()
        self.client.put(
            f"/api/personal/contacts/{self.item.pk}/draft/",
            {"subject": "Question", "body": "Bonjour"},
            format="json",
        )
        with patch("prospection.personal_api.send_message", return_value=fake_log) as send:
            unconfirmed = self.client.post(
                f"/api/personal/contacts/{self.item.pk}/send-email/",
                {"subject": "Question", "body": "Bonjour", "confirmed": False},
                format="json",
                HTTP_IDEMPOTENCY_KEY="unconfirmed",
            )
        self.assertEqual(unconfirmed.status_code, 409)
        send.assert_not_called()

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", DEFAULT_FROM_EMAIL="Test <test@sender.example>")
    def test_approved_saved_draft_sends_only_after_explicit_confirmation(self):
        review = qualify_prospect(self.item)
        approved = self.client.post(f"/api/personal/qualification/{review.pk}/approve/")
        self.assertEqual(approved.data["status"], "approved")
        subject, body = "Question", "Bonjour"
        self.client.put(f"/api/personal/contacts/{self.item.pk}/draft/", {"subject": subject, "body": body}, format="json")
        with patch("prospection.mail.brevo_key", return_value=""), patch("prospection.mail.sender_address", return_value="Test <test@sender.example>"):
            response = self.client.post(
                f"/api/personal/contacts/{self.item.pk}/send-email/",
                {"subject": subject, "body": body, "confirmed": True},
                format="json",
                HTTP_IDEMPOTENCY_KEY="approved-draft",
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mail.outbox[-1].to, [self.item.email])
        self.assertEqual(mail.outbox[-1].body, body)
        self.assertEqual(EmailDraft.objects.get(prospect=self.item).state, "sent")

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", DEFAULT_FROM_EMAIL="Test <test@sender.example>")
    def test_pending_review_cannot_send_even_if_request_claims_confirmation(self):
        qualify_prospect(self.item)
        fake_log = EmailLog(prospect=self.item, subject="Question", body="Bonjour", recipient=self.item.email)
        with patch("prospection.personal_api.send_message", return_value=fake_log) as send:
            response = self.client.post(
                f"/api/personal/contacts/{self.item.pk}/send-email/",
                {"subject": "Question", "body": "Bonjour", "confirmed": True},
                format="json",
                HTTP_IDEMPOTENCY_KEY="pending-review",
            )
        self.assertEqual(response.status_code, 409)
        send.assert_not_called()
        self.assertFalse(EmailLog.objects.exists())

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", DEFAULT_FROM_EMAIL="Test <test@sender.example>")
    def test_rejected_review_cannot_send_even_if_request_claims_confirmation(self):
        review = qualify_prospect(self.item)
        review.status = "rejected"
        review.save(update_fields=["status"])
        subject, body = "Sujet fictif", "Message de test uniquement."
        EmailDraft.objects.update_or_create(prospect=self.item, defaults={"subject": subject, "body": body})
        with patch("prospection.personal_api.send_message") as send:
            response = self.client.post(
                f"/api/personal/contacts/{self.item.pk}/send-email/",
                {"subject": subject, "body": body, "confirmed": True},
                format="json",
                HTTP_IDEMPOTENCY_KEY="rejected-review",
            )
        self.assertEqual(response.status_code, 409)
        send.assert_not_called()
        self.assertFalse(EmailLog.objects.exists())


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", DEFAULT_FROM_EMAIL="Nathaniel <test@sender.example>")
class MailTests(TestCase):
    def setUp(self):
        self.item = Prospect.objects.create(nom="Test", email="contact@test.example")
        QualificationReview.objects.create(prospect=self.item, status="approved", priority="low")
        self.key_patch = patch("prospection.mail.brevo_key", return_value="")
        self.key_patch.start(); self.addCleanup(self.key_patch.stop)
        self.sender_patch = patch("prospection.mail.sender_address", return_value=settings.DEFAULT_FROM_EMAIL)
        self.sender_patch.start(); self.addCleanup(self.sender_patch.stop)

    def send_approved(self, subject, body, key, **kwargs):
        EmailDraft.objects.update_or_create(
            prospect=self.item,
            defaults={"subject": subject, "body": body, "state": "draft", "sent_at": None},
        )
        return send_message(self.item, subject, body, key, approval_confirmed=True, **kwargs)

    def test_custom_message_logs_actual_recipient_and_is_idempotent(self):
        log = self.send_approved("Objet personnel", "Bonjour atelier", "request-1")
        self.assertEqual(mail.outbox[0].to, [self.item.email])
        self.assertEqual(mail.outbox[0].body, "Bonjour atelier")
        self.assertEqual(log.recipient, self.item.email)
        self.assertEqual(self.send_approved(log.subject, log.body, "request-1").pk, log.pk)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIsNotNone(self.item.next_followup_at)

    def test_duplicate_different_key_blocked_unless_explicitly_forced(self):
        self.send_approved("Objet", "Bonjour", "request-1")
        with self.assertRaises(MailError):
            self.send_approved("Objet", "Bonjour", "request-2")
        self.send_approved("Objet", "Bonjour", "request-3", force=True)
        self.assertEqual(len(mail.outbox), 2)

    def test_do_not_contact_blocks_email(self):
        self.item.status = "do_not_contact"
        with self.assertRaises(MailError):
            send_message(self.item, "Objet", "Bonjour", "request-1")
        self.assertFalse(EmailLog.objects.exists())

    def test_sending_followup_reschedules_overdue_date(self):
        self.item.next_followup_at = timezone.now() - timedelta(days=1)
        self.item.save()
        self.send_approved("Relance", "Bonjour", "request-followup")
        self.assertGreater(self.item.next_followup_at, timezone.now())

    def test_manual_confirmation_records_without_sending(self):
        log = self.send_approved("Objet", "Bonjour", "request-1", manual=True)
        self.assertEqual(log.delivery_status, "manual")
        self.assertEqual(len(mail.outbox), 0)

    def test_timeout_is_uncertain_and_cannot_be_resent_by_new_key(self):
        with patch("prospection.mail.brevo_key", return_value="fake-key"), patch("prospection.mail.requests.post", side_effect=requests.Timeout):
            with self.assertRaises(MailError):
                self.send_approved("Objet", "Bonjour", "request-1")
        self.assertEqual(EmailLog.objects.get().delivery_status, "uncertain")
        with self.assertRaises(MailError):
            self.send_approved("Objet", "Bonjour", "request-2", force=True)

    def test_brevo_api_records_id_and_delivery_sync(self):
        response = Mock(status_code=201); response.json.return_value = {"messageId": "brevo-test"}
        with patch("prospection.mail.brevo_key", return_value="fake-key"), patch("prospection.mail.requests.post", return_value=response):
            log = self.send_approved("Objet", "Bonjour", "request-1")
        self.assertEqual(log.message_id, "brevo-test")
        events = Mock(); events.json.return_value = {"events": [{"messageId": "brevo-test", "event": "delivered", "date": (timezone.now() + timedelta(seconds=1)).isoformat()}]}
        with patch("prospection.mail.brevo_key", return_value="fake-key"), patch("prospection.mail.requests.get", return_value=events):
            self.assertEqual(sync_delivery()["updated"], 1)
        log.refresh_from_db(); self.assertEqual(log.delivery_status, "delivered")


class BackupTests(TransactionTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.override = override_settings(BASE_DIR=self.directory, BACKUP_DIR=self.directory / "backups", DESKTOP_MODE=True)
        self.override.enable(); self.addCleanup(self.override.disable)
        self.item = Prospect.objects.create(nom="Original", ville="Rennes")

    def test_consistent_snapshot_and_daily_backup_not_duplicated(self):
        backup = create_backup("manual")
        path = self.directory / "backups" / backup["name"]
        validate_backup(path)
        with closing(sqlite3.connect(path)) as db:
            self.assertEqual(db.execute("SELECT nom FROM prospection_prospect").fetchone()[0], "Original")
        automatic_backup(); automatic_backup()
        self.assertEqual(len(list((self.directory / "backups").glob("*-auto-*.sqlite3"))), 1)

    def test_restore_snapshot_into_file_and_keep_recovery(self):
        backup = create_backup("manual")
        target = self.directory / "database.sqlite3"
        with closing(sqlite3.connect(self.directory / "backups" / backup["name"])) as source, closing(sqlite3.connect(target)) as destination:
            source.backup(destination)
            destination.execute("UPDATE prospection_prospect SET nom='Modifie'")
            destination.commit()
        databases = {"default": {**settings.DATABASES["default"], "NAME": str(target)}}
        with patch.object(settings, "DATABASES", databases), patch("prospection.backups.call_command") as migrate:
            result = restore_backup(backup["name"])
        with closing(sqlite3.connect(target)) as db:
            self.assertEqual(db.execute("SELECT nom FROM prospection_prospect").fetchone()[0], "Original")
        self.assertTrue((self.directory / "backups" / result["recovery"]).exists())
        migrate.assert_called_once()

    def test_restore_rejects_path_traversal_active_jobs_and_worker(self):
        with self.assertRaises(ValueError):
            restore_backup("../db.sqlite3")
        backup = create_backup("manual")
        job = SearchJob.objects.create(status="queued")
        with self.assertRaises(ValueError):
            restore_backup(backup["name"])
        job.delete()
        with worker_activity() as acquired:
            self.assertTrue(acquired)
            with self.assertRaises(ValueError):
                restore_backup(backup["name"])

    def test_invalid_sqlite_backup_is_rejected(self):
        path = self.directory / "invalid.sqlite3"
        with closing(sqlite3.connect(path)) as db:
            db.execute("CREATE TABLE example (id integer)")
            db.commit()
        with self.assertRaises(ValueError):
            validate_backup(path)

    def test_windows_secret_roundtrip_is_encrypted_and_preserves_fields(self):
        if os.name != "nt":
            self.skipTest("Windows DPAPI")
        value = b"fake-secret-for-test-only"
        encrypted = protect(value)
        self.assertNotIn(value, encrypted)
        self.assertEqual(protect(encrypted, decrypt=True), value)
        save_private_settings(brevo_api_key=value.decode())
        save_private_settings(sender_email="test@sender.example")
        self.assertEqual(load_settings()["brevo_api_key"], value.decode())
        self.assertEqual(load_settings()["sender_email"], "test@sender.example")
