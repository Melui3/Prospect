from django.utils import timezone
from django.db.models import Count, Q
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view
from rest_framework.response import Response

from .models import Campaign, Prospect, EmailTemplate, EmailLog
from .serializers import (
    CampaignSerializer,
    ProspectSerializer,
    EmailTemplateSerializer,
)
from .services import run_prospection, send_prospect_email


# ── Campaigns ─────────────────────────────────────────────────

class CampaignViewSet(viewsets.ModelViewSet):
    queryset = Campaign.objects.all()
    serializer_class = CampaignSerializer
    http_method_names = ["get", "post", "patch", "delete"]

    @action(detail=True, methods=["post"], url_path="launch")
    def launch(self, request, pk=None):
        campaign = self.get_object()

        if campaign.status == "running":
            return Response(
                {"error": "Campagne déjà en cours."}, status=status.HTTP_400_BAD_REQUEST
            )

        campaign.status = "running"
        campaign.launched_at = timezone.now()
        campaign.error_message = ""
        campaign.save(update_fields=["status", "launched_at", "error_message"])

        try:
            stats = run_prospection(campaign)
            campaign.status = "done"
            campaign.save(update_fields=["status"])
            return Response(
                {
                    "message": "Prospection terminée.",
                    "total_found": stats["total"],
                    "with_email": stats["with_email"],
                }
            )
        except Exception as exc:
            campaign.status = "error"
            campaign.error_message = str(exc)
            campaign.save(update_fields=["status", "error_message"])
            return Response(
                {"error": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ── Prospects ─────────────────────────────────────────────────

class ProspectViewSet(viewsets.ModelViewSet):
    serializer_class = ProspectSerializer
    http_method_names = ["get", "patch", "delete"]

    def get_queryset(self):
        qs = Prospect.objects.select_related("campaign").prefetch_related("email_logs")

        campaign_id = self.request.query_params.get("campaign")
        if campaign_id:
            qs = qs.filter(campaign_id=campaign_id)

        prospect_status = self.request.query_params.get("status")
        if prospect_status:
            qs = qs.filter(status=prospect_status)

        has_email = self.request.query_params.get("has_email")
        if has_email == "true":
            qs = qs.exclude(email=None).exclude(email="")
        elif has_email == "false":
            qs = qs.filter(Q(email=None) | Q(email=""))

        return qs

    @action(detail=True, methods=["post"], url_path="send-email")
    def send_email(self, request, pk=None):
        prospect = self.get_object()
        template_id = request.data.get("template_id")

        if not template_id:
            return Response(
                {"error": "template_id requis."}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            template = EmailTemplate.objects.get(pk=template_id)
        except EmailTemplate.DoesNotExist:
            return Response(
                {"error": "Template introuvable."}, status=status.HTTP_404_NOT_FOUND
            )

        result = send_prospect_email(prospect, template)

        if result["success"]:
            return Response({"message": "Email envoyé !"})
        return Response({"error": result["error"]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ── Templates ─────────────────────────────────────────────────

class EmailTemplateViewSet(viewsets.ModelViewSet):
    queryset = EmailTemplate.objects.all()
    serializer_class = EmailTemplateSerializer
    http_method_names = ["get", "post", "patch", "delete"]


# ── Stats globales ─────────────────────────────────────────────

@api_view(["GET"])
def stats(request):
    total_campaigns = Campaign.objects.count()
    done_campaigns = Campaign.objects.filter(status="done").count()
    total_prospects = Prospect.objects.count()
    prospects_with_email = Prospect.objects.exclude(email=None).exclude(email="").count()
    emails_sent = EmailLog.objects.filter(success=True).count()
    prospects_contacted = Prospect.objects.filter(status="contacted").count()
    prospects_replied = Prospect.objects.filter(status="replied").count()

    return Response(
        {
            "total_campaigns": total_campaigns,
            "done_campaigns": done_campaigns,
            "total_prospects": total_prospects,
            "prospects_with_email": prospects_with_email,
            "emails_sent": emails_sent,
            "prospects_contacted": prospects_contacted,
            "prospects_replied": prospects_replied,
        }
    )
