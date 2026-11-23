import json
from datetime import timedelta
from unittest.mock import patch
import requests
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from .models import Campaign, SearchJob, Prospect, ServiceCache
from .jobs import run_next_job, recover_jobs, enqueue_search
from .consultations import ConsultationError, job_consultations, request

@override_settings(HTTP_SOURCE_INTERVAL=0, HTTP_DOMAIN_INTERVAL=0,
 HTTP_SOURCE_BUDGET=100, HTTP_DOMAIN_BUDGET=100, DISCOVERY_ENABLED=True,
 DISCOVERY_PROVIDER='tavily', TAVILY_API_KEY='fictional', REQUIRE_OWNER_TOKEN=False,
 OWNER_ACCESS_TOKEN='', DESKTOP_AUTO_AUTH=False, DEMO_MODE=False)
class PilotLimitTests(TestCase):
 def setUp(self):
  self.campaign=Campaign.objects.create(secteur='restaurant',ville='Testville',repeat_days=7)
 def pilot(self):
  from .run_limits import schedule_pilot
  root=schedule_pilot(self.campaign, timezone.now()+timedelta(seconds=1))
  SearchJob.objects.filter(pk=root.pk).update(next_run_at=timezone.now()-timedelta(seconds=1))
  root.refresh_from_db();return root
 def child(self,root,**values):
  p=Prospect.objects.create(nom='Entreprise fictive',ville='Testville',campaign=self.campaign)
  return SearchJob.objects.create(prospect=p,kind='qualification',parent_search=root,**values)
 def response(self):
  r=requests.Response();r.status_code=200;r.url='https://api.tavily.com/search';r._content=b'{"results": []}';return r
 def test_stop_finished_parent_pauses_children_and_cancels_recurrence(self):
  root=SearchJob.objects.create(campaign=self.campaign,status='done')
  child=self.child(root)
  other=SearchJob.objects.create(kind='qualification')
  self.campaign.next_search_at=timezone.now()+timedelta(days=7);self.campaign.save()
  result=APIClient().post(f'/api/personal/campaigns/{self.campaign.pk}/stop/')
  self.assertEqual(result.status_code,200)
  child.refresh_from_db();other.refresh_from_db();self.campaign.refresh_from_db()
  self.assertEqual(child.status,'paused');self.assertEqual(other.status,'queued')
  self.assertEqual(self.campaign.repeat_days,0);self.assertIsNone(self.campaign.next_search_at)
  recover_jobs();self.assertFalse(SearchJob.objects.filter(pk=child.pk,status='queued').exists())
 def test_existing_pause_endpoint_stops_finished_search_family(self):
  root=SearchJob.objects.create(campaign=self.campaign,status='done');child=self.child(root)
  self.assertEqual(APIClient().post(f'/api/personal/jobs/{root.pk}/pause/').status_code,200)
  child.refresh_from_db();self.assertEqual(child.status,'paused')
 def test_pilot_only_arms_once_and_never_recurrs(self):
  from .run_limits import schedule_pilot
  root=self.pilot();self.campaign.refresh_from_db()
  self.assertEqual(self.campaign.repeat_days,0)
  with self.assertRaises(ValueError):schedule_pilot(self.campaign,timezone.now()+timedelta(minutes=1))
  root.status='done';root.save(update_fields=['status'])
  with self.assertRaises(ValueError):enqueue_search(self.campaign)
  result=APIClient().post(f'/api/personal/campaigns/{self.campaign.pk}/schedule/',{'repeat_days':7},format='json')
  self.assertEqual(result.status_code,409)
 def test_capture_is_bounded_before_creating_records_and_links_children(self):
  root=self.pilot()
  rows=[{'type':'node','id':i,'tags':{'name':f'Entreprise fictive {i}','addr:city':'Testville'}} for i in range(9)]
  with patch('prospection.services._get_city_coords',return_value=('48','-1')),patch('prospection.company_discovery.discover_companies',return_value=rows):
   self.assertTrue(run_next_job())
  root.refresh_from_db()
  self.assertEqual(Prospect.objects.count(),5);self.assertEqual(len(root.payload['ids']),5)
  self.assertEqual(SearchJob.objects.filter(parent_search=root).count(),5)
  self.assertEqual(root.payload['pilot_omitted_count'],4)
 def test_five_tavily_attempts_shared_across_children_even_on_network_error(self):
  from .search_providers import search
  from .run_limits import PilotStopped
  root=self.pilot()
  with patch('prospection.consultations.requests.request',side_effect=requests.ConnectionError()) as wire:
   for i in range(5):
    child=self.child(root,status='running')
    with job_consultations(child):
     with self.assertRaises(ConsultationError):search(f'fictive query {i}')
   child=self.child(root,status='running')
   with job_consultations(child):
    with self.assertRaises(PilotStopped):search('sixth fictive query')
  self.assertEqual(wire.call_count,5);root.refresh_from_db();self.assertEqual(root.pilot_tavily_attempts,5)
 def test_deadline_survives_restart_and_expired_jobs_never_consult(self):
  root=self.pilot();child=self.child(root,status='running');original=root.pilot_deadline
  recover_jobs();root.refresh_from_db();self.assertEqual(root.pilot_deadline,original)
  with patch('django.utils.timezone.now',return_value=original+timedelta(seconds=1)),patch('prospection.consultations.requests.request') as wire:
   self.assertFalse(run_next_job());wire.assert_not_called()
  root.refresh_from_db();child.refresh_from_db();self.assertIsNotNone(root.stopped_at);self.assertEqual(child.status,'paused')
 def test_stopped_child_cannot_consult_or_resume(self):
  from .run_limits import stop_campaign, PilotStopped
  root=self.pilot();child=self.child(root,status='running');stop_campaign(self.campaign.pk)
  with patch('prospection.consultations.requests.request') as wire:
   with self.assertRaises(PilotStopped):
    with job_consultations(child):request('GET','https://source.example/',source='website')
   wire.assert_not_called()
  result=APIClient().post(f'/api/personal/jobs/{child.pk}/resume/')
  self.assertEqual(result.status_code,409)
 def test_response_arriving_after_deadline_is_rejected(self):
  from .run_limits import PilotStopped
  root=self.pilot();child=self.child(root,status='running')
  clock=[timezone.now()]
  def answer(*args,**kwargs):
   self.assertLessEqual(kwargs['timeout'],1200)
   clock[0]=root.pilot_deadline+timedelta(seconds=1);return self.response()
  with patch('django.utils.timezone.now',side_effect=lambda:clock[0]),patch('prospection.consultations.requests.request',side_effect=answer):
   with job_consultations(child):
    with self.assertRaises(PilotStopped):request('GET','https://source.example/',source='website',timeout=9999)
  self.assertFalse(ServiceCache.objects.filter(value__has_key='body').exists())
 def test_global_budget_failure_does_not_spend_pilot_attempt(self):
  from .search_providers import search
  root=self.pilot();child=self.child(root,status='running')
  with self.settings(TAVILY_DAILY_LIMIT=0),job_consultations(child),patch('prospection.consultations.requests.request') as wire:
   with self.assertRaises(ConsultationError):search('fictive query')
   wire.assert_not_called()
  root.refresh_from_db();self.assertEqual(root.pilot_tavily_attempts,0)

 def test_legacy_child_is_reported_without_inventing_ownership(self):
  from .run_limits import stop_campaign
  root=SearchJob.objects.create(campaign=self.campaign,status='done')
  p=Prospect.objects.create(nom='Ancienne fiche fictive',ville='Testville')
  root.payload={'ids':[p.pk]};root.save(update_fields=['payload'])
  child=SearchJob.objects.create(prospect=p,kind='qualification')
  result=APIClient().post(f'/api/personal/campaigns/{self.campaign.pk}/stop/')
  self.assertEqual(result.status_code,409)
  child.refresh_from_db();self.assertEqual(child.status,'queued');self.assertIsNone(child.parent_search_id)
  root.refresh_from_db();self.assertIsNotNone(root.stopped_at)
  self.campaign.refresh_from_db();self.assertEqual(self.campaign.repeat_days,0)
 def test_campaign_cannot_be_deleted_with_active_qualification(self):
  root=SearchJob.objects.create(campaign=self.campaign,status='done');self.child(root)
  self.assertEqual(APIClient().delete(f'/api/personal/campaigns/{self.campaign.pk}/').status_code,409)
 def test_stopping_during_http_rejects_response_and_preserves_other_campaign(self):
  from .run_limits import stop_campaign, PilotStopped
  root=self.pilot();child=self.child(root,status='running')
  def answer(*args,**kwargs):
   stop_campaign(self.campaign.pk);return self.response()
  with patch('prospection.consultations.requests.request',side_effect=answer),job_consultations(child):
   with self.assertRaises(PilotStopped):request('GET','https://source.example/',source='website')
  self.assertFalse(ServiceCache.objects.filter(value__has_key='body').exists())
 def test_cached_searches_do_not_reserve_another_attempt(self):
  from .search_providers import search
  root=self.pilot();child=self.child(root,status='running')
  with job_consultations(child),patch('prospection.consultations.requests.request',return_value=self.response()) as wire:
   search('cached fictive query');search('cached fictive query')
  self.assertEqual(wire.call_count,1);root.refresh_from_db();self.assertEqual(root.pilot_tavily_attempts,1)
 def test_interruption_recovery_does_not_reset_attempts_or_duplicate_captures(self):
  root=self.pilot()
  rows=[{'type':'node','id':i,'tags':{'name':f'Entreprise fictive {i}'}} for i in range(8)]
  with patch('prospection.services._get_city_coords',return_value=('48','-1')),patch('prospection.company_discovery.discover_companies',return_value=rows) as overpass:
   run_next_job()
   SearchJob.objects.filter(pk=root.pk).update(status='running',pilot_tavily_attempts=3)
   recover_jobs();run_next_job()
  self.assertEqual(Prospect.objects.count(),5);self.assertEqual(overpass.call_count,1)
  root.refresh_from_db();self.assertEqual(root.pilot_tavily_attempts,3)
  self.assertEqual(SearchJob.objects.filter(parent_search=root).count(),5)
 def test_pilot_launch_api_refuses_second_occurrence(self):
  root=self.pilot();root.status='done';root.save(update_fields=['status'])
  self.assertEqual(APIClient().post(f'/api/personal/campaigns/{self.campaign.pk}/launch/').status_code,409)
 def test_ui_can_stop_after_search_is_finished(self):
  root=SearchJob.objects.create(campaign=self.campaign,status='done');self.child(root)
  self.campaign.repeat_days=0;self.campaign.save(update_fields=['repeat_days'])
  result=APIClient().get(f'/api/personal/campaigns/{self.campaign.pk}/')
  self.assertEqual(result.status_code,200);self.assertTrue(result.data['can_stop'])


 def test_public_route_cannot_delete_an_active_pilot(self):
  root=self.pilot();self.child(root)
  self.assertEqual(APIClient().delete(f'/api/campaigns/{self.campaign.pk}/').status_code,409)
  self.assertTrue(SearchJob.objects.filter(pk=root.pk).exists())
 def test_delete_stopped_campaign_preserves_child_provenance_and_limits(self):
  from .run_limits import stop_campaign
  root=self.pilot();child=self.child(root,status='error')
  root.status='error';root.save(update_fields=['status']);stop_campaign(self.campaign.pk)
  result=APIClient().delete(f'/api/personal/campaigns/{self.campaign.pk}/')
  self.assertEqual(result.status_code,204)
  root.refresh_from_db();child.refresh_from_db()
  self.assertEqual(child.parent_search_id,root.pk);self.assertIsNotNone(root.stopped_at)
  self.assertEqual(APIClient().post(f'/api/personal/jobs/{child.pk}/resume/').status_code,409)
 def test_qualification_write_is_rejected_after_stop(self):
  from .run_limits import stop_campaign,PilotStopped
  from .qualification import _save_review
  from .models import QualificationReview
  root=self.pilot();child=self.child(root,status='running')
  with job_consultations(child):
   stop_campaign(self.campaign.pk)
   with self.assertRaises(PilotStopped):_save_review(child.prospect,'excluded',['Fictive exclusion'],[])
  self.assertFalse(QualificationReview.objects.exists())
 def test_ambiguous_legacy_work_never_prevents_expiry_of_other_pilots(self):
  root=self.pilot()
  p=Prospect.objects.create(nom='Fictive independent work',ville='Testville')
  root.payload={'ids':[p.pk]};root.save(update_fields=['payload'])
  unrelated=SearchJob.objects.create(prospect=p,kind='qualification')
  with patch('django.utils.timezone.now',return_value=root.pilot_deadline+timedelta(seconds=1)):
   self.assertTrue(run_next_job())
  unrelated.refresh_from_db();self.assertIsNone(unrelated.parent_search_id)
  root.refresh_from_db();self.assertIsNotNone(root.stopped_at)

