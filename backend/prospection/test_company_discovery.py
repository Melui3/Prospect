import copy
import json
from datetime import timedelta
from unittest.mock import patch
import requests
from django.test import TestCase,override_settings
from django.utils import timezone
from .models import Campaign,SearchJob,Prospect,EmailDraft,EmailLog,QualificationReview,ServiceCache
from .jobs import enqueue_search,run_next_job,recover_jobs
from .consultations import ConsultationError,job_consultations

URL='https://recherche-entreprises.api.gouv.fr/near_point'
def establishment(siret='00000000100001',**values):
 return dict({'siret':siret,'nom_commercial':'Café des Pins','liste_enseignes':[],
  'libelle_commune':'Testville','adresse':'1 RUE FICTIVE 35000 TESTVILLE','code_postal':'35000',
  'latitude':'48','longitude':'-1','activite_principale':'56.10A',
  'etat_administratif':'A','statut_diffusion_etablissement':'O'},**values)
def legal(matches=None,**values):
 return dict({'siren':'000000001','nom_complet':'Société fictive',
  'etat_administratif':'A','statut_diffusion':'O','opposition_diffusion_commerciale':False,
  'matching_etablissements':[establishment()] if matches is None else matches,
  'siege':{'siret':'00000000199999','libelle_commune':'Autreville','latitude':'45','longitude':'2'}},**values)
def payload(rows=None,page=1,pages=1):
 return {'results':[legal()] if rows is None else rows,'page':page,'per_page':25,
 'total_pages':pages,'total_results':max(0,pages*25) if pages>1 else len(rows if rows is not None else [1])}
def response(data=None,code=200,headers=None):
 r=requests.Response();r.status_code=code;r.url=URL;r._content=json.dumps(payload() if data is None else data).encode();r.encoding='utf-8';r.headers.update(headers or {});return r

