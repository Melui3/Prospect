from datetime import timedelta
from email.utils import parseaddr

from django.conf import settings
from django.db.models import Case, Count, IntegerField, Q, Value, When
from django.utils import timezone
from rest_framework import serializers, viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.generics import get_object_or_404
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from .identity import identity_key
from .jobs import REPEAT_INTERVAL_DAYS, enqueue_enrichment, enqueue_qualification, enqueue_search
from .mail import MailError, send_message, sync_delivery
from .models import Campaign, EmailDraft, EmailLog, EmailTemplate, Prospect, ProspectEvent, QualificationReview, SearchJob
from .private_config import brevo_key, save_private_settings, sender_address
from .views import is_owner_request

CLOSED = ["won", "lost", "ignored", "do_not_contact"]


class OwnerOnly(BasePermission):
    def has_permission(self, request, view):
        return is_owner_request(request)


class JobSerializer(serializers.ModelSerializer):
    class Meta:
        model = SearchJob
        fields = ["id", "campaign", "prospect", "kind", "status", "stage", "total", "processed", "with_email", "attempts", "error", "updated_at", "next_run_at"]


class LogSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailLog
        fields = ["id", "subject", "body", "recipient", "sent_at", "success", "error_message", "source", "delivery_status", "delivery_updated_at"]


class EmailDraftSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailDraft
        fields = ["id", "subject", "body", "template", "state", "updated_at", "sent_at"]
        read_only_fields = ["id", "state", "updated_at", "sent_at"]


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProspectEvent
        fields = ["id", "kind", "message", "created_at"]


class ContactSerializer(serializers.ModelSerializer):
    emails_sent = serializers.IntegerField(source="emails_sent_count", read_only=True)
    campaign_secteur = serializers.SerializerMethodField()
    campaign_names = serializers.SerializerMethodField()
    qualification_status = serializers.SerializerMethodField()

    class Meta:
        model = Prospect
        fields = ["id", "nom", "adresse", "ville", "email", "website", "has_website", "telephone", "status", "notes", "priority", "next_followup_at", "last_contacted_at", "created_at", "email_source", "email_verified_at", "enrichment_status", "enriched_at", "campaign_secteur", "campaign_names", "emails_sent", "qualification_status"]
        read_only_fields = ["created_at", "has_website", "last_contacted_at", "email_source", "email_verified_at", "enrichment_status", "enriched_at"]

    def get_campaign_secteur(self, obj):
        return obj.campaign.secteur if obj.campaign else "Manuel"

    def get_campaign_names(self, obj):
        return [{"id": campaign.pk, "label": f"{campaign.secteur} - {campaign.ville}"} for campaign in obj.campaigns.all()]

    def get_qualification_status(self, obj):
        try:
            return obj.qualification.status
        except QualificationReview.DoesNotExist:
            return "unreviewed"

    def validate(self, data):
        name = data.get("nom", self.instance.nom if self.instance else "")
        city = data.get("ville", self.instance.ville if self.instance else "")
        address = data.get("adresse", self.instance.adresse if self.instance else "")
        key = identity_key(name, city, address)
        duplicates = Prospect.objects.filter(identity_key=key, merged_into=None)
        if self.instance:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError("Une fiche existe deja pour cette entreprise et cette adresse.")
        data["identity_key"] = key
        if "website" in data:
            data["has_website"] = bool(data["website"])
        if "email" in data and (not self.instance or data["email"] != self.instance.email):
            data["email_source"] = "Saisie manuelle" if data["email"] else ""
            data["email_verified_at"] = timezone.now() if data["email"] else None
            data["enrichment_status"] = "found" if data["email"] else "pending"
        if data.get("status", self.instance.status if self.instance else "new") in CLOSED:
            data["next_followup_at"] = None
        return data

    def update(self, instance, data):
        old_status, old_notes, old_followup = instance.status, instance.notes, instance.next_followup_at
        result = super().update(instance, data)
        changes = []
        if result.status != old_status:
            changes.append(f"Statut : {result.get_status_display()}")
        if result.notes != old_notes:
            changes.append("Notes mises a jour")
        if result.next_followup_at != old_followup:
            changes.append("Date de relance mise a jour")
        if changes:
            ProspectEvent.objects.create(prospect=result, kind="update", message=". ".join(changes))
        return result


