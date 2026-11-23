import json
from datetime import timedelta
from unittest.mock import patch

import requests
from django.test import TestCase, override_settings
from django.utils import timezone

from .consultations import ConsultationError, job_consultations
from .jobs import enqueue_search, recover_jobs, run_next_job
from .models import Campaign, Prospect, SearchJob
from .services import _query_overpass


ENDPOINTS = ['https://one.example/api/interpreter', 'https://two.example/api/interpreter']
ELEMENT = {'type': 'node', 'id': 17, 'tags': {'name': 'Restaurant fictif', 'addr:city': 'Testville'}}


@override_settings(OVERPASS_ENDPOINTS=ENDPOINTS, OVERPASS_TOTAL_TIMEOUT=10,
                   OVERPASS_ENDPOINT_TIMEOUT=6, OVERPASS_TIMEOUT=8,
                   HTTP_SOURCE_INTERVAL=0, HTTP_DOMAIN_INTERVAL=0,
                   HTTP_SOURCE_BUDGET=100, HTTP_DOMAIN_BUDGET=100)
class OverpassFallbackTests(TestCase):
    def response(self, code=200, data=None, headers=None):
        response = requests.Response()
        response.status_code = code
        response.url = ENDPOINTS[0]
        response._content = json.dumps(data if data is not None else {'elements': [ELEMENT]}).encode()
        response.headers.update(headers or {})
        return response

    def query(self):
        return _query_overpass('"amenity"="restaurant"', '48', '-1', 1000)

    def test_timeout_uses_next_endpoint_and_deduplicates_osm_identity(self):
        duplicate = dict(ELEMENT)
        way = {**ELEMENT, 'type': 'way'}
        response = self.response(data={'elements': [ELEMENT, duplicate, way]})
        with patch('prospection.consultations.requests.request', side_effect=[requests.ReadTimeout(), response]) as wire:
            rows = self.query()
        self.assertEqual([(r['type'], r['id']) for r in rows], [('node', 17), ('way', 17)])
        self.assertEqual([c.args[1] for c in wire.call_args_list], ENDPOINTS)

    def test_all_endpoints_unavailable_raise_temporary_error_with_each_cause(self):
        with patch('prospection.consultations.requests.request', side_effect=requests.ConnectionError()) as wire:
            with self.assertRaises(ConsultationError) as caught:
                self.query()
        self.assertEqual(wire.call_count, 2)
        self.assertTrue(caught.exception.temporary)
        self.assertIn('Overpass', str(caught.exception))

    def test_global_deadline_stops_before_another_request(self):
        clock = [100.0]
        def timeout(*args, **kwargs):
            clock[0] += 11
            raise requests.ReadTimeout()
        with patch('prospection.services.time.monotonic', side_effect=lambda: clock[0]), \
             patch('prospection.consultations.requests.request', side_effect=timeout) as wire:
            with self.assertRaises(ConsultationError) as caught:
                self.query()
        self.assertEqual(wire.call_count, 1)
        self.assertTrue(caught.exception.temporary)

    def test_next_attempt_uses_only_remaining_global_budget(self):
        clock = [100.0]
        def answer(method, url, **kwargs):
            if url == ENDPOINTS[0]:
                clock[0] += 9.5
                raise requests.ReadTimeout()
            self.assertLessEqual(kwargs['timeout'], 0.5)
            return self.response()
        with patch('prospection.services.time.monotonic', side_effect=lambda: clock[0]), \
             patch('prospection.consultations.requests.request', side_effect=answer):
            self.assertEqual(len(self.query()), 1)

    def test_valid_empty_response_does_not_probe_another_instance(self):
        with patch('prospection.consultations.requests.request', return_value=self.response(data={'elements': []})) as wire:
            self.assertEqual(self.query(), [])
        self.assertEqual(wire.call_count, 1)

    def test_refusal_quota_and_provider_cooldown_do_not_route_around_restrictions(self):
        from .models import ServiceCache
        for code in [403, 429, 503]:
            with self.subTest(code=code):
                ServiceCache.objects.all().delete()
                response = self.response(code, headers={'Retry-After': '120'})
                with patch('prospection.consultations.requests.request', return_value=response) as wire:
                    with self.assertRaises(ConsultationError) as caught:
                        self.query()
                self.assertEqual(caught.exception.http_status, code)
                self.assertEqual(wire.call_count, 1)
                if code in {429, 503}:
                    self.assertGreater(caught.exception.retry_at, timezone.now() + timedelta(seconds=110))

    def test_invalid_response_is_not_masked_by_another_instance_or_empty_result(self):
        from .models import ServiceCache
        for data in [{'unexpected': []}, {'elements': ['invalid']}, {'elements': [], 'remark': 'runtime error'}]:
            with self.subTest(data=data):
                ServiceCache.objects.all().delete()
                with patch('prospection.consultations.requests.request', return_value=self.response(data=data)) as wire:
                    with self.assertRaises(ConsultationError):
                        self.query()
                self.assertEqual(wire.call_count, 1)

    def test_tls_errors_are_not_bypassed(self):
        with patch('prospection.consultations.requests.request', side_effect=requests.exceptions.SSLError()) as wire:
            with self.assertRaises(ConsultationError):
                self.query()
        self.assertEqual(wire.call_count, 1)

    def test_malformed_element_type_remains_a_temporary_response_error(self):
        response = self.response(data={'elements': [{'type': [], 'id': 17}]})
        with patch('prospection.consultations.requests.request', return_value=response):
            with self.assertRaises(ConsultationError) as caught:
                self.query()
        self.assertTrue(caught.exception.temporary)

    def test_invalid_response_is_not_replayed_from_persistent_cache(self):
        job = SearchJob.objects.create(status='running')
        invalid = self.response(data={'elements': [], 'remark': 'runtime error'})
        with job_consultations(job), patch(
            'prospection.consultations.requests.request', side_effect=[invalid, self.response()],
        ) as wire:
            with self.assertRaises(ConsultationError):
                self.query()
            self.assertEqual(self.query(), [ELEMENT])
            self.assertEqual(self.query(), [ELEMENT])
        self.assertEqual(wire.call_count, 2)

    def test_programming_error_is_not_hidden_as_network_failure(self):
        with patch('prospection.consultations.requests.request', side_effect=TypeError('Fictive programming error')) as wire:
            with self.assertRaises(TypeError):
                self.query()
        self.assertEqual(wire.call_count, 1)

    @override_settings(HTTP_SOURCE_INTERVAL=1)
    def test_persistent_resume_skips_failed_endpoint_after_rate_limit_wait(self):
        campaign = Campaign.objects.create(secteur='restaurant', ville='Testville', rayon_km=1)
        job = enqueue_search(campaign)
        job.payload = {"company_discovery_provider": "overpass"}
        job.save(update_fields=["payload"])
        def answer(method, url, **kwargs):
            if url == ENDPOINTS[0]:
                raise requests.ConnectionError()
            return self.response()
        with patch('prospection.services._get_city_coords', return_value=('48', '-1')), \
             patch('prospection.consultations.requests.request', side_effect=answer) as wire:
            self.assertTrue(run_next_job())
            job.refresh_from_db()
            self.assertEqual(job.status, 'queued')
            self.assertEqual(job.attempts, 0)
            recover_jobs()
            self.assertFalse(run_next_job())
            due = job.next_run_at
            with patch('django.utils.timezone.now', return_value=due + timedelta(seconds=1)):
                self.assertTrue(run_next_job())
        job.refresh_from_db()
        self.assertEqual(job.status, 'done')
        self.assertEqual(Prospect.objects.count(), 1)
        self.assertEqual([c.args[1] for c in wire.call_args_list], ENDPOINTS)
        self.assertEqual(job.payload['overpass']['failures'][0]['reason'], 'ConnectionError')
