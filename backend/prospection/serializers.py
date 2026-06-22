from rest_framework import serializers
from .models import Campaign, Prospect, EmailTemplate, EmailLog


class EmailLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailLog
        fields = ["id", "subject", "body", "sent_at", "success", "error_message"]


class ProspectSerializer(serializers.ModelSerializer):
    email_logs = EmailLogSerializer(many=True, read_only=True)
    emails_sent = serializers.SerializerMethodField()
    campaign_secteur = serializers.CharField(source="campaign.secteur", read_only=True)

    class Meta:
        model = Prospect
        fields = [
            "id",
            "campaign",
            "campaign_secteur",
            "nom",
            "adresse",
            "ville",
            "telephone",
            "email",
            "website",
            "has_website",
            "status",
            "created_at",
            "email_logs",
            "emails_sent",
        ]
        read_only_fields = ["campaign", "created_at"]

    def get_emails_sent(self, obj):
        annotated_count = getattr(obj, "emails_sent_count", None)
        if annotated_count is not None:
            return annotated_count

        prefetched_logs = getattr(obj, "_prefetched_objects_cache", {}).get("email_logs")
        if prefetched_logs is not None:
            return sum(1 for log in prefetched_logs if log.success)

        return obj.email_logs.filter(success=True).count()


class ProspectListSerializer(serializers.ModelSerializer):
    emails_sent = serializers.SerializerMethodField()
    campaign_secteur = serializers.CharField(source="campaign.secteur", read_only=True)

    class Meta:
        model = Prospect
        fields = [
            "id",
            "campaign",
            "campaign_secteur",
            "nom",
            "adresse",
            "ville",
            "telephone",
            "email",
            "website",
            "has_website",
            "status",
            "created_at",
            "emails_sent",
        ]
        read_only_fields = ["campaign", "created_at"]

    def get_emails_sent(self, obj):
        return getattr(obj, "emails_sent_count", 0)


class CampaignSerializer(serializers.ModelSerializer):
    total_prospects = serializers.ReadOnlyField()
    prospects_with_email = serializers.ReadOnlyField()

    class Meta:
        model = Campaign
        fields = [
            "id",
            "secteur",
            "ville",
            "rayon_km",
            "status",
            "error_message",
            "created_at",
            "launched_at",
            "total_prospects",
            "prospects_with_email",
        ]
        read_only_fields = ["status", "error_message", "created_at", "launched_at"]


class EmailTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailTemplate
        fields = ["id", "name", "subject", "body", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]
