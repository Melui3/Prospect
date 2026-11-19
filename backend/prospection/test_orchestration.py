from datetime import timedelta
from email.utils import format_datetime
from unittest.mock import Mock, patch

import requests
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from .models import Campaign, EmailDraft, Prospect, QualificationReview, SearchJob, ServiceCache
from .jobs import enqueue_search, recover_jobs, run_next_job


@override_settings(DESKTOP_AUTO_AUTH=False, OWNER_ACCESS_TOKEN="", REQUIRE_OWNER_TOKEN=False, DEMO_MODE=False)
class OrchestrationTests(TestCase):
    def setUp(self):
        self.campaign = Campaign.objects.create(secteur="restaurant", ville="Testville", rayon_km=1)
        self.client = APIClient()

    def test_both_launch_routes_share_one_persistent_job(self):
        with patch("prospection.views.start_campaign_worker") as thread:
            old = self.client.post(f"/api/campaigns/{self.campaign.pk}/launch/")
            new = self.client.post(f"/api/personal/campaigns/{self.campaign.pk}/launch/")
        self.assertEqual(old.status_code, 202)
        self.assertEqual(new.status_code, 202)
        self.assertEqual(SearchJob.objects.count(), 1)
        thread.assert_not_called()

    def test_recovery_keeps_future_deadline_and_exhausted_budget(self):
        due = timezone.now() + timedelta(hours=1)
        job = SearchJob.objects.create(campaign=self.campaign, status="running", attempts=3, next_run_at=due)
        recover_jobs()
        job.refresh_from_db()
        self.assertEqual(job.next_run_at, due)
        self.assertEqual(job.status, "error")

    @patch("prospection.services._query_overpass", return_value=[])
    @patch("prospection.services._get_city_coords", return_value=("1", "2"))
    def test_empty_search_reports_empty_scope(self, coords, overpass):
        job = enqueue_search(self.campaign)
        run_next_job()
        job.refresh_from_db()
        self.assertEqual(job.payload["outcome"], "no_results")
        self.assertEqual(job.status, "done")
        self.assertEqual(EmailDraft.objects.count(), 0)

    def test_missing_proofs_is_not_success(self):
        prospect = Prospect.objects.create(nom="Fictive", ville="Testville", email="contact@fictive.example")
        job = SearchJob.objects.create(prospect=prospect, kind="qualification")
        run_next_job()
        job.refresh_from_db()
        self.assertEqual(job.payload["outcome"], "insufficient_evidence")
        self.assertEqual(job.stage, "À enrichir")

    def test_legacy_done_job_does_not_claim_verified_success(self):
        job = SearchJob.objects.create(campaign=self.campaign, status="done")
        response = self.client.get(f"/api/personal/jobs/{job.pk}/")
        self.assertEqual(response.data["outcome"], "unrecorded")

    @patch("prospection.services._get_city_coords")
    def test_not_due_job_does_not_call_network(self, coords):
        SearchJob.objects.create(campaign=self.campaign, next_run_at=timezone.now()+timedelta(hours=1))
        self.assertFalse(run_next_job())
        coords.assert_not_called()


