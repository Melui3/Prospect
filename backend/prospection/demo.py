from django.utils import timezone


DEMO_CAMPAIGNS = [
    {
        "id": 101,
        "secteur": "association",
        "ville": "Rennes",
        "rayon_km": 15,
        "status": "done",
        "error_message": "",
        "created_at": "2026-07-10T09:15:00+02:00",
        "launched_at": "2026-07-10T09:18:00+02:00",
        "total_prospects": 48,
        "prospects_with_email": 19,
    },
    {
        "id": 102,
        "secteur": "restaurant",
        "ville": "Nantes",
        "rayon_km": 10,
        "status": "done",
        "error_message": "",
        "created_at": "2026-07-11T14:20:00+02:00",
        "launched_at": "2026-07-11T14:23:00+02:00",
        "total_prospects": 86,
        "prospects_with_email": 31,
    },
    {
        "id": 103,
        "secteur": "coiffeur",
        "ville": "Rennes",
        "rayon_km": 10,
        "status": "running",
        "error_message": "",
        "created_at": "2026-07-12T10:05:00+02:00",
        "launched_at": "2026-07-12T10:08:00+02:00",
        "total_prospects": 24,
        "prospects_with_email": 7,
    },
    {
        "id": 104,
        "secteur": "boulangerie",
        "ville": "Combourg",
        "rayon_km": 25,
        "status": "draft",
        "error_message": "",
        "created_at": "2026-07-13T16:35:00+02:00",
        "launched_at": None,
        "total_prospects": 0,
        "prospects_with_email": 0,
    },
]


DEMO_PROSPECTS = [
    {
        "id": 1001,
        "campaign": 101,
        "campaign_secteur": "association",
        "nom": "Collectif Horizon Local",
        "adresse": "12 rue des Ateliers",
        "ville": "Rennes",
        "telephone": "02 00 00 00 11",
        "email": "contact@horizon-local.demo",
        "website": "",
        "has_website": False,
        "status": "contacted",
        "created_at": "2026-07-10T09:25:00+02:00",
        "emails_sent": 1,
    },
    {
        "id": 1002,
        "campaign": 101,
        "campaign_secteur": "association",
        "nom": "Maison des Voisins",
        "adresse": "4 place du Marche",
        "ville": "Cesson-Sevigne",
        "telephone": "02 00 00 00 12",
        "email": "bonjour@maison-voisins.demo",
        "website": "https://maison-voisins.demo",
        "has_website": True,
        "status": "replied",
        "created_at": "2026-07-10T09:28:00+02:00",
        "emails_sent": 2,
    },
    {
        "id": 1003,
        "campaign": 101,
        "campaign_secteur": "association",
        "nom": "Atelier Partage",
        "adresse": "8 avenue des Tilleuls",
        "ville": "Rennes",
        "telephone": "",
        "email": "",
        "website": "",
        "has_website": False,
        "status": "new",
        "created_at": "2026-07-10T09:31:00+02:00",
        "emails_sent": 0,
    },
    {
        "id": 1004,
        "campaign": 102,
        "campaign_secteur": "restaurant",
        "nom": "Le Comptoir du Canal",
        "adresse": "22 quai des Oliviers",
        "ville": "Nantes",
        "telephone": "02 00 00 00 21",
        "email": "reservation@comptoir-canal.demo",
        "website": "",
        "has_website": False,
        "status": "contacted",
        "created_at": "2026-07-11T14:31:00+02:00",
        "emails_sent": 1,
    },
    {
        "id": 1005,
        "campaign": 102,
        "campaign_secteur": "restaurant",
        "nom": "Table Nocturne",
        "adresse": "3 rue des Carmes",
        "ville": "Nantes",
        "telephone": "02 00 00 00 22",
        "email": "",
        "website": "https://table-nocturne.demo",
        "has_website": True,
        "status": "ignored",
        "created_at": "2026-07-11T14:36:00+02:00",
        "emails_sent": 0,
    },
    {
        "id": 1006,
        "campaign": 102,
        "campaign_secteur": "restaurant",
        "nom": "Bistro des Halles",
        "adresse": "18 rue Haute",
        "ville": "Nantes",
        "telephone": "",
        "email": "hello@bistro-halles.demo",
        "website": "",
        "has_website": False,
        "status": "new",
        "created_at": "2026-07-11T14:39:00+02:00",
        "emails_sent": 0,
    },
    {
        "id": 1007,
        "campaign": 103,
        "campaign_secteur": "coiffeur",
        "nom": "Studio Carmin",
        "adresse": "7 rue Saint-Melaine",
        "ville": "Rennes",
        "telephone": "02 00 00 00 31",
        "email": "contact@studio-carmin.demo",
        "website": "",
        "has_website": False,
        "status": "new",
        "created_at": "2026-07-12T10:14:00+02:00",
        "emails_sent": 0,
    },
]


