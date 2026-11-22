import json
from datetime import timedelta
from urllib.parse import urlsplit
from unittest.mock import patch

import requests
from django.test import TestCase, override_settings
from django.utils import timezone

from .identity import capture_prospect
from .jobs import enqueue_qualification, recover_jobs, run_next_job
from .models import Campaign, EmailDraft, Prospect, QualificationReview, SearchJob


@override_settings(DISCOVERY_ENABLED=True, DISCOVERY_PROVIDER="tavily", TAVILY_API_KEY="fictional",
                   HTTP_DOMAIN_INTERVAL=0, HTTP_SOURCE_INTERVAL=0, HTTP_DOMAIN_BUDGET=200,
                   HTTP_SOURCE_BUDGET=200, WEBSITE_EMAIL_MAX_LOOKUPS=100,
                   DISCOVERY_MAX_CANDIDATES=4, DISCOVERY_EXTRA_PAGES=2)
class DiscoveryTests(TestCase):
    def setUp(self):
        self.campaign = Campaign.objects.create(secteur="restaurant",ville="Testville",rayon_km=1)
        self.prospect = Prospect.objects.create(campaign=self.campaign,nom="Café des Pins",ville="Testville")
        self.pages = {}
        self.calls = []
        self.search_html = '<div id="results"><p class="no-results">Aucun résultat</p></div>'
        self.dns = patch("prospection.services.socket.getaddrinfo", return_value=[(2,1,6,"",("8.8.8.8",443))])
        self.wire = patch("prospection.consultations.requests.request", side_effect=self.respond)
        self.dns.start();self.wire.start()
        self.addCleanup(self.dns.stop);self.addCleanup(self.wire.stop)

    def respond(self, method, url, **kwargs):
        self.calls.append(url)
        if urlsplit(url).path == "/robots.txt":
            text=self.pages.get(url,"User-agent: *\nAllow: /")
        elif url == "https://api.tavily.com/search":
            from bs4 import BeautifulSoup
            urls=[a["href"] for a in BeautifulSoup(self.search_html,"html.parser").select("a[href]")]
            text=json.dumps(getattr(self,"search_payload",{"results":[{"url":u} for u in urls]}))
        else:
            text=self.pages.get(url, (404,"Introuvable"))
        if isinstance(text, BaseException):raise text
        code,body,headers=(200,text,{}) if isinstance(text,str) else (*text,{}) if len(text)==2 else text
        r=requests.Response();r.status_code=code;r.url=url;r._content=body.encode()
        r.encoding="utf-8";r.headers.update(headers)
        return r

    def search(self,*urls):
        self.search_html='<div id="results">'+''.join(
            f'<div class="snippet"><a href="{u}">Résultat</a></div>' for u in urls)+'</div>'

    def page(self,name="Café des Pins",city="Testville",extra="",email="contact@cafedespins.example"):
        return f'<html><main><h1>{name}</h1><p>Restaurant à {city}</p>{extra}<a href="mailto:{email}">Contact</a></main></html>'

    def run_discovery(self):
        job=enqueue_qualification(self.prospect,discover=True)
        run_next_job()
        job.refresh_from_db();self.prospect.refresh_from_db()
        return job

    def test_official_site_identity_and_contact_are_discovered(self):
        self.search("https://cafedespins.example/")
        self.pages["https://cafedespins.example/"]=self.page()
        job=self.run_discovery()
        self.assertEqual(job.status,"done")
        self.assertEqual(self.prospect.website,"https://cafedespins.example/")
        self.assertEqual(self.prospect.email,"contact@cafedespins.example")
        q=QualificationReview.objects.get(prospect=self.prospect)
        self.assertTrue(any(e["kind"]=="official_site" for e in q.evidence))
        self.assertTrue(all(e["origin"]=="automatic" and e["observed_at"] and e["company"]["id"]==self.prospect.pk for e in q.evidence))
        self.assertEqual(job.payload["discovery"]["contact_state"],"corroborated")

    def test_homonym_in_other_city_is_not_assigned(self):
        self.search("https://cafedespins.example/")
        self.pages["https://cafedespins.example/"]=self.page(city="Autreville")
        job=self.run_discovery()
        self.assertFalse(self.prospect.website)
        self.assertFalse(self.prospect.email)
        self.assertEqual(job.payload["outcome"],"insufficient_evidence")

    def test_accents_legal_suffix_and_punctuation_variants(self):
        self.search("https://cafedespins.example/")
        self.pages["https://cafedespins.example/"]=self.page(name="CAFE DES PINS SARL")
        self.run_discovery()
        self.assertEqual(self.prospect.website,"https://cafedespins.example/")

    def test_empty_completed_search_never_claims_no_site_exists(self):
        job=self.run_discovery()
        q=QualificationReview.objects.get(prospect=self.prospect)
        self.assertEqual(job.payload["outcome"],"insufficient_evidence")
        self.assertEqual(q.status,"unverified")
        self.assertFalse(self.prospect.website)
        self.assertTrue(any(e["kind"]=="public_search_no_official_site" for e in q.evidence))
        self.assertEqual(EmailDraft.objects.count(),0)

    def test_directory_menu_documents_automatic_opportunity(self):
        from .qualification import opportunity
        url="https://annuaire-restos.fr/fiche/cafe-pins/"
        self.search(url)
        self.pages[url]=self.page(extra="<h2>Carte du midi</h2><p>Plat du jour, soupe.</p>")
        job=self.run_discovery()
        q=QualificationReview.objects.get(prospect=self.prospect)
        self.assertFalse(self.prospect.website)
        self.assertEqual(opportunity(q),"creation")
        self.assertTrue(any(e["kind"]=="third_party_menu" for e in q.evidence))
        self.assertEqual(job.payload["outcome"],"verified")
        self.assertEqual(q.status,"pending")  # Human approval is still necessary.
        draft=EmailDraft.objects.get(prospect=q.prospect)
        self.assertEqual(draft.origin,"conditional")
        self.assertIn("https://nathaniel-dev.fr/",draft.body)
        self.assertEqual(job.payload["draft_preparation"]["created"],1)
        self.assertIsNone(draft.approved_revision)

    def test_directory_contact_without_business_observation_is_insufficient(self):
        url="https://annuaire-restos.fr/fiche/cafe-pins/"
        self.search(url);self.pages[url]=self.page()
        job=self.run_discovery()
        self.assertEqual(job.payload["outcome"],"insufficient_evidence")
        self.assertEqual(QualificationReview.objects.get(prospect=self.prospect).status,"unverified")

    def test_conflicting_email_keeps_existing_contact_uncertain(self):
        self.prospect.email="prior@contact.example";self.prospect.save()
        self.search("https://cafedespins.example/")
        self.pages["https://cafedespins.example/"]=self.page()
        job=self.run_discovery()
        self.assertEqual(self.prospect.email,"prior@contact.example")
        self.assertEqual(job.payload["discovery"]["contact_state"],"uncertain")
        self.assertEqual(job.payload["outcome"],"insufficient_evidence")

    def test_429_wait_is_persistent_and_does_not_duplicate_observations(self):
        self.search("https://cafedespins.example/")
        self.pages["https://cafedespins.example/"]=(429,"",{"Retry-After":"120"})
        job=self.run_discovery()
        self.assertEqual(job.status,"queued")
        before=list(self.calls);recover_jobs();self.assertFalse(run_next_job());self.assertEqual(self.calls,before)
        self.pages["https://cafedespins.example/"]=self.page()
        from .models import ServiceCache
        ServiceCache.objects.filter(expires_at__isnull=False).update(expires_at=timezone.now()-timedelta(seconds=1))
        SearchJob.objects.filter(pk=job.pk).update(next_run_at=timezone.now())
        run_next_job();job.refresh_from_db()
        q=QualificationReview.objects.get(prospect=self.prospect)
        keys=[e["id"] for e in q.evidence]
        self.assertEqual(len(keys),len(set(keys)))
        self.assertEqual(job.status,"done")

    def test_robots_refusal_is_explicit_and_page_is_not_fetched(self):
        self.search("https://cafedespins.example/")
        self.pages["https://cafedespins.example/robots.txt"]="User-agent: *\nDisallow: /"
        job=self.run_discovery()
        self.assertEqual(job.status,"error")
        self.assertNotIn("https://cafedespins.example/",self.calls)

    def test_403_and_503_are_not_empty_search_results(self):
        for code,status in [(403,"error"),(503,"queued")]:
            with self.subTest(code=code):
                from .models import ServiceCache
                ServiceCache.objects.all().delete()
                self.prospect.jobs.all().delete()
                self.search("https://cafedespins.example/")
                self.pages["https://cafedespins.example/"]=(code,"")
                job=self.run_discovery()
                self.assertEqual(job.status,status)
                self.assertFalse(QualificationReview.objects.filter(prospect=self.prospect).exists())

    def test_public_redirect_is_verified_before_assignment(self):
        self.search("https://old.example/")
        self.pages["https://old.example/"]=(301,"",{"Location":"https://cafedespins.example/"})
        self.pages["https://cafedespins.example/"]=self.page()
        self.run_discovery()
        self.assertEqual(self.prospect.website,"https://cafedespins.example/")

    def test_opposition_survives_deletion_and_recreation(self):
        self.prospect.email="contact@cafedespins.example"
        self.prospect.status="do_not_contact";self.prospect.save()
        self.prospect.delete()
        new=capture_prospect(self.campaign,{"type":"node","id":989,"tags":{
            "name":"Nouveau nom","addr:city":"Autreville","email":"contact@cafedespins.example"}})
        self.assertEqual(new.status,"do_not_contact")

    def test_business_opposition_on_identified_page_is_durable(self):
        self.search("https://cafedespins.example/")
        self.pages["https://cafedespins.example/"]=self.page(extra="<p>Nous refusons toute prospection commerciale.</p>")
        job=self.run_discovery()
        self.assertEqual(job.payload["outcome"],"excluded")
        self.assertEqual(self.prospect.status,"do_not_contact")
        self.assertEqual(EmailDraft.objects.count(),0)

    def test_interrupt_after_response_then_restart_avoids_second_consultation(self):
        self.search("https://cafedespins.example/")
        self.pages["https://cafedespins.example/"]=self.page()
        from . import discovery
        original=discovery._analyse_page
        def interrupt(*args,**kwargs):raise KeyboardInterrupt()
        with patch("prospection.discovery._analyse_page",side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):self.run_discovery()
        self.assertEqual(self.calls.count("https://cafedespins.example/"),1)
        recover_jobs();run_next_job()
        self.assertEqual(self.calls.count("https://cafedespins.example/"),1)
        self.assertEqual(QualificationReview.objects.filter(prospect=self.prospect).count(),1)

    def test_existing_approved_review_and_draft_are_preserved(self):
        q=QualificationReview.objects.create(prospect=self.prospect,status="approved",evidence=[{"kind":"old"}])
        d=EmailDraft.objects.create(prospect=self.prospect,subject="Relu",body="Texte historique")
        job=SearchJob.objects.create(prospect=self.prospect,kind="qualification",payload={"discover":True})
        run_next_job()
        q.refresh_from_db();d.refresh_from_db()
        self.assertEqual(q.evidence,[{"kind":"old"}]);self.assertEqual(d.body,"Texte historique")
        self.assertEqual(self.calls,[])

    def test_campaign_to_documented_opportunity_is_fully_automatic_on_fixture(self):
        import json
        from django.conf import settings
        from rest_framework.test import APIClient
        from .models import EmailLog
        self.prospect.delete()
        self.pages["https://nominatim.openstreetmap.org/search"]=json.dumps([{"lat":"48","lon":"-1"}])
        self.pages[settings.OVERPASS_ENDPOINTS[0]]=json.dumps({"elements":[{
            "type":"node","id":321,"tags":{"name":"Café des Pins","addr:city":"Testville"}}]})
        url="https://annuaire-restos.fr/fiche/cafe-pins/"
        self.search(url)
        self.pages[url]=self.page(extra="<h2>Carte du midi</h2><p>Plat de saison.</p>")
        with override_settings(DESKTOP_AUTO_AUTH=False,OWNER_ACCESS_TOKEN="",REQUIRE_OWNER_TOKEN=False):
            response=APIClient().post(f"/api/personal/campaigns/{self.campaign.pk}/launch/")
        self.assertEqual(response.status_code,202)
        self.assertTrue(run_next_job())  # OSM search and persistent discovery enqueue.
        self.assertTrue(run_next_job())  # Automatic discovery, identity and public proofs.
        p=Prospect.objects.get()
        review=QualificationReview.objects.get(prospect=p)
        job=SearchJob.objects.get(kind="qualification")
        self.assertEqual(job.payload["outcome"],"verified")
        self.assertEqual(review.status,"pending")
        self.assertEqual(EmailLog.objects.count(),0)
        self.assertTrue(all(e["origin"]=="automatic" for e in review.evidence))
        print("DEMO LOT2",json.dumps({"company":p.nom,"contact":job.payload["discovery"]["contact_state"],
              "result":job.payload["outcome"],"validation":review.status,
              "evidence_kinds":[e["kind"] for e in review.evidence]},ensure_ascii=True))

    def test_explicit_recheck_keeps_old_evidence_and_draft(self):
        from rest_framework.test import APIClient
        old=QualificationReview.objects.create(prospect=self.prospect,status="pending",evidence=[{"kind":"old","detail":"Historique"}])
        draft=EmailDraft.objects.create(prospect=self.prospect,subject="Relu",body="Texte à conserver")
        self.search("https://cafedespins.example/")
        self.pages["https://cafedespins.example/"]=self.page()
        with override_settings(DESKTOP_AUTO_AUTH=False,OWNER_ACCESS_TOKEN="",REQUIRE_OWNER_TOKEN=False):
            response=APIClient().post(f"/api/personal/qualification/{old.pk}/evidence/",{"discover":True},format="json")
        self.assertEqual(response.status_code,202)
        run_next_job();old.refresh_from_db();draft.refresh_from_db()
        self.assertTrue(any(e["kind"]=="old" and e["historical"] for e in old.evidence))
        self.assertEqual(draft.body,"Texte à conserver")

    def test_two_matching_domains_are_ambiguous(self):
        self.search("https://cafedespins.example/","https://cafedespins-testville.example/")
        for u in ["https://cafedespins.example/","https://cafedespins-testville.example/"]:self.pages[u]=self.page()
        job=self.run_discovery()
        self.assertFalse(self.prospect.website)
        self.assertEqual(job.payload["discovery"]["contact_state"],"uncertain")
        self.assertEqual(job.payload["outcome"],"insufficient_evidence")

    def test_contact_page_inherits_confirmed_same_domain_identity(self):
        self.search("https://cafedespins.example/")
        self.pages["https://cafedespins.example/"]=self.page(email="").replace(
            '<a href="mailto:">Contact</a>','<a href="/contact">Contact</a>')
        self.pages["https://cafedespins.example/contact"]='<html><main><h1>Contact</h1><a href="mailto:bonjour@cafedespins.example">Nous écrire</a></main></html>'
        job=self.run_discovery()
        self.assertEqual(self.prospect.email,"bonjour@cafedespins.example")
        self.assertEqual(job.payload["discovery"]["contact_state"],"corroborated")

    def test_missing_activity_is_not_an_official_site_match(self):
        self.search("https://cafedespins.example/")
        self.pages["https://cafedespins.example/"]=self.page().replace("Restaurant","Association")
        job=self.run_discovery()
        self.assertFalse(self.prospect.website)
        self.assertEqual(job.payload["outcome"],"insufficient_evidence")

    def test_unrecognized_search_payload_blocks_without_claiming_empty_results(self):
        self.search_payload={"unexpected": "Malformed provider payload"}
        job=self.run_discovery()
        self.assertEqual(job.status,"error")
        self.assertNotIn("public_search_no_official_site",[e["kind"] for e in job.payload["discovery"]["evidence"]])
        self.assertFalse(QualificationReview.objects.filter(prospect=self.prospect).exists())

    def test_private_redirect_is_never_fetched(self):
        self.search("https://cafedespins.example/")
        self.pages["https://cafedespins.example/"]=(302,"",{"Location":"http://127.0.0.1/private"})
        def dns(host,*args):
            return [(2,1,6,"",("127.0.0.1" if host=="127.0.0.1" else "8.8.8.8",443))]
        with patch("prospection.services.socket.getaddrinfo",side_effect=dns):
            job=self.run_discovery()
        self.assertEqual(job.status,"error")
        self.assertFalse(any("127.0.0.1" in u for u in self.calls))

    def test_robots_crawl_delay_is_respected(self):
        self.search("https://cafedespins.example/")
        self.pages["https://cafedespins.example/robots.txt"]="User-agent: *\nAllow: /\nCrawl-delay: 10"
        self.pages["https://cafedespins.example/"]=self.page(extra='<a href="/contact">Contact</a>')
        job=self.run_discovery()
        self.assertEqual(job.status,"queued")
        self.assertGreater(job.next_run_at,timezone.now()+timedelta(seconds=8))
        self.assertNotIn("https://cafedespins.example/contact",self.calls)

    def test_automatic_opposition_retains_email_scope_and_origin(self):
        from .cache import cache_key
        from .models import ServiceCache
        self.search("https://cafedespins.example/")
        self.pages["https://cafedespins.example/"]=self.page(extra="<p>Nous refusons toute prospection commerciale.</p>")
        self.run_discovery()
        marker=ServiceCache.objects.get(key=cache_key("commercial-opposition:email:contact@cafedespins.example"))
        self.assertEqual(marker.value["origin"],"automatic")
        self.assertEqual(marker.value["source"],"https://cafedespins.example/")
        self.prospect.delete()
        new=capture_prospect(self.campaign,{"type":"node","id":765,"tags":{
            "name":"Nouvelle enseigne","addr:city":"Autreville","email":"contact@cafedespins.example"}})
        self.assertEqual(new.status,"do_not_contact")

    def test_local_edit_during_discovery_is_not_overwritten(self):
        self.search("https://cafedespins.example/")
        self.pages["https://cafedespins.example/"]=self.page()
        from . import discovery
        analyse=discovery._analyse_page
        def user_edit(*args,**kwargs):
            extra=analyse(*args,**kwargs)
            Prospect.objects.filter(pk=self.prospect.pk).update(email="edited@contact.example")
            return extra
        with patch("prospection.discovery._analyse_page",side_effect=user_edit):
            job=self.run_discovery()
        self.assertEqual(job.status,"error")
        self.assertEqual(self.prospect.email,"edited@contact.example")
        self.assertFalse(QualificationReview.objects.filter(prospect=self.prospect).exists())

    def test_brand_in_subdomain_is_not_sufficient_domain_evidence(self):
        url="https://cafedespins.unrelated.example/"
        self.search(url);self.pages[url]=self.page()
        job=self.run_discovery()
        self.assertFalse(self.prospect.website)
        self.assertEqual(job.payload["outcome"],"insufficient_evidence")

    def test_unavailable_linked_official_site_blocks_creation_claim(self):
        from .qualification import opportunity
        url="https://annuaire-restos.fr/fiche/cafe-pins/"
        self.search(url)
        self.pages[url]=self.page(extra='<h2>Carte du midi</h2><a href="https://official.example/">Site officiel</a>')
        self.pages["https://official.example/"]=(404,"Introuvable")
        job=self.run_discovery()
        q=QualificationReview.objects.get(prospect=self.prospect)
        self.assertIsNone(opportunity(q))
        self.assertEqual(job.payload["outcome"],"insufficient_evidence")

    def test_candidate_count_is_bounded(self):
        urls=[f"https://candidate-{i}.example/" for i in range(12)]
        self.search(*urls)
        for u in urls:self.pages[u]=self.page(city="Autreville")
        self.run_discovery()
        inspected=[u for u in self.calls if urlsplit(u).hostname.startswith("candidate") and urlsplit(u).path!="/robots.txt"]
        self.assertEqual(len(inspected),4)

    def test_name_variant_does_not_bypass_opposition_without_an_email(self):
        self.prospect.status="do_not_contact";self.prospect.save()
        new=capture_prospect(self.campaign,{"type":"node","id":987,"tags":{
            "name":"CAFE DES PINS SARL","addr:city":"Testville","addr:street":"Nouvelle adresse"}})
        self.assertEqual(new.status,"do_not_contact")

    def test_human_decision_during_network_is_preserved(self):
        self.search("https://cafedespins.example/")
        self.pages["https://cafedespins.example/"]=self.page()
        from . import discovery
        analyse=discovery._analyse_page
        def decide(*args,**kwargs):
            result=analyse(*args,**kwargs)
            QualificationReview.objects.create(prospect=self.prospect,status="rejected",evidence=[{"kind":"human_decision"}])
            return result
        with patch("prospection.discovery._analyse_page",side_effect=decide):
            self.run_discovery()
        q=QualificationReview.objects.get(prospect=self.prospect)
        self.assertEqual(q.status,"rejected")
        self.assertEqual(q.evidence,[{"kind":"human_decision"}])
        self.assertFalse(self.prospect.website)
        self.assertFalse(self.prospect.email)

    def test_manual_assisted_proof_keeps_its_origin(self):
        from .qualification import record_creation_search
        self.prospect.email="contact@cafedespins.example";self.prospect.save()
        q=record_creation_search(self.prospect,search_url="https://search.example/",
            contact_url="https://directory.example/",method="Contrôle assisté",
            limits="Délivrabilité non testée.",origin="assisted")
        self.assertTrue(all(e["origin"]=="assisted" for e in q.evidence))

    @override_settings(HTTP_DOMAIN_INTERVAL=1,HTTP_SOURCE_INTERVAL=1)
    def test_redirect_with_rate_limits_makes_progress_after_restart(self):
        self.search("https://old.example/")
        self.pages["https://old.example/"]=(301,"",{"Location":"https://cafedespins.example/"})
        self.pages["https://cafedespins.example/"]=self.page()
        clock=timezone.now()
        job=enqueue_qualification(self.prospect,discover=True)
        for step in range(12):
            clock+=timedelta(seconds=2)
            with patch("django.utils.timezone.now",return_value=clock):
                SearchJob.objects.filter(pk=job.pk).update(next_run_at=clock)
                run_next_job()
                job.refresh_from_db()
            if job.status=="done":break
        self.assertEqual(job.status,"done")
        self.assertEqual(self.calls.count("https://old.example/"),1)
        self.prospect.refresh_from_db()
        self.assertEqual(self.prospect.website,"https://cafedespins.example/")

    def test_practical_information_on_two_sources_is_documented(self):
        from .qualification import opportunity
        urls=["https://annuaire-restos.fr/fiche/cafe-pins/","https://fr.restaurantguru.com/cafe-pins/"]
        self.search(*urls)
        for u in urls:self.pages[u]=self.page(extra="<h2>Horaires</h2><p>Ouvert le midi.</p>")
        job=self.run_discovery()
        q=QualificationReview.objects.get(prospect=self.prospect)
        self.assertEqual(opportunity(q),"creation")
        self.assertTrue(any(e["kind"]=="dispersed_information" for e in q.evidence))
        self.assertEqual(job.payload["outcome"],"verified")

    def test_contact_is_explicitly_not_found_when_no_address_is_published(self):
        self.search("https://cafedespins.example/")
        self.pages["https://cafedespins.example/"]=self.page(email="")
        job=self.run_discovery()
        self.assertFalse(self.prospect.email)
        self.assertEqual(job.payload["discovery"]["contact_state"],"not_found")
        self.assertEqual(job.payload["outcome"],"insufficient_evidence")

    def test_opposition_on_directory_does_not_exclude_its_other_listings(self):
        from .opposition import is_opposed
        self.prospect.status="do_not_contact"
        self.prospect.website="https://es.restaurantguru.com/cafe-pins/"
        self.prospect.save()
        self.assertFalse(is_opposed("Autre entreprise","Autreville",None,"https://es.restaurantguru.com/other/"))
