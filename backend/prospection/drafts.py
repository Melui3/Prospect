"""Evidence-bound conditional writing and append-only email versions. No network."""
import copy
import hashlib
import json
from datetime import datetime
from django.conf import settings
from django.db import models, transaction
from django.db.models import F
from django.utils import timezone
from .models import EmailDraft, EmailDraftVersion, Prospect, QualificationReview
from .qualification import prospect_is_eligible
from .selection import select_opportunities

PORTFOLIO = "https://nathaniel-dev.fr/"
GENERATOR = "conditional-v1-2026-11-20"

class DraftError(ValueError):
    pass

def context_for(prospect):
    return {k:getattr(prospect,k) or "" for k in ("nom","ville","email","website")}

def payload_for(draft, context):
    return {"subject":draft.subject,"body":draft.body,"template_id":draft.template_id,
            "context":context,"evidence":draft.evidence_snapshot}

def digest(payload):
    return hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def lock_prospect(pk):
    # Acquire a SQLite write lock BEFORE reads; row locks on other supported databases.
    Prospect.objects.filter(pk=pk).update(priority=F("priority"))
    return Prospect.objects.select_for_update().get(pk=pk)

def snapshot(draft, number, context, origin=None):
    return EmailDraftVersion.objects.create(draft=draft,number=number,subject=draft.subject,
        body=draft.body,recipient=context["email"],context=context,
        evidence=copy.deepcopy(draft.evidence_snapshot),origin=origin or draft.origin,
        generator=GENERATOR if draft.origin=="conditional" else "",
        template_id_snapshot=draft.template_id,fingerprint=digest(payload_for(draft,context)))

@transaction.atomic
def persist(draft, *args, **kwargs):
    from .run_limits import guard_current
    guard_current()
    prospect=lock_prospect(draft.prospect_id)
    previous=EmailDraft.objects.select_for_update().filter(pk=draft.pk).first() if draft.pk else None
    if hasattr(draft,"expected_revision") and draft.expected_revision != (previous.revision if previous else 0):
        raise DraftError("Le brouillon a changé dans une autre fenêtre. Actualise avant de continuer.")
    fields=kwargs.get("update_fields")
    if previous and fields is not None:
        # Partial state/approval writes must not restore stale text from another editor.
        for field in draft._meta.concrete_fields:
            if field.name not in fields and field.attname not in fields and not field.primary_key:
                setattr(draft,field.attname,getattr(previous,field.attname))
    context=context_for(prospect)
    current=previous.versions.filter(number=previous.revision).first() if previous else None
    changed=current is None or current.fingerprint != digest(payload_for(draft,context))
    changed=changed or getattr(draft,"force_new_version",False)
    if previous and previous.sending_revision is not None and changed:
        raise DraftError("Un envoi est en cours pour cette version. Attends son résultat avant de modifier le brouillon.")
    if previous:
        draft.revision=previous.revision
    if changed:
        if previous and draft.origin == "conditional" and not getattr(draft, "force_new_version", False):
            draft.origin = "manual"
        draft.revision+=1
        draft.approved_revision=None
        draft.approved_at=None
        if previous:
            QualificationReview.objects.filter(prospect_id=prospect.pk,status="approved").update(status="pending")
        if fields is not None:
            kwargs["update_fields"]=set(fields)|{"revision","approved_revision","approved_at","origin"}
    models.Model.save(draft,*args,**kwargs)
    if changed:
        snapshot(draft,draft.revision,context)
    guard_current()
    draft.force_new_version=False
    if hasattr(draft, "expected_revision"):
        draft.expected_revision=draft.revision

def selected_info(prospect_id, *, explicit_approval=False):
    reviews=list(QualificationReview.objects.select_related("prospect").all())
    if explicit_approval:
        for review in reviews:
            if review.prospect_id==prospect_id and review.status in {"approved","deferred"}:
                review.status="pending"
    chosen, info, _=select_opportunities(reviews)
    review=next((r for r in chosen if r.prospect_id==prospect_id),None)
    if review is None:
        raise DraftError("Cette fiche ne fait pas partie des cinq opportunités justifiées actuelles. Vérifie les preuves, le contact et les décisions.")
    return review, info[review.pk]