DEMO_TEMPLATES = [
    {
        "id": 201,
        "name": "Sans site - premier contact",
        "subject": "Bonjour {nom} - une presence web simple pour {ville}",
        "body": (
            "Bonjour,\n\n"
            "Je vous contacte car {nom} ressort dans mes recherches locales a {ville}, "
            "mais je n'ai pas trouve de site web clair.\n\n"
            "Je cree des sites rapides et sobres pour aider les structures locales a "
            "presenter leurs services, rassurer les visiteurs et recevoir plus de demandes.\n\n"
            "Seriez-vous ouvert a un court echange ?"
        ),
        "created_at": "2026-07-09T11:00:00+02:00",
        "updated_at": "2026-07-09T11:00:00+02:00",
    },
    {
        "id": 202,
        "name": "Refonte site existant",
        "subject": "Idee rapide pour moderniser {nom}",
        "body": (
            "Bonjour,\n\n"
            "J'ai regarde le site de {nom} ({website}) et je pense qu'une refonte legere "
            "pourrait le rendre plus lisible sur mobile et plus rassurant pour vos visiteurs.\n\n"
            "Je peux vous envoyer une proposition courte si cela vous interesse."
        ),
        "created_at": "2026-07-09T11:20:00+02:00",
        "updated_at": "2026-07-09T11:20:00+02:00",
    },
]


def demo_campaigns():
    return [campaign.copy() for campaign in DEMO_CAMPAIGNS]


def demo_campaign(pk):
    campaign = next((item for item in DEMO_CAMPAIGNS if str(item["id"]) == str(pk)), None)
    return campaign.copy() if campaign else None


def demo_campaign_from_payload(data, pk=901):
    now = timezone.now().isoformat()
    return {
        "id": pk,
        "secteur": data.get("secteur", "association"),
        "ville": data.get("ville", "Rennes"),
        "rayon_km": data.get("rayon_km", 15),
        "status": "draft",
        "error_message": "",
        "created_at": now,
        "launched_at": None,
        "total_prospects": 0,
        "prospects_with_email": 0,
    }


def demo_prospects(params=None):
    params = params or {}
    prospects = list(DEMO_PROSPECTS)

    campaign_id = params.get("campaign")
    if campaign_id:
        prospects = [p for p in prospects if str(p["campaign"]) == str(campaign_id)]

    prospect_status = params.get("status")
    if prospect_status:
        prospects = [p for p in prospects if p["status"] == prospect_status]

    has_email = params.get("has_email")
    if has_email == "true":
        prospects = [p for p in prospects if p.get("email")]
    elif has_email == "false":
        prospects = [p for p in prospects if not p.get("email")]

    has_website = params.get("has_website")
    if has_website == "true":
        prospects = [p for p in prospects if p.get("has_website")]
    elif has_website == "false":
        prospects = [p for p in prospects if not p.get("has_website")]

    return [prospect.copy() for prospect in prospects]


def demo_prospect(pk):
    prospect = next((item for item in DEMO_PROSPECTS if str(item["id"]) == str(pk)), None)
    if not prospect:
        return None
    prospect = prospect.copy()

    return {
        **prospect,
        "email_logs": [
            {
                "id": 3001,
                "subject": "Message demo envoye",
                "body": "Ceci est un journal anonymise de demonstration.",
                "sent_at": "2026-07-12T15:00:00+02:00",
                "success": True,
                "error_message": "",
            }
        ]
        if prospect["emails_sent"]
        else [],
    }


def demo_templates():
    return [template.copy() for template in DEMO_TEMPLATES]


def demo_template(pk):
    template = next((item for item in DEMO_TEMPLATES if str(item["id"]) == str(pk)), None)
    return template.copy() if template else None


def demo_template_from_payload(data, pk=902):
    now = timezone.now().isoformat()
    return {
        "id": pk,
        "name": data.get("name", "Template demo non persiste"),
        "subject": data.get("subject", "Bonjour {nom}"),
        "body": data.get("body", "Message de demonstration."),
        "created_at": now,
        "updated_at": now,
    }


def demo_stats():
    emails_sent = sum(prospect["emails_sent"] for prospect in DEMO_PROSPECTS)
    return {
        "total_campaigns": len(DEMO_CAMPAIGNS),
        "done_campaigns": sum(1 for campaign in DEMO_CAMPAIGNS if campaign["status"] == "done"),
        "total_prospects": sum(campaign["total_prospects"] for campaign in DEMO_CAMPAIGNS),
        "prospects_with_email": sum(campaign["prospects_with_email"] for campaign in DEMO_CAMPAIGNS),
        "emails_sent": emails_sent,
        "prospects_contacted": sum(
            1 for prospect in DEMO_PROSPECTS if prospect["status"] in {"contacted", "replied"}
        ),
        "prospects_replied": sum(1 for prospect in DEMO_PROSPECTS if prospect["status"] == "replied"),
    }
