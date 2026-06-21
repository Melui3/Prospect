import logging
import threading

from django.conf import settings
from django.db import close_old_connections, connection
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
from .services import ProspectionTemporaryError, run_prospection, send_prospect_email
from .demo import (
    demo_campaign,
    demo_campaigns,
    demo_prospect,
    demo_prospects,
    demo_stats,
    demo_template,
    demo_templates,
)

logger = logging.getLogger(__name__)


def start_campaign_worker(campaign_id):
    thread = threading.Thread(
        target=_run_campaign_worker,
        args=(campaign_id,),
        daemon=True,
        name=f"campaign-{campaign_id}-prospection",
    )
    thread.start()


def _run_campaign_worker(campaign_id):
    close_old_connections()
    try:
        campaign = Campaign.objects.get(pk=campaign_id)
        try:
            run_prospection(campaign)
            campaign.status = "done"
            campaign.error_message = ""
            campaign.save(update_fields=["status", "error_message"])
        except Exception as exc:
            logger.exception("Campaign %s prospection failed", campaign_id)
            campaign.status = "error"
            campaign.error_message = str(exc)
            campaign.save(update_fields=["status", "error_message"])
    except Exception:
        logger.exception("Campaign %s worker failed before completion", campaign_id)
    finally:
        close_old_connections()


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


def template_db_columns():
    with connection.cursor() as cursor:
        return {
            column.name
            for column in connection.introspection.get_table_description(
                cursor,
                EmailTemplate._meta.db_table,
            )
        }


def template_value_fields():
    columns = template_db_columns()
    fields = ["id", "name", "subject", "body"]
    for field in ("created_at", "updated_at"):
        if field in columns:
            fields.append(field)
    return fields


def normalize_template_row(row):
    if "created_at" not in row:
        row["created_at"] = None
    if "updated_at" not in row:
        row["updated_at"] = row["created_at"]
    return row


def template_queryset_values():
    return EmailTemplate.objects.values(*template_value_fields())


def template_ordered_values():
    order_field = "-created_at" if "created_at" in template_db_columns() else "-id"
    return template_queryset_values().order_by(order_field)


def template_response(pk):
    row = template_queryset_values().filter(pk=pk).first()
    if not row:
        return None
    return normalize_template_row(row)


def validate_template_payload(data, partial=False):
    updates = {}
    errors = {}
    limits = {"name": 100, "subject": 200}

    for field in ("name", "subject", "body"):
        if partial and field not in data:
            continue

        value = data.get(field, "")
        if value is None:
            value = ""
        value = str(value).replace("\x00", "")

        if not value.strip():
            errors[field] = "Champ requis."
            continue

        max_length = limits.get(field)
        if max_length and len(value) > max_length:
            errors[field] = f"{max_length} caracteres maximum."
            continue

        updates[field] = value.strip() if field != "body" else value

    return updates, errors


def insert_template(updates):
    now = timezone.now()
    columns = template_db_columns()
    fields = ["name", "subject", "body"]
    params = [updates["name"], updates["subject"], updates["body"]]

    if "created_at" in columns:
        fields.append("created_at")
        params.append(now)
    if "updated_at" in columns:
        fields.append("updated_at")
        params.append(now)

    quote = connection.ops.quote_name
    table = quote(EmailTemplate._meta.db_table)
    column_sql = ", ".join(quote(field) for field in fields)
    placeholders = ", ".join(["%s"] * len(fields))

    with connection.cursor() as cursor:
        if connection.vendor == "postgresql":
            cursor.execute(
                f"INSERT INTO {table} ({column_sql}) VALUES ({placeholders}) RETURNING id",
                params,
            )
            return cursor.fetchone()[0]

        cursor.execute(
            f"INSERT INTO {table} ({column_sql}) VALUES ({placeholders})",
            params,
        )
        return cursor.lastrowid


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

        start_campaign_worker(campaign.id)
        return Response(
            {
                "message": "Prospection lancee.",
                "status": "running",
                "campaign_id": campaign.id,
            }
        )

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
        except ProspectionTemporaryError as exc:
            campaign.status = "error"
            campaign.error_message = str(exc)
            campaign.save(update_fields=["status", "error_message"])
            return Response(
                {
                    "status": "error",
                    "error": str(exc),
                    "total_found": campaign.total_prospects,
                    "with_email": campaign.prospects_with_email,
                }
            )
        except Exception as exc:
            campaign.status = "error"
            campaign.error_message = str(exc)
            campaign.save(update_fields=["status", "error_message"])
            return Response(
                {
                    "status": "error",
                    "error": str(exc),
                    "total_found": campaign.total_prospects,
                    "with_email": campaign.prospects_with_email,
                }
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
        try:
            templates = [
                normalize_template_row(row)
                for row in template_ordered_values()
            ]
            return Response(templates)
        except Exception as exc:
            logger.exception("Template list failed")
            return Response(
                {"error": "Impossible de charger les templates.", "detail": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def retrieve(self, request, *args, **kwargs):
        if is_demo_request(request):
            template = demo_template(kwargs.get("pk"))
            if not template:
                return not_found_response()
            return Response(template)
        try:
            template = template_response(kwargs.get("pk"))
            if not template:
                return not_found_response()
            return Response(template)
        except Exception as exc:
            logger.exception("Template retrieve failed")
            return Response(
                {"error": "Impossible de charger ce template.", "detail": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def create(self, request, *args, **kwargs):
        if is_demo_request(request):
            return Response(
                demo_template_from_payload(request.data),
                status=status.HTTP_201_CREATED,
            )
        updates, errors = validate_template_payload(request.data)
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            template_id = insert_template(updates)
            return Response(
                template_response(template_id),
                status=status.HTTP_201_CREATED,
            )
        except Exception as exc:
            logger.exception("Template create failed")
            return Response(
                {"error": "Impossible de creer ce template.", "detail": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def partial_update(self, request, *args, **kwargs):
        if is_demo_request(request):
            template = demo_template(kwargs.get("pk")) or demo_template_from_payload({}, kwargs.get("pk"))
            template.update(request.data)
            template["updated_at"] = timezone.now().isoformat()
            return Response(template)
        template_id = kwargs.get("pk")
        if not template_response(template_id):
            return not_found_response()

        updates, errors = validate_template_payload(request.data, partial=True)
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)
        if not updates:
            return Response(template_response(template_id))

        try:
            if "updated_at" in template_db_columns():
                updates["updated_at"] = timezone.now()
            EmailTemplate.objects.filter(pk=template_id).update(**updates)
            return Response(template_response(template_id))
        except Exception as exc:
            logger.exception("Template update failed")
            return Response(
                {"error": "Impossible de sauvegarder ce template.", "detail": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def destroy(self, request, *args, **kwargs):
        if is_demo_request(request):
            return Response(status=status.HTTP_204_NO_CONTENT)
        try:
            deleted, _ = EmailTemplate.objects.filter(pk=kwargs.get("pk")).delete()
            if not deleted:
                return not_found_response()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as exc:
            logger.exception("Template delete failed")
            return Response(
                {"error": "Impossible de supprimer ce template.", "detail": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


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
