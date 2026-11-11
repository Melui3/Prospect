import logging
import threading
import hmac

from django.conf import settings
from django.db import close_old_connections, connection
from django.utils import timezone
from django.db.models import Count, Q
from django.contrib.auth.models import User
from rest_framework import mixins, viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, BasePermission
from rest_framework.response import Response

from .models import Campaign, Prospect, EmailTemplate, EmailLog
from .serializers import (
    CampaignSerializer,
    ProspectListSerializer,
    ProspectSerializer,
    EmailTemplateSerializer,
)
from .services import run_prospection, send_prospect_email
from .demo import (
    demo_campaign,
    demo_campaign_from_payload,
    demo_campaigns,
    demo_prospect,
    demo_prospects,
    demo_stats,
    demo_template,
    demo_template_from_payload,
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
    if getattr(settings, "DESKTOP_MODE", False):
        origin = request.headers.get("Origin")
        if origin and origin != f"{request.scheme}://{request.get_host()}":
            return False
    owner_token = getattr(settings, "OWNER_ACCESS_TOKEN", "")
    if settings.DESKTOP_MODE and settings.DESKTOP_AUTO_AUTH:
        from .private_config import desktop_access_token
        owner_token = desktop_access_token()
    if not owner_token:
        return not getattr(settings, "REQUIRE_OWNER_TOKEN", False)
    return hmac.compare_digest(request.headers.get("X-Owner-Token", ""), owner_token)


def is_demo_request(request):
    if is_owner_request(request):
        return False
    return (
        bool(getattr(settings, "DEMO_MODE", False))
        and request.headers.get("X-Demo-Mode") == "true"
    )


class OwnerOrDemo(BasePermission):
    message = "Acces prive requis, ou mode demo indisponible."

    def has_permission(self, request, view):
        return is_owner_request(request) or is_demo_request(request)


def not_found_response():
    return Response({"detail": "Introuvable."}, status=status.HTTP_404_NOT_FOUND)


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
    permission_classes = [OwnerOrDemo]
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
                {
                    **demo_campaign_from_payload(request.data),
                    "demo_notice": "Creation simulee: aucune donnee n'est enregistree.",
                },
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
                    "message": "Mode demo: recherche externe non lancee.",
                    "status": "done",
                    "demo_blocked": True,
                    "total_found": 18,
                    "with_email": 7,
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


# ── Prospects ─────────────────────────────────────────────────

class ProspectViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = ProspectSerializer
    permission_classes = [OwnerOrDemo]
    http_method_names = ["get", "post", "patch", "delete"]

    def get_serializer_class(self):
        if self.action == "list":
            return ProspectListSerializer
        return ProspectSerializer

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
        qs = Prospect.objects.select_related("campaign")

        if self.action == "list":
            qs = qs.annotate(
                emails_sent_count=Count(
                    "email_logs",
                    filter=Q(email_logs__success=True),
                )
            )
        else:
            qs = qs.prefetch_related("email_logs")

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
            if not demo_prospect(pk):
                return not_found_response()
            return Response(
                {
                    "message": "Mode demo: aucun email reel n'a ete envoye.",
                    "demo_blocked": True,
                }
            )

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
    permission_classes = [OwnerOrDemo]
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
                {
                    **demo_template_from_payload(request.data),
                    "demo_notice": "Creation simulee: aucun template n'est enregistre.",
                },
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
            template = demo_template(kwargs.get("pk")) or demo_template_from_payload(
                {},
                kwargs.get("pk"),
            )
            template.update(request.data)
            template["updated_at"] = timezone.now().isoformat()
            template["demo_notice"] = "Sauvegarde simulee: aucune donnee n'est modifiee."
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
@permission_classes([OwnerOrDemo])
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
    is_demo = is_demo_request(request)
    auth_required = bool(getattr(settings, "OWNER_ACCESS_TOKEN", "")) or bool(
        getattr(settings, "REQUIRE_OWNER_TOKEN", False)
    ) or bool(settings.DESKTOP_MODE and settings.DESKTOP_AUTO_AUTH)
    mode = "private" if is_owner else "demo" if is_demo else "locked"

    return Response(
        {
            "is_owner": is_owner,
            "is_demo": is_demo,
            "mode": mode,
            "auth_required": auth_required,
            "demo_available": bool(getattr(settings, "DEMO_MODE", False)),
            "desktop": bool(getattr(settings, "DESKTOP_MODE", False)),
        }
    )
