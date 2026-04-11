from django.db import models


class Campaign(models.Model):
    STATUS_CHOICES = [
        ("draft", "Brouillon"),
        ("running", "En cours"),
        ("done", "Terminée"),
        ("error", "Erreur"),
    ]

    secteur = models.CharField(max_length=100)
    ville = models.CharField(max_length=100)
    rayon_km = models.IntegerField(default=5)
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
        return self.prospects.count()

    @property
    def prospects_with_email(self):
        return self.prospects.exclude(email="").exclude(email=None).count()


class Prospect(models.Model):
    STATUS_CHOICES = [
        ("new", "Nouveau"),
        ("contacted", "Contacté"),
        ("replied", "Répondu"),
        ("ignored", "Ignoré"),
    ]

    campaign = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, related_name="prospects"
    )
    nom = models.CharField(max_length=200)
    adresse = models.CharField(max_length=300, blank=True, default="")
    ville = models.CharField(max_length=100, blank=True, default="")
    telephone = models.CharField(max_length=50, blank=True, default="")
    email = models.EmailField(blank=True, null=True)
    website = models.URLField(max_length=500, blank=True, null=True)
    has_website = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="new")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.nom


class EmailTemplate(models.Model):
    name = models.CharField(max_length=100)
    subject = models.CharField(max_length=200)
    body = models.TextField(
        help_text="Variables disponibles : {nom}, {ville}, {secteur}"
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
            "ville": prospect.ville or prospect.campaign.ville,
            "secteur": prospect.campaign.secteur,
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

    class Meta:
        ordering = ["-sent_at"]

    def __str__(self):
        return f"Email → {self.prospect.nom} ({self.sent_at:%d/%m/%Y})"
