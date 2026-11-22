import json
from datetime import timedelta
from email.utils import format_datetime
from unittest.mock import patch
import requests
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from .consultations import ConsultationError, job_consultations
from .jobs import enqueue_qualification, recover_jobs, run_next_job
from .models import Campaign, EmailDraft, EmailLog, Prospect, QualificationReview, SearchJob, ServiceCache
from . import test_discovery as discovery_fixtures


@override_settings(DISCOVERY_PROVIDER='tavily', DISCOVERY_ENABLED=True, TAVILY_API_KEY='fictive-secret',
                   TAVILY_DAILY_LIMIT=20, TAVILY_MONTHLY_LIMIT=600,
                   HTTP_DOMAIN_INTERVAL=0, HTTP_SOURCE_INTERVAL=0,
                   HTTP_DOMAIN_BUDGET=200, HTTP_SOURCE_BUDGET=200)
class C1ProviderTests(TestCase):
    def search(self, query='Entreprise fictive Testville'):
        from .search_providers import search
        return search(query)

    def response(self, code=200, payload=None, headers=None):
        r=requests.Response();r.status_code=code;r.url='https://api.tavily.com/search'
        r._content=json.dumps(payload if payload is not None else {'results':[]}).encode()
        r.headers.update(headers or {});return r

    def test_disabled_and_missing_key_never_call_network(self):
        with patch('prospection.consultations.requests.request') as wire:
            for settings in [dict(DISCOVERY_ENABLED=False),dict(TAVILY_API_KEY=''),dict(DISCOVERY_PROVIDER='unknown')]:
                with self.settings(**settings), self.assertRaises(ConsultationError):self.search()
            wire.assert_not_called()

    def test_basic_only_sanitized_results_cache_and_secret_not_persisted(self):
        with patch('prospection.consultations.requests.request',return_value=self.response(payload={'results':[
            {'url':'https://exemple.test/','content':'Un extrait ne constitue pas une preuve'},
            {'url':'https://exemple.test/#fragment'}, {'url':'file:///secret'}]})) as wire:
            first=self.search();second=self.search()
        self.assertEqual(first,second);self.assertEqual(first['urls'],['https://exemple.test/'])
        self.assertEqual(wire.call_count,1)
        args=wire.call_args.kwargs
        self.assertEqual(args['json']['search_depth'],'basic');self.assertFalse(args['json']['auto_parameters'])
        self.assertFalse(args['json']['include_answer']);self.assertFalse(args['json']['include_raw_content'])
        self.assertNotIn('fictive-secret',str(list(ServiceCache.objects.values_list('value',flat=True))))

    def test_daily_and_monthly_caps_block_before_http_and_survive_expired_cache_ttl(self):
        with patch('prospection.consultations.requests.request',return_value=self.response()) as wire:
            with self.settings(TAVILY_DAILY_LIMIT=1):
                self.search('one')
                with self.assertRaises(ConsultationError) as caught:self.search('two')
                self.assertTrue(caught.exception.deferred)
            ServiceCache.objects.update(expires_at=timezone.now()-timedelta(days=1))
            with self.settings(TAVILY_MONTHLY_LIMIT=1),self.assertRaises(ConsultationError):self.search('three')
        self.assertEqual(wire.call_count,1)

    def test_429_seconds_and_date_5xx_network_and_forbidden(self):
        for code,header in [(429,'120'),(429,format_datetime(timezone.now()+timedelta(minutes=3))),
                            (503,None),(403,None),(401,None),(432,None),(433,None)]:
            with self.subTest(code=code,header=header):
                ServiceCache.objects.all().delete()
                with patch('prospection.consultations.requests.request',return_value=self.response(code,headers={'Retry-After':header} if header else {})):
                    with self.assertRaises(ConsultationError) as caught:self.search()
                self.assertEqual(caught.exception.temporary,code in {429,503})
                if code==429:self.assertGreater(caught.exception.retry_at,timezone.now()+timedelta(seconds=100))
        ServiceCache.objects.all().delete()
        with patch('prospection.consultations.requests.request',side_effect=requests.ConnectionError('fictive-secret')):
            with self.assertRaises(ConsultationError) as caught:self.search()
            self.assertTrue(caught.exception.temporary);self.assertNotIn('fictive-secret',str(caught.exception))

    def test_malformed_json_is_not_a_completed_empty_search(self):
        with patch('prospection.consultations.requests.request',return_value=self.response(payload={'unexpected':[]})):
            with self.assertRaises(ConsultationError):self.search()

    def test_each_calendar_day_and_month_has_its_own_budget(self):
        clock=timezone.now().replace(day=10,hour=12,minute=0,second=0,microsecond=0)
        with self.settings(TAVILY_DAILY_LIMIT=1,TAVILY_MONTHLY_LIMIT=2),patch('prospection.consultations.requests.request',return_value=self.response()) as wire:
            with patch('django.utils.timezone.now',return_value=clock):self.search('day one')
            with patch('django.utils.timezone.now',return_value=clock+timedelta(days=1)):self.search('day two')
            with patch('django.utils.timezone.now',return_value=clock+timedelta(days=2)),self.assertRaises(ConsultationError):self.search('blocked month')
            next_month=(clock.replace(day=28)+timedelta(days=5)).replace(day=1)
            with patch('django.utils.timezone.now',return_value=next_month):self.search('next month')
        self.assertEqual(wire.call_count,3)

    def test_interruption_after_http_response_reuses_job_cache_without_another_credit(self):
        job=SearchJob.objects.create(status='running')
        with job_consultations(job),patch('prospection.consultations.requests.request',return_value=self.response()) as wire:
            with patch('prospection.search_providers.store_value',side_effect=RuntimeError('Interruption simulée')):
                with self.assertRaises(RuntimeError):self.search()
            self.search()
        self.assertEqual(wire.call_count,1)

    def test_different_json_queries_have_different_job_cache_entries(self):
        job=SearchJob.objects.create(status='running')
        with job_consultations(job),patch('prospection.consultations.requests.request',return_value=self.response()) as wire:
            self.search('one');self.search('two')
        self.assertEqual(wire.call_count,2)