@override_settings(HTTP_DOMAIN_INTERVAL=0, HTTP_SOURCE_INTERVAL=0, HTTP_DOMAIN_BUDGET=20, HTTP_SOURCE_BUDGET=20)
class ConsultationTests(TestCase):
    def response(self, code=200, retry=None, text="ok"):
        result = requests.Response()
        result.status_code = code
        result.url = "https://source.example/page"
        result._content = text.encode()
        result.headers["Content-Type"] = "text/html; charset=utf-8"
        if retry is not None:
            result.headers["Retry-After"] = str(retry)
        return result

    def test_429_seconds_and_date_persist_provider_deadline(self):
        from .consultations import ConsultationError, request
        for retry in ["120", format_datetime(timezone.now()+timedelta(minutes=5), usegmt=True)]:
            ServiceCache.objects.all().delete()
            with patch("prospection.consultations.requests.request", return_value=self.response(429,retry)) as wire:
                with self.assertRaises(ConsultationError) as caught:
                    request("GET","https://source.example/page",source="website",timeout=1)
                self.assertTrue(caught.exception.temporary)
                self.assertGreater(caught.exception.retry_at,timezone.now()+timedelta(seconds=110))
                with self.assertRaises(ConsultationError):
                    request("GET","https://source.example/other",source="website",timeout=1)
                self.assertEqual(wire.call_count,1)

    def test_permanent_and_temporary_failures(self):
        from .consultations import ConsultationError, request
        for code,temporary in [(403,False),(404,False),(500,True),(503,True)]:
            ServiceCache.objects.all().delete()
            with patch("prospection.consultations.requests.request",return_value=self.response(code)):
                with self.assertRaises(ConsultationError) as caught:
                    request("GET","https://source.example/page",source="website",timeout=1)
                self.assertEqual(caught.exception.temporary,temporary)
                self.assertEqual(caught.exception.http_status,code)

    def test_network_failure_is_retryable(self):
        from .consultations import ConsultationError, request
        with patch("prospection.consultations.requests.request",side_effect=requests.Timeout):
            with self.assertRaises(ConsultationError) as caught:
                request("GET","https://source.example/page",source="website",timeout=1)
            self.assertTrue(caught.exception.temporary)

    @override_settings(HTTP_DOMAIN_BUDGET=1)
    def test_domain_budget_is_shared_between_jobs(self):
        from .consultations import ConsultationError, request
        with patch("prospection.consultations.requests.request",return_value=self.response()) as wire:
            request("GET","https://source.example/one",source="website",timeout=1)
            with self.assertRaises(ConsultationError) as caught:
                request("GET","https://source.example/two",source="website",timeout=1)
            self.assertTrue(caught.exception.deferred)
            self.assertEqual(wire.call_count,1)

    def test_cached_page_survives_restart_without_second_request(self):
        from .consultations import request, job_consultations
        job=SearchJob.objects.create(status="running")
        with patch("prospection.consultations.requests.request",return_value=self.response()) as wire:
            with job_consultations(job):
                first=request("GET","https://source.example/page",source="website",timeout=1)
            job.refresh_from_db()
            with job_consultations(job):
                second=request("GET","https://source.example/page",source="website",timeout=1)
            self.assertEqual(first.text,second.text)
            self.assertEqual(wire.call_count,1)

