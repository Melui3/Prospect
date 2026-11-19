from datetime import timedelta
from email.utils import make_msgid, parseaddr

import requests
from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import EmailDraft, EmailLog, ProspectEvent, QualificationReview
from .private_config import brevo_key, sender_address


class MailError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def mark_contacted(prospect):
    prospect.last_contacted_at = timezone.now()
    if prospect.status in ["new", "ignored"]:
        prospect.status = "contacted"
    if (not prospect.next_followup_at or prospect.next_followup_at <= timezone.now()) and prospect.status not in ["won", "lost", "do_not_contact"]:
        prospect.next_followup_at = timezone.now() + timedelta(days=7)
    prospect.save(update_fields=["last_contacted_at", "status", "next_followup_at"])


def send_message(prospect, subject, body, request_key, template=None, force=False, manual=False, approval_confirmed=False):
    from .opposition import is_opposed
    if prospect.status == "do_not_contact" or is_opposed(prospect.nom, prospect.ville, prospect.email, prospect.website):
        raise MailError("Cette fiche est marquee Ne plus contacter.")
    if not prospect.email:
        raise MailError("Prospect sans email.")
    if not isinstance(subject, str) or not isinstance(body, str) or not subject.strip() or not body.strip() or len(subject) > 200 or "\n" in subject or "\r" in subject:
        raise MailError("Renseigne un sujet valide et un message.")
    if len(body) > 50000 or not isinstance(request_key, str) or not request_key or len(request_key) > 80:
        raise MailError("Message ou identifiant d'envoi invalide.")
    with transaction.atomic():
        existing = EmailLog.objects.filter(request_key=request_key).first()
        if existing:
            if existing.prospect_id != prospect.pk or existing.subject != subject or existing.body != body or existing.recipient != prospect.email or (existing.source == "manual") != manual:
                raise MailError("Cet identifiant appartient deja a un autre message.", 409)
            if not existing.success:
                raise MailError("Cet envoi a deja ete tente. Verifie son historique avant de recommencer.", 409)
            return existing
        if approval_confirmed is not True:
            raise MailError("Confirmation explicite requise avant l'envoi.", 409)
        if not QualificationReview.objects.filter(prospect=prospect, status="approved").exists():
            raise MailError("Une proposition approuvee est requise avant l'envoi.", 409)
        draft = EmailDraft.objects.filter(prospect=prospect, state="draft", subject=subject, body=body).first()
        if not draft:
            raise MailError("Le texte exact doit etre enregistre comme brouillon avant l'envoi.", 409)
        same_message = EmailLog.objects.filter(prospect=prospect, recipient=prospect.email, subject=subject, body=body, sent_at__gte=timezone.now() - timedelta(days=1))
        if same_message.filter(delivery_status__in=["uncertain", "submitting"]).exists():
            raise MailError("Un envoi de ce message est en cours ou incertain. Verifie Brevo avant de retenter.", 409)
        if not force and same_message.filter(success=True).exists():
            raise MailError("Un message identique a deja ete envoye a ce contact aujourd'hui.", 409)
        log = EmailLog.objects.create(
            prospect=prospect, template=template, recipient=prospect.email,
            subject=subject, body=body, request_key=request_key,
            success=False, delivery_status="submitting", source="manual" if manual else "smtp",
        )
    try:
        key = "" if manual else brevo_key()
        if manual:
            log.delivery_status = "manual"
        elif key:
            name, sender = parseaddr(sender_address())
            if not sender:
                raise MailError("L'expediteur n'est pas configure.")
            response = requests.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={"api-key": key, "Content-Type": "application/json"},
                json={"sender": {"email": sender, "name": name or sender}, "to": [{"email": prospect.email}],
                      "subject": subject, "textContent": body, "tags": [f"prospect-{log.pk}"]}, timeout=20,
            )
            if response.status_code >= 400:
                raise MailError(f"Brevo refuse l'envoi (HTTP {response.status_code}). Verifie l'expediteur et la cle API.")
            log.message_id = response.json()["messageId"]
            log.source = "brevo"
            log.delivery_status = "sent"
        else:
            log.message_id = make_msgid()
            sent = EmailMessage(subject, body, sender_address(), [prospect.email], headers={"Message-ID": log.message_id}).send(fail_silently=False)
            if sent != 1:
                raise MailError("Le serveur email n'a pas accepte le message.")
            log.delivery_status = "sent"
        log.success = True
        log.delivery_updated_at = timezone.now()
        log.save()
        draft.state = "sent"
        draft.sent_at = timezone.now()
        draft.save(update_fields=["state", "sent_at", "updated_at"])
        mark_contacted(prospect)
        return log
    except Exception as exc:
        log.delivery_status = "uncertain" if isinstance(exc, (requests.Timeout, requests.ConnectionError, TimeoutError)) else "error"
        log.error_message = str(exc)[:1000]
        log.save()
        raise MailError("Envoi non confirme. Consulte l'historique avant de renvoyer." if log.delivery_status == "uncertain" else str(exc), 502) from exc


def sync_delivery():
    key = brevo_key()
    if not key:
        return {"configured": False, "updated": 0}
    logs = {log.message_id: log for log in EmailLog.objects.exclude(message_id="").filter(sent_at__gte=timezone.now() - timedelta(days=30))}
    if not logs:
        return {"configured": True, "updated": 0}
    updated = 0
    for offset in range(0, 5000, 500):
        response = requests.get("https://api.brevo.com/v3/smtp/statistics/events", headers={"api-key": key}, params={"days": 30, "limit": 500, "offset": offset, "sort": "asc"}, timeout=15)
        response.raise_for_status()
        events = response.json().get("events", [])
        for event in events:
            log = logs.get(event.get("messageId"))
            if not log:
                continue
            event_type = event.get("event", "")
            if event_type not in ["delivered", "opened", "clicks", "soft_bounce", "hard_bounce", "blocked", "error", "deferred", "unsubscribed"]:
                continue
            date = parse_datetime(event.get("date", "")) or timezone.now()
            if timezone.is_naive(date):
                date = timezone.make_aware(date)
            if log.delivery_updated_at and date <= log.delivery_updated_at:
                continue
            log.delivery_status = "delivered" if event_type in ["clicks", "opened"] else event_type
            log.delivery_updated_at = date
            log.error_message = event.get("reason", "")[:1000]
            log.save(update_fields=["delivery_status", "delivery_updated_at", "error_message"])
            if event_type == "unsubscribed":
                log.prospect.status = "do_not_contact"
                log.prospect.next_followup_at = None
                log.prospect.save(update_fields=["status", "next_followup_at"])
                ProspectEvent.objects.create(prospect=log.prospect, kind="status", message="Desinscription signalee par Brevo.")
            updated += 1
        if len(events) < 500:
            break
    return {"configured": True, "updated": updated}