from . import test_c1 as c1_fixtures

@override_settings(DISCOVERY_ENABLED=True,DISCOVERY_PROVIDER='tavily',TAVILY_API_KEY='fictional',
 HTTP_SOURCE_INTERVAL=0,HTTP_DOMAIN_INTERVAL=0,HTTP_SOURCE_BUDGET=100,HTTP_DOMAIN_BUDGET=100,
 REQUIRE_OWNER_TOKEN=False,OWNER_ACCESS_TOKEN='',DESKTOP_AUTO_AUTH=False,DEMO_MODE=False)
class PilotPipelineTests(TestCase):
 setUp=c1_fixtures.C1PipelineTests.setUp
 search=c1_fixtures.C1PipelineTests.search
 page=c1_fixtures.C1PipelineTests.page
 respond=c1_fixtures.C1PipelineTests.respond
 def test_due_pilot_runs_to_personalized_unapproved_draft_without_manual_capture(self):
  from .run_limits import schedule_pilot
  from .models import EmailDraft,EmailLog,QualificationReview
  self.prospect.delete()
  url='https://annuaire-restos.fr/fiche/cafe-pins/'
  self.search(url);self.pages[url]=self.page(extra='<h2>Carte du midi</h2>')
  root=schedule_pilot(self.campaign,timezone.now()+timedelta(minutes=1))
  rows=[{'type':'node','id':987,'tags':{'name':'Café des Pins','addr:city':'Testville','amenity':'restaurant'}}]
  self.assertFalse(run_next_job())
  with patch('django.utils.timezone.now',return_value=root.next_run_at+timedelta(seconds=1)),patch('prospection.services._get_city_coords',return_value=('48','-1')),patch('prospection.company_discovery.discover_companies',return_value=rows):
   self.assertTrue(run_next_job());self.assertTrue(run_next_job());self.assertFalse(run_next_job())
  self.assertEqual(QualificationReview.objects.get().status,'pending')
  draft=EmailDraft.objects.get();self.assertIn('Carte du midi',draft.body);self.assertIn('https://nathaniel-dev.fr/',draft.body)
  self.assertIsNone(draft.approved_revision);self.assertFalse(EmailLog.objects.exists())
  root.refresh_from_db();self.assertEqual(root.pilot_tavily_attempts,1)
  self.campaign.refresh_from_db();self.assertEqual(self.campaign.repeat_days,0);self.assertIsNone(self.campaign.next_search_at)