class ContactDetailSerializer(ContactSerializer):
    email_logs = LogSerializer(many=True, read_only=True)
    events = EventSerializer(many=True, read_only=True)
    jobs = JobSerializer(many=True, read_only=True)

    class Meta(ContactSerializer.Meta):
        fields = ContactSerializer.Meta.fields + ["email_logs", "events", "jobs"]


class QualificationSerializer(serializers.ModelSerializer):
    prospect = serializers.SerializerMethodField()
    draft = serializers.SerializerMethodField()

    class Meta:
        model = QualificationReview
        fields = ["id", "status", "priority", "reasons", "evidence", "checked_at", "prospect", "draft"]

    def get_prospect(self, obj):
        item = obj.prospect
        return {"id": item.pk, "nom": item.nom, "ville": item.ville, "email": item.email or "", "website": item.website or ""}

    def get_draft(self, obj):
        try:
            draft = obj.prospect.email_draft
        except EmailDraft.DoesNotExist:
            return None
        return {"subject": draft.subject, "body": draft.body, "state": draft.state}


class ContactPagination(PageNumberPagination):
    page_size = 40
    page_size_query_param = "page_size"
    max_page_size = 100


def contacts():
    return Prospect.objects.filter(merged_into=None).select_related("campaign", "qualification").prefetch_related("campaigns").annotate(
        emails_sent_count=Count("email_logs", filter=Q(email_logs__success=True), distinct=True),
        priority_rank=Case(When(priority="high", then=Value(2)), When(priority="normal", then=Value(1)), default=Value(0), output_field=IntegerField()),
    )