@override_settings(HTTP_SOURCE_INTERVAL=0,HTTP_DOMAIN_INTERVAL=0,HTTP_SOURCE_BUDGET=100,HTTP_DOMAIN_BUDGET=100)
class CompanyDiscoveryTests(TestCase):
 def setUp(self):
  self.campaign=Campaign.objects.create(secteur='restaurant',ville='Testville',rayon_km=1)
  self.job=SearchJob.objects.create(campaign=self.campaign,status='running')
 def discover(self):
  from .company_discovery import discover_companies
  with job_consultations(self.job),patch('prospection.services._get_city_coords',return_value=('48','-1')):
   return discover_companies(self.job)
 def test_contract_uses_local_matching_establishment_not_remote_headquarters(self):
  with patch('prospection.consultations.requests.request',return_value=response()) as wire:
   rows=self.discover()
  self.assertEqual(len(rows),1);self.assertEqual(rows[0]['type'],'siret');self.assertEqual(rows[0]['id'],'00000000100001')
  self.assertEqual(rows[0]['tags']['name'],'Café des Pins');self.assertEqual(rows[0]['tags']['addr:city'],'Testville')
  args=wire.call_args;self.assertEqual(args.args[:2],('GET',URL))
  params=args.kwargs['params'];self.assertEqual(params['radius'],1)
  self.assertEqual(params['activite_principale'],'56.10A,56.10B,56.10C')
  self.assertEqual(params['include'],'matching_etablissements');self.assertTrue(params['minimal'])
  self.assertIn('Prospect',args.kwargs['headers']['User-Agent'])
  self.assertNotIn('email',rows[0]['tags']);self.assertNotIn('website',rows[0]['tags'])
 def test_outside_radius_closed_wrong_activity_and_unknown_coordinates_are_rejected(self):
  entries=[establishment('00000000100002',latitude='49'),establishment('00000000100003',etat_administratif='F'),
   establishment('00000000100004',activite_principale='96.02A'),establishment('00000000100005',latitude=None)]
  with patch('prospection.consultations.requests.request',return_value=response(payload([legal(entries)]))):
   self.assertEqual(self.discover(),[])
  self.assertTrue(self.job.payload['company_discovery']['rejections'])
 def test_opposition_and_partial_diffusion_never_feed_the_pipeline(self):
  for values in [{'opposition_diffusion_commerciale':True},{'opposition_diffusion_commerciale':None},
                 {'statut_diffusion':'P'},{'etat_administratif':'C'}]:
   with self.subTest(values=values):
    ServiceCache.objects.all().delete();self.job.payload={};self.job.save(update_fields=['payload'])
    with patch('prospection.consultations.requests.request',return_value=response(payload([legal(**values)]))):
     self.assertEqual(self.discover(),[])
 def test_explicit_opposition_is_preserved_by_existing_suppression_mechanism(self):
  from .opposition import is_opposed
  with patch('prospection.consultations.requests.request',return_value=response(payload([legal(opposition_diffusion_commerciale=True)]))):self.discover()
  self.assertTrue(is_opposed('Café des Pins','Testville'))
 def test_duplicate_siret_does_not_produce_duplicate_captures(self):
  with patch('prospection.consultations.requests.request',return_value=response(payload([legal([establishment(),establishment()])]))):
   rows=self.discover()
  self.assertEqual(len(rows),1)
 def test_invalid_payload_is_temporary_and_never_cached_as_an_empty_success(self):
  for invalid in [{},{'results':None},payload([{'matching_etablissements':'wrong'}])]:
   ServiceCache.objects.all().delete();self.job.payload={};self.job.save(update_fields=['payload'])
   with patch('prospection.consultations.requests.request',return_value=response(invalid)):
    with self.assertRaises(ConsultationError) as caught:self.discover()
   self.assertTrue(caught.exception.temporary)
   self.assertFalse(ServiceCache.objects.filter(value__has_key='body').exists())
 def test_empty_response_is_a_documented_scope_result(self):
  with patch('prospection.consultations.requests.request',return_value=response(payload([]))):self.assertEqual(self.discover(),[])
  self.assertEqual(self.job.payload['company_discovery']['returned_units'],0)
 def test_unknown_sector_fails_before_any_http(self):
  self.campaign.secteur='secteur inconnu';self.campaign.save()
  with patch('prospection.consultations.requests.request') as wire:
   with self.assertRaises(ValueError):self.discover()
   wire.assert_not_called()
 def test_429_403_5xx_and_network_use_existing_error_contract(self):
  for code in [429,403,503]:
   ServiceCache.objects.all().delete();self.job.payload={};self.job.save(update_fields=['payload'])
   with patch('prospection.consultations.requests.request',return_value=response(code=code,headers={'Retry-After':'120'})):
    with self.assertRaises(ConsultationError) as caught:self.discover()
   self.assertEqual(caught.exception.http_status,code)
   if code!=403:self.assertGreater(caught.exception.retry_at,timezone.now()+timedelta(seconds=110))
  ServiceCache.objects.all().delete();self.job.payload={};self.job.save(update_fields=['payload'])
  with patch('prospection.consultations.requests.request',side_effect=requests.ConnectionError()):
   with self.assertRaises(ConsultationError):self.discover()
 def test_pages_resume_from_checkpoint_without_repeating_first_http(self):
  one=payload([legal()],page=1,pages=2);one.update(per_page=1,total_results=2)
  two=payload([legal(opposition_diffusion_commerciale=None)],page=2,pages=2);two.update(per_page=1,total_results=2)
  first=response(one);second=response(two)
  clock=[timezone.now()]
  def tick():
   clock[0]+=timedelta(seconds=2);return clock[0]
  with patch('django.utils.timezone.now',side_effect=tick),patch('prospection.consultations.requests.request',side_effect=[first,requests.ConnectionError(),second]) as wire:
   with self.assertRaises(ConsultationError):self.discover()
   self.job.refresh_from_db();rows=self.discover()
  self.assertEqual(len(rows),1);self.assertEqual([c.kwargs['params']['page'] for c in wire.call_args_list],[1,2,2])
 def test_nonnecessary_personal_fields_are_not_persisted_in_http_cache_or_tags(self):
  data=payload([legal()]);data['results'][0]['dirigeants']=[{'date_de_naissance':'SENSITIVE_FICTIVE_MARKER'}]
  with patch('prospection.consultations.requests.request',return_value=response(data)):
   rows=self.discover()
  self.assertNotIn('SENSITIVE_FICTIVE_MARKER',str(list(ServiceCache.objects.values_list('value',flat=True))))
  self.assertNotIn('dirigeants',str(rows));self.assertIn('observed_at',rows[0]['tags']['company_discovery'])
 def test_new_jobs_choose_api_without_overpass_and_keep_siret_provenance(self):
  self.job.delete();job=enqueue_search(self.campaign)
  with patch('prospection.services._get_city_coords',return_value=('48','-1')),patch('prospection.consultations.requests.request',return_value=response()),patch('prospection.services._query_overpass') as old:
   self.assertTrue(run_next_job());old.assert_not_called()
  job.refresh_from_db();p=Prospect.objects.get()
  self.assertEqual(p.external_id,'siret:00000000100001');self.assertIsNone(p.email)
  self.assertEqual(job.payload['company_discovery_provider'],'recherche_entreprises')
  self.assertEqual(SearchJob.objects.get(kind='qualification').parent_search_id,job.pk)
  self.assertFalse(EmailDraft.objects.exists());self.assertFalse(EmailLog.objects.exists())
 def test_existing_osm_identity_keeps_decisions_and_records_siret_for_future_recapture(self):
  from .identity import capture_prospect
  old=capture_prospect(self.campaign,{'type':'node','id':123,'tags':{'name':'Café des Pins','addr:city':'Testville','addr:street':'1 RUE FICTIVE'}})
  review=QualificationReview.objects.create(prospect=old,status='approved',evidence=[{'kind':'historical','detail':'Fictive decision'}])
  draft=EmailDraft.objects.create(prospect=old,subject='Historique fictif',body='Texte conservé')
  with patch('prospection.consultations.requests.request',return_value=response()):rows=self.discover()
  first=capture_prospect(self.campaign,rows[0]);self.assertEqual(first.pk,old.pk)
  renamed=copy.deepcopy(rows[0]);renamed['tags']['name']='Nouvelle enseigne fictive'
  again=capture_prospect(self.campaign,renamed)
  self.assertEqual(again.pk,old.pk);self.assertEqual(Prospect.objects.count(),1)
  old.refresh_from_db();review.refresh_from_db();draft.refresh_from_db()
  self.assertEqual(old.external_id,'node:123');self.assertEqual(old.raw_tags['siret'],'00000000100001')
  self.assertEqual(review.status,'approved');self.assertEqual(draft.body,'Texte conservé')
 def test_pagination_mismatch_is_not_cached(self):
  with patch('prospection.consultations.requests.request',return_value=response(payload(page=2,pages=2))):
   with self.assertRaises(ConsultationError):self.discover()
  self.assertFalse(ServiceCache.objects.filter(value__has_key='body').exists())
 def test_stop_during_response_never_captures_businesses(self):
  from .run_limits import stop_campaign,PilotStopped
  def stop(*args,**kwargs):stop_campaign(self.campaign.pk);return response()
  with patch('prospection.consultations.requests.request',side_effect=stop):
   with self.assertRaises(PilotStopped):self.discover()
  self.assertFalse(Prospect.objects.exists())
 def test_different_sirets_at_the_same_address_never_merge(self):
  from .identity import capture_prospect
  with patch('prospection.consultations.requests.request',return_value=response()):row=self.discover()[0]
  capture_prospect(self.campaign,row)
  other=copy.deepcopy(row);other['id']='00000000100002';other['tags']['siret']=other['id']
  other['tags']['company_discovery']['siret']=other['id']
  with self.assertRaises(ValueError):capture_prospect(self.campaign,other)
  self.assertEqual(Prospect.objects.count(),1)
 def test_empty_results_with_positive_total_are_not_a_success(self):
  inconsistent=payload([]);inconsistent['total_results']=1
  with patch('prospection.consultations.requests.request',return_value=response(inconsistent)):
   with self.assertRaises(ConsultationError):self.discover()
 def test_exactly_five_results_are_not_reported_as_truncated(self):
  self.job.pilot_deadline=timezone.now()+timedelta(minutes=20);self.job.save(update_fields=['pilot_deadline'])
  entries=[establishment(f'000000001{i:05d}',nom_commercial=f'Entreprise fictive {i}') for i in range(5)]
  with patch('prospection.consultations.requests.request',return_value=response(payload([legal(entries)]))):
   self.assertEqual(len(self.discover()),5)
  self.assertFalse(self.job.payload['company_discovery']['scope_truncated'])
 def test_rejected_names_and_error_bodies_are_not_cached(self):
  denied=payload([legal(nom_complet='REJECTED_PRIVATE_MARKER',opposition_diffusion_commerciale=True)])
  with patch('prospection.consultations.requests.request',return_value=response(denied)):self.discover()
  self.assertNotIn('REJECTED_PRIVATE_MARKER',str(list(ServiceCache.objects.values_list('value',flat=True))))
  self.job.payload={};self.job.save(update_fields=['payload']);ServiceCache.objects.all().delete()
  error=response(code=404);error._content=b'ERROR_PRIVATE_MARKER'
  with patch('prospection.consultations.requests.request',return_value=error):
   with self.assertRaises(ConsultationError):self.discover()
  self.assertNotIn('ERROR_PRIVATE_MARKER',str(list(ServiceCache.objects.values_list('value',flat=True))))
 def test_page_limit_is_persistent_and_incomplete_scope_is_explicit(self):
  clock=[timezone.now()]
  def tick():clock[0]+=timedelta(seconds=2);return clock[0]
  def answer(method,url,**kwargs):
   page=kwargs['params']['page']
   rows=[legal([establishment(etat_administratif='F')]) for _ in range(25)]
   return response(payload(rows,page=page,pages=6))
  with patch('django.utils.timezone.now',side_effect=tick),patch('prospection.consultations.requests.request',side_effect=answer) as wire:
   self.assertEqual(self.discover(),[])
   self.job.refresh_from_db();self.assertEqual(self.discover(),[])
  self.assertEqual(wire.call_count,4);self.assertTrue(self.job.payload['company_discovery']['scope_truncated'])
 def test_legacy_started_overpass_job_keeps_its_provider(self):
  self.job.status='queued';self.job.payload={'overpass':{'next_endpoint':1}};self.job.save()
  with patch('prospection.services._get_city_coords',return_value=('48','-1')),patch('prospection.services._query_overpass',return_value=[]) as old,patch('prospection.consultations.requests.request') as wire:
   run_next_job();old.assert_called_once();wire.assert_not_called()

