from django.db import models
from django.utils import timezone


class Campaign(models.Model):
    STATUS_CHOICES = [
        ("draft", "Brouillon"),
        ("running", "En cours"),
        ("queued", "En attente"),
        ("paused", "En pause"),
        ("done", "Terminée"),
        ("error", "Erreur"),
    ]

    secteur = models.CharField(max_length=100)
    ville = models.CharField(max_length=100)
    rayon_km = models.IntegerField(default=5)
    repeat_days = models.PositiveSmallIntegerField(
        default=0,
        choices=[(0, "Désactivée"), (7, "Chaque semaine"), (14, "Toutes les deux semaines"), (30, "Chaque mois")],
    )
    next_search_at = models.DateTimeField(null=True, blank=True, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    launched_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.secteur} — {self.ville}"

    @property
    def total_prospects(self):
        return self.discovered_prospects.filter(merged_into=None).count()

    @property
    def prospects_with_email(self):
        return self.discovered_prospects.filter(merged_into=None).exclude(email="").exclude(email=None).count()


class Prospect(models.Model):
    STATUS_CHOICES = [
        ("new", "Nouveau"),
        ("contacted", "Contacté"),
        ("replied", "Répondu"),
        ("ignored", "Ignoré"),
        ("interested", "Interesse"),
        ("proposal", "Devis envoye"),
        ("won", "Gagne"),
        ("lost", "Refuse"),
        ("do_not_contact", "Ne plus contacter"),
    ]

    campaign = models.ForeignKey(
        Campaign, on_delete=models.SET_NULL, null=True, related_name="prospects"
    )
    campaigns = models.ManyToManyField(Campaign, related_name="discovered_prospects", blank=True)
    identity_key = models.CharField(max_length=64, unique=True, null=True, blank=True)
    external_id = models.CharField(max_length=100, blank=True, db_index=True)
    merged_into = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="merged_records")
    nom = models.CharField(max_length=200)
    adresse = models.CharField(max_length=300, blank=True, default="")
    ville = models.CharField(max_length=100, blank=True, default="")
    telephone = models.CharField(max_length=50, blank=True, default="")
    email = models.EmailField(blank=True, null=True)
    website = models.URLField(max_length=500, blank=True, null=True)
    has_website = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="new")
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)
    priority = models.CharField(max_length=10, choices=[("low", "Basse"), ("normal", "Normale"), ("high", "Haute")], default="normal")
    next_followup_at = models.DateTimeField(null=True, blank=True, db_index=True)
    last_contacted_at = models.DateTimeField(null=True, blank=True)
    email_source = models.CharField(max_length=500, blank=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    enrichment_status = models.CharField(max_length=20, default="pending", choices=[("pending", "A completer"), ("found", "Email trouve"), ("not_found", "Introuvable"), ("error", "A reessayer")])
    enriched_at = models.DateTimeField(null=True, blank=True)
    raw_tags = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.nom


class EmailTemplate(models.Model):
    name = models.CharField(max_length=100)
    subject = models.CharField(max_length=200)
    body = models.TextField(
        help_text=(
            "Variables disponibles : {nom}, {ville}, {secteur}, "
            "{website}"
        )
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def render(self, prospect: Prospect) -> tuple[str, str]:
        """Retourne (sujet, corps) avec les variables remplacées."""
        context = {
            "nom": prospect.nom,
            "ville": prospect.ville or (prospect.campaign.ville if prospect.campaign else ""),
            "secteur": prospect.campaign.secteur if prospect.campaign else "",
            "website": prospect.website or "",
            "site": prospect.website or "",
            "social": "",
            "social_platform": "",
        }
        subject = self.subject.format(**context)
        body = self.body.format(**context)
        return subject, body


class EmailLog(models.Model):
    prospect = models.ForeignKey(
        Prospect, on_delete=models.CASCADE, related_name="email_logs"
    )
    template = models.ForeignKey(
        EmailTemplate, on_delete=models.SET_NULL, null=True, blank=True
    )
    subject = models.CharField(max_length=200)
    body = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True, default="")
    recipient = models.EmailField(blank=True)
    message_id = models.CharField(max_length=250, blank=True, db_index=True)
    request_key = models.CharField(max_length=80, null=True, blank=True, unique=True)
    delivery_status = models.CharField(max_length=30, default="sent")
    delivery_updated_at = models.DateTimeField(null=True, blank=True)
    source = models.CharField(max_length=20, default="smtp")

    class Meta:
        ordering = ["-sent_at"]

    def __str__(self):
        return f"Email → {self.prospect.nom} ({self.sent_at:%d/%m/%Y})"


class ProspectEvent(models.Model):
    prospect = models.ForeignKey(Prospect, on_delete=models.CASCADE, related_name="events")
    kind = models.CharField(max_length=30)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class SearchJob(models.Model):
    campaign = models.ForeignKey(Campaign, null=True, on_delete=models.CASCADE, related_name="jobs")
    prospect = models.ForeignKey(Prospect, null=True, on_delete=models.CASCADE, related_name="jobs")
    kind = models.CharField(max_length=20, default="search")
    status = models.CharField(max_length=20, default="queued", db_index=True)
    stage = models.CharField(max_length=80, default="En attente")
    payload = models.JSONField(default=dict)
    total = models.PositiveIntegerField(default=0)
    processed = models.PositiveIntegerField(default=0)
    with_email = models.PositiveIntegerField(default=0)
    attempts = models.PositiveIntegerField(default=0)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    next_run_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]


class ServiceCache(models.Model):
    key = models.CharField(max_length=64, unique=True)
    value = models.JSONField()
    expires_at = models.DateTimeField()


class QualificationReview(models.Model):
    STATUS_CHOICES = [
        ("pending", "A examiner"),
        ("approved", "Approuve"),
        ("rejected", "Rejete"),
        ("deferred", "Reporte"),
        ("excluded", "Exclu"),
        ("no_opportunity", "Aucun signal pertinent"),
        ("unverified", "Non verifie"),
    ]
    PRIORITY_CHOICES = [("low", "Basse"), ("medium", "Moyenne"), ("high", "Haute")]

    prospect = models.OneToOneField(Prospect, on_delete=models.CASCADE, related_name="qualification")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default="low")
    reasons = models.JSONField(default=list, blank=True)
    evidence = models.JSONField(default=list, blank=True)
    checked_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-priority", "-checked_at"]


class EmailDraft(models.Model):
    STATE_CHOICES = [("draft", "Brouillon"), ("sent", "Envoye")]

    prospect = models.OneToOneField(Prospect, on_delete=models.CASCADE, related_name="email_draft")
    template = models.ForeignKey(EmailTemplate, null=True, blank=True, on_delete=models.SET_NULL)
    subject = models.CharField(max_length=200, blank=True)
    body = models.TextField(blank=True)
    state = models.CharField(max_length=10, choices=STATE_CHOICES, default="draft")
    updated_at = models.DateTimeField(auto_now=True)
    sent_at = models.DateTimeField(null=True, blank=True)