def clean(value):
    return " ".join(str(value or "").split())

def bound_info(review, info):
    result=copy.deepcopy(info)
    result["records"]=[copy.deepcopy(row) for row in review.evidence if not row.get("historical") and
        any(row.get("kind")==ref["kind"] and row.get("url")==ref["url"] and
            row.get("observed_at")==ref["observed_at"] and row.get("detail")==ref["detail"]
            for ref in info["evidence"])]
    return result

def compose(review, info):
    p=review.prospect
    proof=info["evidence"][0]
    date=datetime.fromisoformat(proof["observed_at"].replace("Z","+00:00")).strftime("%d/%m/%Y")
    name,city,url=clean(p.nom),clean(p.ville),clean(proof["url"])
    detail=clean(proof["detail"])[:400]
    if proof["kind"]=="third_party_menu":
        subject=f"Une page dédiée à votre carte — {name}"
        observation=f"En consultant {url} le {date}, la vérification a relevé une carte publiée chez ce tiers pour {name}, à {city}. Constat consigné : « {detail} »"
        value="Une page dédiée pourrait réunir votre carte, vos horaires et vos coordonnées sous une adresse que vous maîtrisez. Chez NateOS, je propose des landing pages adaptées aux téléphones."
        limit="Cette publication ne permet pas de conclure à l’absence d’un site officiel ; l’intérêt d’une telle page reste à confirmer avec vous."
        cta="Si cette piste rejoint vos priorités, souhaitez-vous une proposition de périmètre par email, puis un devis si elle vous convient ?"
    elif proof["kind"]=="dispersed_information":
        subject=f"Vos informations pratiques au même endroit — {name}"
        observation=f"Le {date}, la vérification documentée pour {name}, à {city}, a relevé des informations pratiques sur plusieurs sources tierces, dont {url}. Constat consigné : « {detail} »"
        value="Un site vitrine pourrait réunir les informations que vous souhaitez communiquer à vos clients et simplifier leur mise à jour. Je conçois ce type de site chez NateOS, avec une présentation adaptée aux téléphones."
        limit="La dispersion observée ne prouve pas que vos clients rencontrent des difficultés, ni que vous souhaitez un nouveau site."
        cta="Est-ce un sujet que vous envisagez ? Si oui, je peux vous proposer par email un périmètre précis à chiffrer."
    elif proof["kind"]=="missing_viewport":
        subject=f"Une vérification mobile ciblée — {name}"
        observation=f"Lors de la consultation du {date}, la page {url} associée à {name}, à {city}, ne déclarait pas de balise viewport dans son HTML."
        value="Cette balise aide le navigateur à gérer la largeur d’affichage. Dans le cadre de mes prestations de sites vitrines chez NateOS, je peux vérifier l’affichage sur téléphone et proposer un ajustement si un problème est confirmé."
        limit="Son absence ne suffit pas à démontrer un défaut visuel : l’affichage mobile n’a pas été testé."
        cta="Souhaitez-vous que nous précisions ce contrôle par email ? Un devis pourrait être établi pour les ajustements réellement nécessaires."
    else:
        raise DraftError("Aucun modèle conditionnel justifié pour cette observation.")
    body=f"Bonjour,\n\n{observation}\n\n{value}\n\n{limit}\n\nJe suis Nathaniel, développeur web indépendant chez NateOS. Voici mon portfolio : {PORTFOLIO}\n\n{cta}\n\nSi vous ne souhaitez pas être recontacté, vous pouvez simplement me l’indiquer en réponse.\n\nCordialement,\nNathaniel\nNateOS"
    return subject[:200],body

@transaction.atomic
def generate(prospect_id, expected_revision):
    prospect=lock_prospect(prospect_id)
    review,info=selected_info(prospect_id)
    draft=EmailDraft.objects.filter(prospect=prospect).first()
    if expected_revision != (draft.revision if draft else 0):
        raise DraftError("Le brouillon a changé. Actualise avant de générer une version.")
    subject,body=compose(review,info)
    draft=draft or EmailDraft(prospect=prospect)
    draft.subject=subject;draft.body=body;draft.template=None
    draft.origin="conditional";draft.evidence_snapshot=bound_info(review,info)
    draft.state="draft";draft.sent_at=None
    draft.expected_revision=expected_revision;draft.force_new_version=True
    draft.save()
    return draft