@override_settings(DISCOVERY_PROVIDER='tavily',DISCOVERY_ENABLED=True,TAVILY_API_KEY='fictional',
                   DESKTOP_AUTO_AUTH=False,OWNER_ACCESS_TOKEN='',REQUIRE_OWNER_TOKEN=False,DEMO_MODE=False,
                   HTTP_DOMAIN_INTERVAL=0,HTTP_SOURCE_INTERVAL=0,HTTP_DOMAIN_BUDGET=200,
                   HTTP_SOURCE_BUDGET=200,WEBSITE_EMAIL_MAX_LOOKUPS=100)
class C1PipelineTests(TestCase):
    setUp=discovery_fixtures.DiscoveryTests.setUp
    search=discovery_fixtures.DiscoveryTests.search
    page=discovery_fixtures.DiscoveryTests.page
    run_discovery=discovery_fixtures.DiscoveryTests.run_discovery

    def respond(self, method,url,**kwargs):
        if url=='https://api.tavily.com/search':
            self.calls.append(url)
            from bs4 import BeautifulSoup
            urls=[a['href'] for a in BeautifulSoup(self.search_html,'html.parser').select('a[href]')]
            r=requests.Response();r.status_code=200;r.url=url
            r._content=json.dumps(getattr(self,'search_payload',{'results':[{'url':u} for u in urls]})).encode();return r
        return discovery_fixtures.DiscoveryTests.respond(self,method,url,**kwargs)

    def test_discovery_to_approval_and_explicit_legacy_regeneration(self):
        self.client=APIClient()
        url='https://annuaire-restos.fr/fiche/cafe-pins/'
        self.search(url);self.pages[url]=self.page(extra='<h2>Carte du midi</h2><p>Soupe et dessert.</p>')
        old=EmailDraft.objects.create(prospect=self.prospect,subject='Historique',body='Ancien générique',origin='legacy')
        job=self.run_discovery();self.assertEqual(job.status,'done')
        old.refresh_from_db();self.assertEqual(old.body,'Ancien générique')
        q=QualificationReview.objects.get(prospect=self.prospect)
        feed=self.client.get('/api/personal/qualification/?status=selection').data
        self.assertEqual(feed['count'],1)
        endpoint=f'/api/personal/contacts/{self.prospect.pk}/'
        draft=self.client.post(endpoint+'generate-draft/',{'expected_revision':old.revision},format='json')
        self.assertEqual(draft.status_code,200,draft.data)
        self.assertIn('Carte du midi',draft.data['body']);self.assertIn('NateOS',draft.data['body'])
        self.assertIn('https://nathaniel-dev.fr/',draft.data['body'])
        old.refresh_from_db();self.assertEqual(old.versions.get(number=1).body,'Ancien générique')
        approved=self.client.post(f'/api/personal/qualification/{q.pk}/approve/',{'revision':old.revision},format='json')
        self.assertEqual(approved.status_code,200,approved.data)
        updated=self.client.put(endpoint+'draft/',{'body':old.body+'\nPrécision fictive.',
                                 'expected_revision':old.revision},format='json')
        self.assertEqual(updated.status_code,200,updated.data);self.assertIsNone(updated.data['approved_revision'])
        self.assertFalse(EmailLog.objects.exists())

    def test_omission_reasons_are_exposed_without_changing_criteria(self):
        QualificationReview.objects.create(prospect=self.prospect,status='pending')
        result=APIClient().get('/api/personal/qualification/?status=enrich').data
        self.assertEqual(result['count'],1)
        self.assertEqual(result['results'][0]['selection_diagnostic']['code'],'contact_invalid')
        self.assertIn('contact_invalid',result['selection']['omitted_counts'])

    def test_provider_retry_deadline_persists_and_failed_historical_job_is_not_requeued(self):
        old=SearchJob.objects.create(prospect=self.prospect,kind='qualification',status='error',error='Ancien refus robots')
        original=self.respond
        def respond(method,url,**kwargs):
            if url=='https://api.tavily.com/search':
                r=requests.Response();r.status_code=429;r.url=url;r.headers['Retry-After']='120';r._content=b'';return r
            return original(method,url,**kwargs)
        with patch('prospection.consultations.requests.request',side_effect=respond):
            job=self.run_discovery()
        self.assertEqual(job.status,'queued')
        due=job.next_run_at;recover_jobs();self.assertFalse(run_next_job())
        job.refresh_from_db();self.assertEqual(job.next_run_at,due)
        old.refresh_from_db();self.assertEqual(old.status,'error')