from django.test import TransactionTestCase
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

class PilotMigrationTests(TransactionTestCase):
 def test_additive_migration_preserves_historical_records(self):
  before=[('prospection','0011_preserve_legacy_drafts')]
  after=[('prospection','0012_searchjob_parent_search_searchjob_pilot_deadline_and_more')]
  executor=MigrationExecutor(connection);executor.migrate(before)
  try:
   old=executor.loader.project_state(before).apps
   campaign=old.get_model('prospection','Campaign').objects.create(secteur='restaurant',ville='Testville')
   prospect=old.get_model('prospection','Prospect').objects.create(campaign_id=campaign.pk,nom='Entreprise historique fictive',ville='Testville')
   review=old.get_model('prospection','QualificationReview').objects.create(prospect_id=prospect.pk,evidence=[{'origin':'human','detail':'Preuve fictive conservée'}])
   draft=old.get_model('prospection','EmailDraft').objects.create(prospect_id=prospect.pk,subject='Ancien objet',body='Texte fictif historique',revision=1,origin='legacy')
   version=old.get_model('prospection','EmailDraftVersion').objects.create(draft_id=draft.pk,number=1,subject=draft.subject,body=draft.body,fingerprint='fictive',origin='legacy')
   job=old.get_model('prospection','SearchJob').objects.create(campaign_id=campaign.pk,payload={'ids':[prospect.pk],'events':[{'outcome':'insufficient_evidence'}]},status='done')
   names=['Campaign','Prospect','QualificationReview','EmailDraft','EmailDraftVersion','SearchJob']
   snapshots={name:list(old.get_model('prospection',name).objects.values()) for name in names}
   executor=MigrationExecutor(connection);executor.migrate(after)
   current=executor.loader.project_state(after).apps
   for name,rows in snapshots.items():
    fields=list(rows[0])
    self.assertEqual(list(current.get_model('prospection',name).objects.values(*fields)),rows)
   updated=current.get_model('prospection','SearchJob').objects.get(pk=job.pk)
   self.assertIsNone(updated.parent_search_id);self.assertIsNone(updated.pilot_deadline)
   self.assertEqual(updated.pilot_tavily_attempts,0);self.assertIsNone(updated.stopped_at)
  finally:
   MigrationExecutor(connection).migrate(after)