class ContactViewSet(viewsets.ModelViewSet):
    permission_classes = [OwnerOnly]
    pagination_class = ContactPagination
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]

    def get_serializer_class(self):
        return ContactSerializer if self.action == "list" else ContactDetailSerializer

    def get_queryset(self):
        qs = contacts()
        params = self.request.query_params
        search = params.get("search", "").strip()
        if search:
            qs = qs.filter(Q(nom__icontains=search) | Q(ville__icontains=search) | Q(email__icontains=search) | Q(notes__icontains=search))
        for field in ["status", "priority", "enrichment_status"]:
            if params.get(field):
                qs = qs.filter(**{field: params[field]})
        if params.get("campaign"):
            if not params["campaign"].isdigit():
                return qs.none()
            qs = qs.filter(campaigns__id=params["campaign"])
        if params.get("has_email") == "true":
            qs = qs.exclude(email=None).exclude(email="")
        elif params.get("has_email") == "false":
            qs = qs.filter(Q(email=None) | Q(email=""))
        if params.get("has_website") in ["true", "false"]:
            qs = qs.filter(has_website=params["has_website"] == "true")
        if params.get("view") == "contactable":
            qs = qs.filter(status="new").exclude(email=None).exclude(email="")
        elif params.get("view") == "due":
            qs = qs.filter(next_followup_at__lte=timezone.now()).exclude(status__in=CLOSED)
        elif params.get("view") == "incomplete":
            qs = qs.filter(Q(email=None) | Q(email=""))
        ordering = params.get("ordering", "-priority_rank,-created_at")
        allowed = {"nom", "ville", "created_at", "next_followup_at", "priority_rank", "status"}
        fields = [f for f in ordering.split(",") if f.lstrip("-") in allowed]
        return qs.order_by(*(fields or ["-created_at"]), "id").distinct()

    def perform_create(self, serializer):
        item = serializer.save()
        ProspectEvent.objects.create(prospect=item, kind="created", message="Fiche ajoutee manuellement.")

    @action(detail=True, methods=["post"])
    def enrich(self, request, pk=None):
        job = enqueue_enrichment(self.get_object())
        return Response(JobSerializer(job).data, status=202)

    @action(detail=True, methods=["get", "put"], url_path="draft")
    def draft(self, request, pk=None):
        prospect = self.get_object()
        review = QualificationReview.objects.filter(prospect=prospect).first()
        if not review:
            return Response({"error": "Cette fiche doit d'abord etre analysee."}, status=409)
        draft, _ = EmailDraft.objects.get_or_create(prospect=prospect)
        if request.method == "PUT":
            if review.status not in ["pending", "approved"]:
                return Response({"error": "Seules les propositions a examiner ou approuvees peuvent etre modifiees."}, status=409)
            serializer = EmailDraftSerializer(draft, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            if "subject" in serializer.validated_data:
                subject = serializer.validated_data["subject"]
                if "\n" in subject or "\r" in subject:
                    return Response({"error": "Le sujet doit tenir sur une seule ligne."}, status=400)
            if draft.state == "sent":
                draft.state = "draft"
                draft.sent_at = None
            draft = serializer.save(state="draft", sent_at=None)
        return Response(EmailDraftSerializer(draft).data)

    @action(detail=True, methods=["post"], url_path="send-email")
    def send_email(self, request, pk=None):
        prospect = self.get_object()
        review = QualificationReview.objects.filter(prospect=prospect).first()
        draft = EmailDraft.objects.filter(prospect=prospect).first()
        if not review or review.status != "approved":
            return Response({"error": "Valide d'abord cette proposition avant tout envoi."}, status=409)
        if request.data.get("confirmed") is not True:
            return Response({"error": "Confirmation explicite requise pour envoyer ce message."}, status=409)
        template = None
        subject, body = request.data.get("subject", ""), request.data.get("body", "")
        if not isinstance(subject, str) or not isinstance(body, str):
            return Response({"error": "L'objet et le message doivent etre du texte."}, status=400)
        if len(subject) > 200 or len(body) > 50000 or "\n" in subject or "\r" in subject:
            return Response({"error": "Objet ou message invalide."}, status=400)
        if request.data.get("template_id"):
            if not str(request.data["template_id"]).isdigit():
                return Response({"error": "Modele invalide."}, status=400)
            template = EmailTemplate.objects.filter(pk=request.data["template_id"]).first()
            if not template:
                return Response({"error": "Modele introuvable."}, status=400)
            if not subject or not body:
                try:
                    subject, body = template.render(prospect)
                except (KeyError, ValueError):
                    return Response({"error": "Le modele contient une variable inconnue."}, status=400)
        if not draft or draft.state != "draft" or draft.subject != subject or draft.body != body:
            return Response({"error": "Enregistre le texte exact comme brouillon avant de confirmer l'envoi."}, status=409)
        try:
            log = send_message(prospect, subject, body, request.headers.get("Idempotency-Key", ""), template,
                               force=request.data.get("force") is True, manual=request.data.get("manual") is True,
                               approval_confirmed=True)
            draft.state = "sent"
            draft.sent_at = timezone.now()
            draft.save(update_fields=["state", "sent_at", "updated_at"])
            return Response(LogSerializer(log).data)
        except MailError as exc:
            return Response({"error": str(exc)}, status=exc.status)


class PersonalCampaignSerializer(serializers.ModelSerializer):
    total_prospects = serializers.ReadOnlyField()
    prospects_with_email = serializers.ReadOnlyField()
    job = serializers.SerializerMethodField()
    rayon_km = serializers.IntegerField(min_value=1, max_value=30)
    class Meta:
        model = Campaign
        fields = ["id", "secteur", "ville", "rayon_km", "repeat_days", "next_search_at", "status", "error_message", "created_at", "total_prospects", "prospects_with_email", "job"]
        read_only_fields = ["next_search_at", "status", "error_message", "created_at"]

    def get_job(self, obj):
        jobs = list(obj.jobs.all())
        return JobSerializer(jobs[0]).data if jobs else None


class CampaignScheduleSerializer(serializers.Serializer):
    repeat_days = serializers.ChoiceField(
        choices=[(0, "Désactivée"), *[(day, f"{day} jours") for day in sorted(REPEAT_INTERVAL_DAYS)]]
    )


class PersonalCampaignViewSet(viewsets.ModelViewSet):
    permission_classes = [OwnerOnly]
    serializer_class = PersonalCampaignSerializer
    queryset = Campaign.objects.prefetch_related("jobs").all()
    http_method_names = ["get", "post", "delete", "head", "options"]

    @action(detail=True, methods=["post"])
    def launch(self, request, pk=None):
        return Response(JobSerializer(enqueue_search(self.get_object())).data, status=202)

    @action(detail=True, methods=["post"])
    def schedule(self, request, pk=None):
        campaign = self.get_object()
        serializer = CampaignScheduleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        repeat_days = serializer.validated_data["repeat_days"]
        active = campaign.jobs.filter(status__in=["queued", "running", "paused"]).exists()
        campaign.repeat_days = repeat_days
        campaign.next_search_at = (
            timezone.now() + timedelta(days=repeat_days)
            if repeat_days in REPEAT_INTERVAL_DAYS and not active
            else None
        )
        campaign.save(update_fields=["repeat_days", "next_search_at"])
        return Response(self.get_serializer(campaign).data)

    def destroy(self, request, *args, **kwargs):
        campaign = self.get_object()
        if campaign.jobs.filter(status="running").exists():
            return Response({"error": "Mets cette recherche en pause avant de la supprimer."}, status=409)
        return super().destroy(request, *args, **kwargs)


class JobViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [OwnerOnly]
    serializer_class = JobSerializer
    queryset = SearchJob.objects.all()[:100]

    def get_queryset(self):
        return SearchJob.objects.all() if self.action != "list" else SearchJob.objects.all()[:100]

    @action(detail=True, methods=["post"])
    def pause(self, request, pk=None):
        job = self.get_object()
        if job.status in ["running", "queued"]:
            job.status = "paused"
            job.stage = "En pause"
            job.save(update_fields=["status", "stage", "updated_at"])
            if job.campaign_id:
                Campaign.objects.filter(pk=job.campaign_id).update(status="paused")
        return Response(JobSerializer(job).data)

    @action(detail=True, methods=["post"])
    def resume(self, request, pk=None):
        job = self.get_object()
        if job.status in ["error", "paused"]:
            job.status = "queued"
            job.stage = "Reprise programmee"
            job.error = ""
            job.attempts = 0
            job.next_run_at = timezone.now()
            job.save(update_fields=["status", "stage", "error", "attempts", "next_run_at", "updated_at"])
            if job.campaign_id:
                Campaign.objects.filter(pk=job.campaign_id).update(status="queued", error_message="")
        return Response(JobSerializer(job).data)


@api_view(["GET"])
@permission_classes([OwnerOnly])
def qualification_queue(request):
    status_filter = request.query_params.get("status", "pending")
    if status_filter not in ["pending", "deferred"]:
        return Response({"error": "Filtre de qualification invalide."}, status=400)
    qs = QualificationReview.objects.filter(status=status_filter, prospect__merged_into=None, prospect__status="new").exclude(
        prospect__email_logs__isnull=False
    ).filter(prospect__last_contacted_at__isnull=True).select_related("prospect").annotate(
        priority_rank=Case(When(priority="high", then=Value(2)), When(priority="medium", then=Value(1)), default=Value(0), output_field=IntegerField())
    ).order_by("-priority_rank", "-checked_at", "id").distinct()
    results = list(qs[:100])
    return Response({"count": qs.count(), "results": QualificationSerializer(results, many=True).data})


@api_view(["POST"])
@permission_classes([OwnerOnly])
def qualification_run(request):
    qs = Prospect.objects.filter(merged_into=None, status="new", qualification__isnull=True, last_contacted_at__isnull=True).exclude(email_logs__isnull=False).order_by("pk")
    prospects = list(qs[:100])
    queued = sum(enqueue_qualification(item) is not None for item in prospects)
    return Response({"queued": queued, "remaining": max(0, qs.count() - len(prospects))}, status=202)


@api_view(["POST"])
@permission_classes([OwnerOnly])
def qualification_decision(request, pk, decision):
    review = get_object_or_404(QualificationReview.objects.select_related("prospect"), pk=pk)
    allowed = {"approve": "approved", "reject": "rejected", "defer": "deferred", "reopen": "pending"}
    if decision not in allowed:
        return Response({"error": "Decision invalide."}, status=400)
    if decision == "approve" and review.status not in ["pending", "deferred"]:
        return Response({"error": "Cette proposition n'est plus en attente de validation."}, status=409)
    if decision == "reopen" and review.status != "deferred":
        return Response({"error": "Seule une proposition reportee peut etre reouverte."}, status=409)
    review.status = allowed[decision]
    review.save(update_fields=["status"])
    ProspectEvent.objects.create(prospect=review.prospect, kind="qualification", message=f"Qualification : {review.get_status_display()}.")
    return Response(QualificationSerializer(review).data)


@api_view(["GET"])
@permission_classes([OwnerOnly])
def today(request):
    qs = contacts()
    due = qs.filter(next_followup_at__lte=timezone.now()).exclude(status__in=CLOSED)
    fresh = qs.filter(status="new").exclude(email=None).exclude(email="")
    return Response({
        "total": qs.count(), "due_count": due.count(), "contactable_count": fresh.count(),
        "incomplete_count": qs.filter(Q(email=None) | Q(email="")).count(),
        "won_count": qs.filter(status="won").count(),
        "due": ContactSerializer(due.order_by("next_followup_at")[:10], many=True).data,
        "contactable": ContactSerializer(fresh.order_by("-priority_rank", "-created_at")[:10], many=True).data,
        "pipeline": list(Prospect.objects.filter(merged_into=None).values("status").annotate(count=Count("id"))),
        "jobs": JobSerializer(SearchJob.objects.filter(status__in=["queued", "running", "paused"])[:10], many=True).data,
    })


@api_view(["GET", "POST"])
@permission_classes([OwnerOnly])
def email_settings(request):
    if request.method == "POST":
        values = {}
        if "brevo_api_key" in request.data:
            key = request.data["brevo_api_key"]
            if not isinstance(key, str) or (key and not 20 <= len(key.strip()) <= 1000):
                return Response({"error": "Cle API invalide."}, status=400)
            values["brevo_api_key"] = key.strip()
        if "sender_email" in request.data:
            serializer = serializers.EmailField()
            values["sender_email"] = serializer.run_validation(request.data["sender_email"])
            values["sender_name"] = serializers.CharField(max_length=100, allow_blank=True).run_validation(request.data.get("sender_name", ""))
        try:
            save_private_settings(**values)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=400)
    name, sender = parseaddr(sender_address())
    return Response({"brevo_configured": bool(brevo_key()), "sender": sender, "sender_name": name, "smtp_configured": bool(settings.EMAIL_HOST_USER)})


@api_view(["POST"])
@permission_classes([OwnerOnly])
def delivery_sync(request):
    try:
        return Response(sync_delivery())
    except Exception:
        return Response({"error": "Synchronisation Brevo impossible. Verifie la cle et la connexion."}, status=502)


@api_view(["GET", "POST"])
@permission_classes([OwnerOnly])
def backups(request):
    from .backups import create_backup, list_backups
    if not settings.DESKTOP_MODE:
        return Response({"error": "Reserve a l'application locale."}, status=403)
    if request.method == "POST":
        return Response(create_backup(), status=201)
    return Response(list_backups())


@api_view(["POST"])
@permission_classes([OwnerOnly])
def restore(request):
    from .backups import restore_backup
    if not settings.DESKTOP_MODE or request.data.get("confirmation") != "RESTAURER":
        return Response({"error": "Confirmation de restauration requise."}, status=400)
    try:
        return Response(restore_backup(request.data.get("name")))
    except ValueError as exc:
        return Response({"error": str(exc)}, status=400)
