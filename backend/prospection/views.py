from django.conf import settings
from django.utils import timezone
from django.db.models import Count, Q
from django.contrib.auth.models import User
from rest_framework import mixins, viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import Campaign, Prospect, EmailTemplate, EmailLog
from .serializers import (
    CampaignSerializer,
    ProspectSerializer,
    EmailTemplateSerializer,
)
from .services import run_prospection, send_prospect_email
from .demo import (
    demo_campaign,
    demo_campaigns,
    demo_prospect,
    demo_prospects,
    demo_stats,
    demo_template,
    demo_templates,
)


def is_owner_request(request):
    owner_token = getattr(settings, "OWNER_ACCESS_TOKEN", "")
    if not owner_token:
        return True
    return request.headers.get("X-Owner-Token") == owner_token


def is_demo_request(request):
    return not is_owner_request(request)


def not_found_response():
    return Response({"detail": "Introuvable."}, status=status.HTTP_404_NOT_FOUND)


def demo_campaign_from_payload(data, pk=999):
    return {
        "id": pk,
        "secteur": data.get("secteur", "restaurant"),
        "ville": data.get("ville", "Rennes"),
        "rayon_km": data.get("rayon_km", 10),
        "status": "draft",
        "error_message": "",
        "created_at": timezone.now().isoformat(),
        "launched_at": None,
        "total_prospects": 0,
        "prospects_with_email": 0,
    }


def demo_template_from_payload(data, pk=999):
    now = timezone.now().isoformat()
    return {
        "id": pk,
        "name": data.get("name", "Template demo"),
        "subject": data.get("subject", "Bonjour {nom}"),
        "body": data.get("body", "Message de demonstration."),
        "created_at": now,
        "updated_at": now,
    }


# ── Campaigns ─────────────────────────────────────────────────

class CampaignViewSet(viewsets.ModelViewSet):
    queryset = Campaign.objects.all()
    serializer_class = CampaignSerializer
    http_method_names = ["get", "post", "patch", "delete"]

    def list(self, request, *args, **kwargs):
        if is_demo_request(request):
            return Response(demo_campaigns())
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        if is_demo_request(request):
            campaign = demo_campaign(kwargs.get("pk"))
            if not campaign:
                return not_found_response()
            return Response(campaign)
        return super().retrieve(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        if is_demo_request(request):
            return Response(
                demo_campaign_from_payload(request.data),
                status=status.HTTP_201_CREATED,
            )
        return super().create(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if is_demo_request(request):
            return Response(status=status.HTTP_204_NO_CONTENT)
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"], url_path="launch")
    def launch(self, request, pk=None):
        if is_demo_request(request):
            return Response(
                {
                    "message": "Prospection demo terminee.",
                    "total_found": 18,
                    "with_email": 12,
                }
            )

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

class ProspectViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = ProspectSerializer
    http_method_names = ["get", "post", "patch", "delete"]

    def list(self, request, *args, **kwargs):
        if is_demo_request(request):
            return Response(demo_prospects(request.query_params))
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        if is_demo_request(request):
            prospect = demo_prospect(kwargs.get("pk"))
            if not prospect:
                return not_found_response()
            return Response(prospect)
        return super().retrieve(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        if is_demo_request(request):
            prospect = demo_prospect(kwargs.get("pk"))
            if not prospect:
                return not_found_response()
            prospect.update(request.data)
            return Response(prospect)
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if is_demo_request(request):
            return Response(status=status.HTTP_204_NO_CONTENT)
        return super().destroy(request, *args, **kwargs)

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

        has_website = self.request.query_params.get("has_website")
        if has_website == "true":
            qs = qs.filter(has_website=True)
        elif has_website == "false":
            qs = qs.filter(Q(has_website=False) | Q(website=None) | Q(website=""))

        return qs

    @action(detail=True, methods=["post"], url_path="send-email")
    def send_email(self, request, pk=None):
        if is_demo_request(request):
            prospect = demo_prospect(pk)
            if not prospect:
                return not_found_response()
            return Response({"message": "Email demo simule."})

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

    def list(self, request, *args, **kwargs):
        if is_demo_request(request):
            return Response(demo_templates())
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        if is_demo_request(request):
            template = demo_template(kwargs.get("pk"))
            if not template:
                return not_found_response()
            return Response(template)
        return super().retrieve(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        if is_demo_request(request):
            return Response(
                demo_template_from_payload(request.data),
                status=status.HTTP_201_CREATED,
            )
        return super().create(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        if is_demo_request(request):
            template = demo_template(kwargs.get("pk")) or demo_template_from_payload({}, kwargs.get("pk"))
            template.update(request.data)
            template["updated_at"] = timezone.now().isoformat()
            return Response(template)
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if is_demo_request(request):
            return Response(status=status.HTTP_204_NO_CONTENT)
        return super().destroy(request, *args, **kwargs)


# ── Register ──────────────────────────────────────────────────

@api_view(["POST"])
@permission_classes([AllowAny])
def register(request):
    username = request.data.get("username", "").strip()
    password = request.data.get("password", "")

    if not username or not password:
        return Response({"error": "Champs requis."}, status=status.HTTP_400_BAD_REQUEST)
    if len(password) < 8:
        return Response({"error": "Mot de passe trop court (8 caractères min)."}, status=status.HTTP_400_BAD_REQUEST)
    if User.objects.filter(username=username).exists():
        return Response({"error": "Ce nom d'utilisateur est déjà pris."}, status=status.HTTP_400_BAD_REQUEST)

    User.objects.create_user(username=username, password=password)
    return Response({"message": "Compte créé."}, status=status.HTTP_201_CREATED)


# ── Stats globales ─────────────────────────────────────────────

@api_view(["GET"])
def stats(request):
    if is_demo_request(request):
        return Response(demo_stats())

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


@api_view(["GET"])
@permission_classes([AllowAny])
def session_status(request):
    is_owner = is_owner_request(request)
    return Response(
        {
            "is_owner": is_owner,
            "mode": "owner" if is_owner else "demo",
            "demo_enabled": bool(getattr(settings, "OWNER_ACCESS_TOKEN", "")),
        }
    )