from . import test_c1 as c1_fixtures

@override_settings(DISCOVERY_ENABLED=True,DISCOVERY_PROVIDER='tavily',TAVILY_API_KEY='fictional',
 HTTP_SOURCE_INTERVAL=0,HTTP_DOMAIN_INTERVAL=0,HTTP_SOURCE_BUDGET=100,HTTP_DOMAIN_BUDGET=100,
 REQUIRE_OWNER_TOKEN=False,OWNER_ACCESS_TOKEN='',DESKTOP_AUTO_AUTH=False,DEMO_MODE=False)
class CompanyPipelineTests(TestCase):
 setUp=c1_fixtures.C1PipelineTests.setUp
 search=c1_fixtures.C1PipelineTests.search
 page=c1_fixtures.C1PipelineTests.page
 def respond(self,method,url,**kwargs):
  if url==URL:return response(getattr(self,'registry_payload',None))
  return c1_fixtures.C1PipelineTests.respond(self,method,url,**kwargs)
 def test_registry_to_contact_proof_selection_and_personalized_draft_is_automatic(self):
  from .selection import select_opportunities
  self.prospect.delete()
  url='https://annuaire-restos.fr/fiche/cafe-pins/'
  self.search(url);self.pages[url]=self.page(extra='<h2>Carte du midi</h2>')
  job=enqueue_search(self.campaign)
  with patch('prospection.services._get_city_coords',return_value=('48','-1')),patch('prospection.services._query_overpass') as overpass:
   self.assertTrue(run_next_job());self.assertTrue(run_next_job());self.assertFalse(run_next_job());overpass.assert_not_called()
  job.refresh_from_db();prospect=Prospect.objects.get();review=QualificationReview.objects.get();draft=EmailDraft.objects.get()
  self.assertEqual(prospect.external_id,'siret:00000000100001')
  self.assertEqual(prospect.enrichment_status,'found');self.assertEqual(review.status,'pending')
  self.assertIn('corroborated_contact',{e['kind'] for e in review.evidence})
  self.assertEqual(len(select_opportunities([review])[0]),1)
  self.assertEqual(draft.origin,'conditional');self.assertIn('Carte du midi',draft.body)
  self.assertIn('NateOS',draft.body);self.assertIn('https://nathaniel-dev.fr/',draft.body)
  self.assertIsNone(draft.approved_revision);self.assertFalse(EmailLog.objects.exists())
  print('DEMO REGISTRY',json.dumps({'identified':1,'corroborated_contacts':1,'selected':1,'drafts':1,'approved':0,'sent':0,'manual_per_record':0}))
 def test_pilot_maximum_five_applies_before_capture_on_large_registry_response(self):
  from .run_limits import schedule_pilot
  self.prospect.delete()
  self.registry_payload=payload([legal([establishment(f'000000001{i:05d}',nom_commercial=f'Entreprise fictive {i}') for i in range(8)])])
  job=schedule_pilot(self.campaign,timezone.now()+timedelta(minutes=1))
  SearchJob.objects.filter(pk=job.pk).update(next_run_at=timezone.now()-timedelta(seconds=1))
  with patch('prospection.services._get_city_coords',return_value=('48','-1')):run_next_job()
  job.refresh_from_db();self.assertEqual(Prospect.objects.count(),5)
  self.assertEqual(SearchJob.objects.filter(parent_search=job).count(),5)
  self.assertTrue(job.payload['company_discovery']['scope_truncated'])
  self.assertEqual(job.payload['pilot_omitted_count'],3)
  self.assertEqual(job.pilot_tavily_attempts,0)