@override_settings(DESKTOP_AUTO_AUTH=False, OWNER_ACCESS_TOKEN="", REQUIRE_OWNER_TOKEN=False, DEMO_MODE=False)
class RecoveryAndPreservationTests(TestCase):
    def setUp(self):
        self.campaign = Campaign.objects.create(secteur="restaurant", ville="Testville", rayon_km=1)

    def test_job_retry_after_and_recovery_do_not_consult_before_deadline(self):
        from .consultations import ConsultationError
        deadline = timezone.now() + timedelta(hours=2)
        job = enqueue_search(self.campaign)
        failure = ConsultationError("source limitée", temporary=True, retry_at=deadline,
                                    source="overpass", http_status=429)
        with patch("prospection.services._get_city_coords", side_effect=failure) as network:
            run_next_job()
            job.refresh_from_db()
            self.assertEqual(job.status, "queued")
            self.assertGreaterEqual(job.next_run_at, deadline)
            due = job.next_run_at
            recover_jobs()
            self.assertFalse(run_next_job())
            self.assertEqual(network.call_count, 1)
        job.refresh_from_db()
        self.assertEqual(job.next_run_at, due)
        self.assertEqual(job.payload["events"][-1]["http_status"], 429)

    def test_permanent_refusal_is_documented_and_never_retried(self):
        from .consultations import ConsultationError
        job = enqueue_search(self.campaign)
        with patch("prospection.services._get_city_coords",
                   side_effect=ConsultationError("HTTP 403", source="nominatim", http_status=403)) as network:
            run_next_job()
            recover_jobs()
            self.assertFalse(run_next_job())
            self.assertEqual(network.call_count, 1)
        job.refresh_from_db()
        self.assertEqual(job.payload["outcome"], "permanent_error")

    def test_quota_wait_does_not_consume_failure_budget(self):
        from .consultations import ConsultationError
        job = enqueue_search(self.campaign)
        with patch("prospection.services._get_city_coords", side_effect=ConsultationError(
            "quota", temporary=True, deferred=True, retry_at=timezone.now()+timedelta(hours=1))):
            run_next_job()
        job.refresh_from_db()
        self.assertEqual(job.attempts, 0)
        self.assertEqual(job.status, "queued")

    def test_pause_resume_preserves_deadline(self):
        due = timezone.now()+timedelta(hours=1)
        job=SearchJob.objects.create(campaign=self.campaign,status="paused",next_run_at=due,attempts=1)
        response=APIClient().post(f"/api/personal/jobs/{job.pk}/resume/")
        self.assertEqual(response.status_code,200)
        job.refresh_from_db()
        self.assertEqual(job.next_run_at,due)

    def test_recurrence_with_active_job_keeps_due_date(self):
        from .jobs import enqueue_due_scheduled_searches
        due=timezone.now()-timedelta(minutes=1)
        self.campaign.repeat_days=7
        self.campaign.next_search_at=due
        self.campaign.save()
        SearchJob.objects.create(campaign=self.campaign,status="paused")
        self.assertEqual(enqueue_due_scheduled_searches(),0)
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.next_search_at,due)

    def test_partial_capture_restart_preserves_historical_data_without_duplicates(self):
        from .identity import capture_prospect
        element={"type":"node","id":123,"tags":{"name":"Fictive","email":"contact@fictive.example","addr:city":"Testville"}}
        prospect=capture_prospect(self.campaign,element)
        review=QualificationReview.objects.create(prospect=prospect,status="approved",evidence=[{"kind":"historical"}])
        draft=EmailDraft.objects.create(prospect=prospect,subject="Historique",body="Texte relu")
        before=(review.evidence,draft.body,self.campaign.created_at)
        job=SearchJob.objects.create(campaign=self.campaign,status="running",
            payload={"elements":[element],"capture_index":0,"ids":[],"enrich_index":0})
        recover_jobs()
        with patch("prospection.services._query_overpass") as overpass:
            run_next_job()
            overpass.assert_not_called()
        self.assertEqual(Prospect.objects.count(),1)
        self.assertEqual(self.campaign.discovered_prospects.count(),1)
        review.refresh_from_db();draft.refresh_from_db();self.campaign.refresh_from_db()
        self.assertEqual((review.evidence,draft.body,self.campaign.created_at),before)

    def test_qualification_temporary_failure_keeps_old_proofs_and_draft(self):
        from .consultations import ConsultationError
        p=Prospect.objects.create(nom="Fictive",ville="Testville",email="contact@fictive.example",
                                  website="https://fictive.example/")
        q=QualificationReview.objects.create(prospect=p,status="unverified",evidence=[{"kind":"old"}])
        d=EmailDraft.objects.create(prospect=p,subject="Ancien",body="À conserver")
        job=SearchJob.objects.create(prospect=p,kind="qualification")
        with patch("prospection.qualification._get_public_page",side_effect=ConsultationError(
            "HTTP 503",temporary=True,http_status=503)):
            run_next_job()
        job.refresh_from_db();q.refresh_from_db();d.refresh_from_db()
        self.assertEqual(job.status,"queued")
        self.assertEqual(q.evidence,[{"kind":"old"}])
        self.assertEqual(d.body,"À conserver")

    def test_refused_optional_contact_page_does_not_create_negative_cache(self):
        from .consultations import ConsultationError
        from .services import _find_email_on_website
        from .cache import cached_value
        page=Mock(text="<html></html>",url="https://fictive.example/")
        with patch("prospection.services._get_public_page",side_effect=[
            page, ConsultationError("HTTP 429",temporary=True,http_status=429)]):
            with self.assertRaises(ConsultationError):
                _find_email_on_website("https://fictive.example/")
        self.assertIsNone(cached_value("website:https://fictive.example/"))

    def test_excluded_prospect_does_not_trigger_enrichment(self):
        from .identity import capture_prospect
        element={"type":"node","id":123,"tags":{"name":"Fictive","addr:city":"Testville"}}
        p=capture_prospect(self.campaign,element)
        p.status="do_not_contact";p.save()
        job=SearchJob.objects.create(campaign=self.campaign,
            payload={"elements":[element],"capture_index":1,"ids":[p.pk],"enrich_index":0})
        with patch("prospection.enrichment.enrich_prospect") as enrich:
            run_next_job()
            enrich.assert_not_called()
        job.refresh_from_db()
        self.assertEqual(job.payload["outcome"],"excluded")

    @override_settings(HTTP_SOURCE_INTERVAL=0,HTTP_DOMAIN_INTERVAL=0,WEBSITE_EMAIL_MAX_LOOKUPS=1)
    def test_per_task_budget_survives_restart(self):
        from .consultations import ConsultationError,job_consultations,request
        job=SearchJob.objects.create(status="running")
        response=requests.Response();response.status_code=200;response._content=b"ok"
        response.url="https://fictive.example/";response.encoding="utf-8"
        with patch("prospection.consultations.requests.request",return_value=response) as wire:
            with job_consultations(job):
                request("GET","https://fictive.example/1",source="website",timeout=1)
            job.refresh_from_db()
            with job_consultations(job):
                with self.assertRaises(ConsultationError) as caught:
                    request("GET","https://fictive.example/2",source="website",timeout=1)
            self.assertFalse(caught.exception.temporary)
            self.assertEqual(wire.call_count,1)

    def test_worker_interruption_restarts_without_requerying_completed_search(self):
        from .identity import capture_prospect
        element={"type":"node","id":444,"tags":{"name":"Fictive","addr:city":"Testville"}}
        job=enqueue_search(self.campaign)
        def interrupted(current):
            current.payload.update({"elements":[element],"capture_index":1,"ids":[],"enrich_index":0})
            item=capture_prospect(self.campaign,element)
            current.payload["ids"]=[item.pk]
            from .jobs import checkpoint
            checkpoint(current,payload=current.payload)
            raise KeyboardInterrupt()
        with patch("prospection.jobs.process_search",side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt):
                run_next_job()
        job.refresh_from_db()
        self.assertEqual(job.status,"running")
        recover_jobs()
        with patch("prospection.services._query_overpass") as overpass, patch("prospection.enrichment.enrich_prospect"):
            run_next_job()
            overpass.assert_not_called()
        job.refresh_from_db()
        self.assertEqual(job.status,"done")
        self.assertEqual(Prospect.objects.count(),1)

    def test_retry_exhaustion_is_terminal_after_worker_restart(self):
        from .consultations import ConsultationError
        job=enqueue_search(self.campaign)
        with patch("prospection.services._get_city_coords",side_effect=ConsultationError(
            "indisponible",temporary=True)) as wire:
            for attempt in range(3):
                SearchJob.objects.filter(pk=job.pk).update(next_run_at=timezone.now())
                run_next_job()
            job.refresh_from_db()
            self.assertEqual(job.status,"error")
            self.assertEqual(job.attempts,3)
            recover_jobs()
            self.assertFalse(run_next_job())
            self.assertEqual(wire.call_count,3)

    @override_settings(HTTP_DOMAIN_INTERVAL=0,HTTP_SOURCE_INTERVAL=0,HTTP_SOURCE_BUDGET=1)
    def test_source_budget_applies_across_different_domains(self):
        from .consultations import ConsultationError,request
        response=requests.Response();response.status_code=200;response._content=b"ok"
        response.url="https://one.example/"
        with patch("prospection.consultations.requests.request",return_value=response) as wire:
            request("GET","https://one.example/",source="overpass",timeout=1)
            with self.assertRaises(ConsultationError):
                request("GET","https://two.example/",source="overpass",timeout=1)
            self.assertEqual(wire.call_count,1)

    def test_interactive_check_returns_clear_error_without_mutation(self):
        from .consultations import ConsultationError
        p=Prospect.objects.create(nom="Fictive",ville="Testville",website="https://fictive.example/")
        review=QualificationReview.objects.create(prospect=p,status="unverified",evidence=[{"kind":"old"}])
        with patch("prospection.qualification._get_public_page",side_effect=ConsultationError(
            "HTTP 429",temporary=True,http_status=429,retry_at=timezone.now()+timedelta(hours=1))):
            response=APIClient().post(f"/api/personal/qualification/{review.pk}/evidence/",{"check_site":True},format="json")
        self.assertEqual(response.status_code,503)
        self.assertEqual(response.data["outcome"],"temporary_error")
        review.refresh_from_db()
        self.assertEqual(review.evidence,[{"kind":"old"}])
