from django.contrib import admin
from .models import Campaign, Prospect, EmailTemplate, EmailLog


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ["secteur", "ville", "rayon_km", "status", "total_prospects", "created_at"]
    list_filter = ["status", "secteur"]
    search_fields = ["ville", "secteur"]


@admin.register(Prospect)
class ProspectAdmin(admin.ModelAdmin):
    list_display = ["nom", "ville", "email", "telephone", "status", "campaign"]
    list_filter = ["status", "has_website", "campaign__secteur"]
    search_fields = ["nom", "email", "ville"]


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ["name", "subject", "created_at"]
    search_fields = ["name", "subject"]


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = ["prospect", "subject", "sent_at", "success"]
    list_filter = ["success"]
    search_fields = ["prospect__nom", "subject"]