def prepare_selected_missing(prospect_ids=None):
    reviews=list(QualificationReview.objects.select_related("prospect").all())
    chosen,_,_=select_opportunities(reviews)
    result={"created":0,"preserved":0,"blocked":[]}
    for review in chosen:
        if prospect_ids is not None and review.prospect_id not in prospect_ids:
            continue
        from .run_limits import guard_current
        guard_current()
        if EmailDraft.objects.filter(prospect_id=review.prospect_id).exists():
            result["preserved"]+=1
            continue
        try:
            generate(review.prospect_id,0)
            result["created"]+=1
        except DraftError as exc:
            result["blocked"].append({"review":review.pk,"reason":str(exc)})
    return result

@transaction.atomic
def approve(prospect_id, revision):
    prospect=lock_prospect(prospect_id)
    review,info=selected_info(prospect_id,explicit_approval=True)
    draft=EmailDraft.objects.select_for_update().filter(prospect=prospect,state="draft").first()
    if not draft or type(revision) is not int or revision!=draft.revision or not draft.subject.strip() or not draft.body.strip():
        raise DraftError("Relis et enregistre la version actuelle avant de l’approuver.")
    if draft.sending_revision is not None:
        raise DraftError("Un envoi est en cours.")
    version=draft.versions.get(number=revision)
    if version.fingerprint!=digest(payload_for(draft,context_for(prospect))):
        raise DraftError("Le contenu ou le destinataire a changé. Enregistre une nouvelle version.")
    if draft.evidence_snapshot.get("records")!=bound_info(review,info)["records"]:
        raise DraftError("Les preuves ont changé depuis la rédaction. Génère une nouvelle version justifiée.")
    draft.approved_revision=revision;draft.approved_at=timezone.now()
    models.Model.save(draft,update_fields=["approved_revision","approved_at"])
    EmailDraftVersion.objects.filter(pk=version.pk).update(approved_at=draft.approved_at)
    QualificationReview.objects.filter(pk=review.pk).update(status="approved")
    return draft

def assert_approved(draft, prospect, subject, body, revision):
    if type(revision) is not int or draft.revision!=revision or draft.approved_revision!=revision:
        raise DraftError("Cette version exacte du brouillon doit être approuvée avant tout envoi.")
    version=draft.versions.filter(number=revision).first()
    if not version or draft.subject!=subject or draft.body!=body or version.fingerprint!=digest(payload_for(draft,context_for(prospect))):
        raise DraftError("Le texte, le destinataire ou les preuves diffèrent de la version approuvée.")
    if not QualificationReview.objects.filter(prospect=prospect,status="approved").exists():
        raise DraftError("La décision humaine actuelle n’autorise pas cet envoi.")
    from .selection import _valid_evidence, _duplicate_groups
    from .models import EmailLog
    prospects=list(Prospect.objects.all())
    groups=_duplicate_groups(prospects)
    aliases=[p for p in prospects if p.pk != prospect.pk and groups[p.pk] == groups[prospect.pk]]
    alias_ids=[p.pk for p in aliases]
    if any(p.status != "new" or p.last_contacted_at for p in aliases) or (
        QualificationReview.objects.filter(prospect_id__in=alias_ids,
            status__in=["approved","rejected","deferred","excluded"]).exists()
        or EmailLog.objects.filter(prospect_id__in=alias_ids).exists()):
        raise DraftError("Une décision ou un contact sur un doublon impose une nouvelle revue.")
    review=QualificationReview.objects.get(prospect=prospect)
    valid=[row for row,_ in _valid_evidence(review,timezone.now(),
           settings.SELECTION_EVIDENCE_MAX_AGE_DAYS)]
    if not draft.evidence_snapshot.get("records") or any(
            row not in valid for row in draft.evidence_snapshot["records"]):
        raise DraftError("Les preuves approuvées ont changé ou sont périmées. Nouvelle revue requise.")
