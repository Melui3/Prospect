from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from .models import Campaign, EmailDraft, EmailLog, Prospect, QualificationReview
from .qualification import _identity


@override_settings(DESKTOP_AUTO_AUTH=False, OWNER_ACCESS_TOKEN="", REQUIRE_OWNER_TOKEN=False)
class CommercialSelectionTests(TestCase):
    def setUp(self):
        self.campaign = Campaign.objects.create(secteur="restaurant",ville="Testville")
        self.client = APIClient()
        self.number = 0

    def candidate(self, kind="third_party_menu", age=1, status="pending", email=None, **fields):
        self.number += 1
        p = Prospect.objects.create(campaign=self.campaign, nom=f"Entreprise {self.number}", ville="Testville",
                                    email=email or f"contact{self.number}@business.example", **fields)
        date = (timezone.now()-timedelta(days=age)).isoformat()
        def evidence(k,url,**values):
            return {"kind":k,"url":url,"source":"Source fictive","observed_at":date,
                    "origin":"automatic","detail":"Observation vérifiable sur la page.",
                    "method":"Lecture et recoupement de la fiche.","limits":"Délivrabilité non testée.",
                    "company":{"id":p.pk,"name":p.nom,"city":p.ville},**values}
        rows = [evidence("corroborated_contact","https://directory.example/contact",
                         email=p.email,identity=_identity(p))]
        if kind == "missing_viewport":
            p.website = f"https://business-{p.pk}.example/";p.save()
            rows.append(evidence(kind,p.website,input_website=p.website))
        else:
            rows += [evidence("public_search_no_official_site","https://search.example/results"),
                     evidence(kind,"https://directory.example/company")]
        return QualificationReview.objects.create(prospect=p,status=status,evidence=rows)

    def selection(self):
        response = self.client.get("/api/personal/qualification/",{"status":"selection"})
        self.assertEqual(response.status_code,200)
        return response.data

    def test_at_most_five_without_padding(self):
        for _ in range(8):self.candidate()
        result=self.selection()
        self.assertEqual(len(result["results"]),5)
        self.assertEqual(result["selection"]["unique_count"],8)
        self.assertEqual(result["selection"]["held_by_limit"],3)
        QualificationReview.objects.all().delete()
        self.candidate()
        self.assertEqual(self.selection()["count"],1)

    def test_no_evidence_means_empty_selection(self):
        p=Prospect.objects.create(nom="Sans preuve",ville="Testville",email="x@business.example")
        QualificationReview.objects.create(prospect=p,status="pending")
        self.assertEqual(self.selection()["count"],0)

    def test_explained_order_matches_services_and_real_dates(self):
        technical=self.candidate("missing_viewport",age=0)
        dispersed=self.candidate("dispersed_information",age=1)
        menu=self.candidate(age=2)
        result=self.selection()
        self.assertEqual([r["id"] for r in result["results"]],[menu.pk,dispersed.pk,technical.pk])
        first=result["results"][0]["selection"]
        self.assertEqual(first["rank"],1)
        self.assertEqual(first["service"]["id"],"landing-page")
        self.assertEqual(first["service"]["url"],"https://nathaniel-dev.fr/services/")
        self.assertTrue(first["reasons"])
        self.assertTrue(first["evidence"])
        self.assertEqual(result["results"][2]["selection"]["service"]["id"],"site-vitrine")

    def test_stale_future_undated_and_uncertain_contacts_are_excluded(self):
        self.candidate(age=40)
        self.candidate(age=-1)
        undated=self.candidate();undated.evidence[0]["observed_at"]="";undated.save()
        wrong=self.candidate();wrong.evidence[0]["email"]="someone@else.example";wrong.save()
        self.assertEqual(self.selection()["count"],0)

    def test_historical_evidence_cannot_qualify(self):
        q=self.candidate()
        for e in q.evidence:e["historical"]=True
        q.save()
        self.assertEqual(self.selection()["count"],0)

    def test_unsupported_evidence_does_not_fill_selection(self):
        self.candidate("website_not_listed")
        self.assertEqual(self.selection()["count"],0)

    def test_duplicate_contact_is_selected_once(self):
        self.candidate(email="shared@business.example")
        self.candidate(email="shared@business.example")
        self.assertEqual(self.selection()["count"],1)

    def test_duplicate_identity_variants_do_not_create_two_places(self):
        a=self.candidate();b=self.candidate()
        b.prospect.nom=a.prospect.nom+" SARL";b.prospect.save()
        for e in b.evidence:
            e["company"]["name"]=b.prospect.nom
            if e["kind"]=="corroborated_contact":e["identity"]=_identity(b.prospect)
        b.save()
        self.assertEqual(self.selection()["count"],1)

    def test_transitive_duplicates_are_grouped(self):
        a=self.candidate(email="shared@business.example")
        b=self.candidate(email="shared@business.example")
        c=self.candidate()
        b.prospect.website="https://shared-business.example/"
        c.prospect.website="https://shared-business.example/"
        b.prospect.save();c.prospect.save()
        self.assertEqual(self.selection()["count"],1)

    def test_human_decisions_also_block_duplicate_aliases(self):
        for decision in ["approved","rejected","deferred","excluded"]:
            with self.subTest(decision=decision):
                QualificationReview.objects.all().delete();Prospect.objects.all().delete()
                self.candidate(status=decision,email=f"{decision}@business.example")
                self.candidate(email=f"{decision}@business.example")
                self.assertEqual(self.selection()["count"],0)

    def test_opposition_and_prior_outreach_are_excluded(self):
        q=self.candidate();q.prospect.status="do_not_contact";q.prospect.save()
        contacted=self.candidate()
        EmailLog.objects.create(prospect=contacted.prospect,subject="Ancien",body="Historique",success=False)
        self.assertEqual(self.selection()["count"],0)

    def test_reading_selection_never_changes_reviews_or_drafts(self):
        q=self.candidate()
        EmailDraft.objects.create(prospect=q.prospect,subject="À conserver",body="Texte humain")
        before=list(QualificationReview.objects.values())
        drafts=list(EmailDraft.objects.values())
        self.selection();self.selection()
        self.assertEqual(list(QualificationReview.objects.values()),before)
        self.assertEqual(list(EmailDraft.objects.values()),drafts)

    def test_ties_are_stable_and_freshness_is_based_on_proof(self):
        a=self.candidate(age=3);b=self.candidate(age=1)
        self.assertEqual([r["id"] for r in self.selection()["results"]],[b.pk,a.pk])
        # Repeat reads keep the same deterministic ordering.
        self.assertEqual(self.selection()["results"],self.selection()["results"])

    def test_source_url_and_provenance_are_required(self):
        bad=self.candidate();bad.evidence[0]["url"]="http://127.0.0.1/contact";bad.save()
        unknown=self.candidate();unknown.evidence[0].pop("origin");unknown.save()
        self.assertEqual(self.selection()["count"],0)

    def test_demonstration_selects_only_justified_candidates(self):
        self.candidate(age=40)
        self.candidate("website_not_listed")
        menu=self.candidate()
        dispersed=self.candidate("dispersed_information")
        q=self.candidate(status="rejected")
        result=self.selection()
        self.assertEqual([r["id"] for r in result["results"]],[menu.pk,dispersed.pk])
        print("DEMO LOT3",[(r["prospect"]["nom"],r["selection"]["rank"],r["selection"]["signal"]) for r in result["results"]])

    def test_invalid_or_empty_contact_cannot_be_shortlisted(self):
        for email in ["", "not-an-email"]:
            q=self.candidate()
            q.prospect.email=email;q.prospect.save()
            q.evidence[0]["email"]=email;q.save()
        self.assertEqual(self.selection()["count"],0)
