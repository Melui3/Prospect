from copy import deepcopy


DEMO_CAMPAIGNS = [
    {
        "id": 101,
        "secteur": "restaurant",
        "ville": "Rennes",
        "rayon_km": 12,
        "status": "done",
        "error_message": "",
        "created_at": "2026-06-09T09:15:00+02:00",
        "launched_at": "2026-06-09T09:16:00+02:00",
        "total_prospects": 4,
        "prospects_with_email": 3,
    },
    {
        "id": 102,
        "secteur": "boulangerie",
        "ville": "Fougeres",
        "rayon_km": 8,
        "status": "done",
        "error_message": "",
        "created_at": "2026-06-08T14:20:00+02:00",
        "launched_at": "2026-06-08T14:21:00+02:00",
        "total_prospects": 3,
        "prospects_with_email": 2,
    },
]

DEMO_PROSPECTS = [
    {
        "id": 1001,
        "campaign": 101,
        "campaign_secteur": "restaurant",
        "nom": "Le Comptoir Demo",
        "adresse": "12 rue de la Demo",
        "ville": "Rennes",
        "telephone": "+33 2 99 00 00 01",
        "email": "contact@demo-comptoir.example",
        "website": None,
        "has_website": False,
        "status": "new",
        "created_at": "2026-06-09T09:18:00+02:00",
        "email_logs": [],
        "emails_sent": 0,
    },
    {
        "id": 1002,
        "campaign": 101,
        "campaign_secteur": "restaurant",
        "nom": "Maison Exemple",
        "adresse": "4 place du Marche",
        "ville": "Rennes",
        "telephone": "+33 2 99 00 00 02",
        "email": "bonjour@maison-exemple.demo",
        "website": None,
        "has_website": False,
        "status": "contacted",
        "created_at": "2026-06-09T09:19:00+02:00",
        "email_logs": [
            {
                "id": 5001,
                "subject": "Bonjour Maison Exemple",
                "body": "Message de demonstration.",
                "sent_at": "2026-06-09T10:00:00+02:00",
                "success": True,
                "error_message": "",
            }
        ],
        "emails_sent": 1,
    },
    {
        "id": 1003,
        "campaign": 101,
        "campaign_secteur": "restaurant",
        "nom": "Bistro Sans Email",
        "adresse": "8 avenue Test",
        "ville": "Rennes",
        "telephone": "+33 2 99 00 00 03",
        "email": None,
        "website": None,
        "has_website": False,
        "status": "new",
        "created_at": "2026-06-09T09:20:00+02:00",
        "email_logs": [],
        "emails_sent": 0,
    },
    {
        "id": 1004,
        "campaign": 102,
        "campaign_secteur": "boulangerie",
        "nom": "Fournil Demo",
        "adresse": "18 rue du Pain",
        "ville": "Fougeres",
        "telephone": "+33 2 99 00 00 04",
        "email": "fournil@demo.example",
        "website": None,
        "has_website": False,
        "status": "replied",
        "created_at": "2026-06-08T14:22:00+02:00",
        "email_logs": [
            {
                "id": 5002,
                "subject": "Votre presence en ligne",
                "body": "Message de demonstration.",
                "sent_at": "2026-06-08T15:00:00+02:00",
                "success": True,
                "error_message": "",
            }
        ],
        "emails_sent": 1,
    },
]

DEMO_TEMPLATES = [
    {
        "id": 201,
        "name": "Premier contact",
        "subject": "Bonjour {nom}, votre site web",
        "body": (
            "Bonjour,\n\n"
            "Je me permets de vous contacter au sujet de {nom} a {ville}.\n\n"
            "Je cree des sites web simples et rapides pour les {secteur}s locaux.\n\n"
            "Seriez-vous disponible pour en discuter ?"
        ),
        "created_at": "2026-06-01T10:00:00+02:00",
        "updated_at": "2026-06-01T10:00:00+02:00",
    }
]


def demo_campaigns():
    return deepcopy(DEMO_CAMPAIGNS)


def demo_campaign(pk):
    return _find_by_id(DEMO_CAMPAIGNS, pk)


def demo_prospects(params=None):
    params = params or {}
    prospects = demo_prospects_unfiltered()

    campaign_id = params.get("campaign")
    if campaign_id:
        prospects = [p for p in prospects if str(p["campaign"]) == str(campaign_id)]

    prospect_status = params.get("status")
    if prospect_status:
        prospects = [p for p in prospects if p["status"] == prospect_status]

    has_email = params.get("has_email")
    if has_email == "true":
        prospects = [p for p in prospects if p["email"]]
    elif has_email == "false":
        prospects = [p for p in prospects if not p["email"]]

    return prospects


def demo_prospects_unfiltered():
    return deepcopy(DEMO_PROSPECTS)


def demo_prospect(pk):
    return _find_by_id(DEMO_PROSPECTS, pk)


def demo_templates():
    return deepcopy(DEMO_TEMPLATES)


def demo_template(pk):
    return _find_by_id(DEMO_TEMPLATES, pk)


def demo_stats():
    prospects = DEMO_PROSPECTS
    campaigns = DEMO_CAMPAIGNS
    return {
        "total_campaigns": len(campaigns),
        "done_campaigns": sum(1 for c in campaigns if c["status"] == "done"),
        "total_prospects": len(prospects),
        "prospects_with_email": sum(1 for p in prospects if p["email"]),
        "emails_sent": sum(p["emails_sent"] for p in prospects),
        "prospects_contacted": sum(1 for p in prospects if p["status"] == "contacted"),
        "prospects_replied": sum(1 for p in prospects if p["status"] == "replied"),
    }


def _find_by_id(items, pk):
    for item in items:
        if str(item["id"]) == str(pk):
            return deepcopy(item)
    return None
