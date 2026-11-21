import { useEffect, useRef, useState } from "react";
import { X, Save, Search, ExternalLink, Send, Mail, RefreshCw, Pause, Play } from "lucide-react";
import { getTemplates } from "../api/client";
import { renderMessageTemplate } from "../api/personal-utils";
import { controlJob, enrichContact, errorMessage, getContact, sendMessage, saveContact, getEmailDraft, saveEmailDraft, validateEmailDraft } from "./api";
import { Empty, IconButton, Loading, Notice, Status, externalUrl, formatDate, statuses } from "./common";

const localDate = (value) => {
  if (!value) return "";
  const date = new Date(value);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
};
const formValues = (item) => ({ nom: item.nom, ville: item.ville, adresse: item.adresse || "", email: item.email || "", telephone: item.telephone || "", website: item.website || "", status: item.status, priority: item.priority, notes: item.notes, next_followup_at: localDate(item.next_followup_at) });
const deliveryLabels = { sent: "Accepte par le service d'envoi", delivered: "Delivre", submitting: "Envoi en cours", uncertain: "Envoi incertain : verifier les logs avant de retenter", error: "Echec", hard_bounce: "Adresse rejetee", soft_bounce: "Rejet temporaire", blocked: "Bloque", deferred: "Differe", unsubscribed: "Desinscrit", manual: "Envoi confirme manuellement" };

export default function ContactDrawer({ id, initialTab = "fiche", onClose, onChanged }) {
  const [item, setItem] = useState(null);
  const [form, setForm] = useState(null);
  const [tab, setTab] = useState(initialTab === "email" ? "email" : "fiche");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [busy, setBusy] = useState(false);
  const [templates, setTemplates] = useState([]);
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [templateId, setTemplateId] = useState("");
  const [dirty, setDirty] = useState(false);
  const [draftReady, setDraftReady] = useState(false);
  const [draftSaving, setDraftSaving] = useState(false);
  const [savedSignature, setSavedSignature] = useState("");
  const [gmailOpened, setGmailOpened] = useState(false);
  const [draftVersion, setDraftVersion] = useState({ revision: 0, approved_revision: null });
  const [browserDraft, setBrowserDraft] = useState(null);
  const attempt = useRef(null);
  const draftKey = `prospect_mail_draft_${id}`;
  const load = (replaceForm = false) => getContact(id, true).then((value) => { setItem(value); if (replaceForm) { setForm(formValues(value)); setDirty(false); } }).catch((e) => setError(errorMessage(e)));
  useEffect(() => {
    load(true); getTemplates().then(setTemplates).catch((e) => setError(errorMessage(e)));
    setTab(initialTab === "email" ? "email" : "fiche");
    let localDraft = {};
    try { localDraft = JSON.parse(localStorage.getItem(draftKey)) || {}; } catch { /* Ignore an invalid browser draft. */ }
    setDraftReady(false); setSavedSignature("");
    getEmailDraft(id).then((draft) => {
      setDraftVersion(draft);
      setBrowserDraft((localDraft.subject || localDraft.body) && (localDraft.subject !== draft.subject || localDraft.body !== draft.body) ? localDraft : null);
      const next = { subject: draft.subject || "", body: draft.body || "", templateId: draft.template || "" };
      setSubject(next.subject || ""); setBody(next.body || ""); setTemplateId(next.templateId || "");
      setSavedSignature(JSON.stringify({ subject: draft.subject || "", body: draft.body || "", template: draft.template || null }));
      setDraftReady(true);
    }).catch((err) => { setSubject(localDraft.subject || ""); setBody(localDraft.body || ""); setTemplateId(localDraft.templateId || ""); setDraftReady(false); if (err.response?.status !== 409) setError(errorMessage(err)); });
    attempt.current = null;
  }, [id, initialTab]);
  useEffect(() => { if (!draftReady) return; try { localStorage.setItem(draftKey, JSON.stringify({ subject, body, templateId })); } catch { /* Storage may be full or disabled. */ } }, [id, subject, body, templateId, draftReady]);
  const currentSignature = JSON.stringify({ subject, body, template: templateId || null });
  useEffect(() => {
    if (!draftReady || !item || !subject.trim() || !body.trim() || currentSignature === savedSignature) return undefined;
    setDraftSaving(true);
    const timer = setTimeout(() => saveEmailDraft(id, { subject, body, template: templateId || null, expected_revision: draftVersion.revision })
      .then((saved) => { setDraftVersion(saved); setSavedSignature(currentSignature); setError(""); setGmailOpened(false); return load(); })
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setDraftSaving(false)), 700);
    return () => clearTimeout(timer);
  }, [draftReady, item, id, subject, body, templateId, currentSignature, savedSignature]);
  const close = () => { if (!dirty || window.confirm("Fermer sans enregistrer les changements de la fiche ?")) onClose(); };
  useEffect(() => { const keydown = (e) => { if (e.key === "Escape") close(); }; document.addEventListener("keydown", keydown); const old = document.body.style.overflow; document.body.style.overflow = "hidden"; return () => { document.removeEventListener("keydown", keydown); document.body.style.overflow = old; }; }, [dirty]);
  useEffect(() => {
    if (!item?.jobs.some((job) => ["queued", "running"].includes(job.status))) return;
    const timer = setInterval(() => { load(!dirty); onChanged(); }, 3000);
    return () => clearInterval(timer);
  }, [item?.jobs, dirty]);
  const update = (key, value) => { setForm((prev) => ({ ...prev, [key]: value })); setDirty(true); setSuccess(""); };
  const save = async (e) => {
    e.preventDefault(); setBusy(true); setError("");
    const original = formValues(item);
    const changes = Object.fromEntries(Object.entries(form).filter(([key, value]) => value !== original[key]));
    if ("email" in changes) changes.email ||= null;
    if ("website" in changes) changes.website ||= null;
    if ("next_followup_at" in changes) changes.next_followup_at = changes.next_followup_at ? new Date(changes.next_followup_at).toISOString() : null;
    try { await saveContact(id, changes); await load(true); onChanged(); setSuccess("Fiche enregistree."); } catch (err) { setError(errorMessage(err)); } finally { setBusy(false); }
  };
  const enrich = async () => {
    setBusy(true); setError("");
    try { await enrichContact(id); await load(); setSuccess("Recherche d'email ajoutee a la file."); } catch (err) { setError(errorMessage(err)); } finally { setBusy(false); }
  };
  const chooseTemplate = (value) => {
    const template = templates.find((t) => String(t.id) === value);
    if (!template) { setTemplateId(""); return; }
    if ((body || subject) && !window.confirm("Remplacer le brouillon par ce modele ?")) return;
    const variables = { nom: item.nom, nom_entreprise: item.nom, ville: item.ville, secteur: item.campaign_secteur === "Manuel" ? "" : item.campaign_secteur, website: item.website || "", site: item.website || "", social: "", social_platform: "" };
    try {
      const nextSubject = renderMessageTemplate(template.subject, variables);
      const nextBody = renderMessageTemplate(template.body, variables);
      setTemplateId(value); setSubject(nextSubject); setBody(nextBody); setGmailOpened(false); attempt.current = null; setError("");
    } catch (err) { setError(err.message); }
  };
  const composeChange = (setter, value) => { setter(value); attempt.current = null; setGmailOpened(false); setSuccess(""); };
  const send = async (manual = false, force = false) => {
    if (item.qualification_status !== "approved") { setError("Approuve d'abord la proposition dans Qualification."); return; }
    if (currentSignature !== savedSignature) { setError("Attends l'enregistrement du brouillon avant de confirmer."); return; }
    const confirmation = manual
      ? `Confirmer que tu as envoye depuis Gmail le message ci-dessous a ${item.email} ?\n\nObjet : ${subject}\n\n${body}`
      : `Envoyer a ${item.email} le message ci-dessous ?\n\nObjet : ${subject}\n\n${body}`;
    if (!window.confirm(confirmation)) return;
    setBusy(true); setError(""); setSuccess("");
    const signature = JSON.stringify({ subject, body, manual, force, revision: draftVersion.revision });
    if (attempt.current?.signature !== signature) attempt.current = { signature, key: crypto.randomUUID() };
    try {
      await sendMessage(id, { subject, body, template_id: templateId || undefined, manual, force, confirmed: true, revision: draftVersion.revision }, attempt.current.key);
      await load(true); onChanged(); setSuccess(manual ? "Envoi note dans l'historique." : "Message accepte par le service d'envoi. La livraison apparaitra dans l'historique.");
      setGmailOpened(false);
    } catch (err) {
      setError(errorMessage(err));
      if (err.response?.status === 409 && !manual && String(err.response.data?.error).includes("identique") && window.confirm("Un message identique a deja ete envoye aujourd'hui. Confirmer un nouvel envoi ?")) { setBusy(false); await send(false, true); return; }
    } finally { setBusy(false); }
  };
  const gmail = async () => {
    setBusy(true); setError("");
    try {
      await validateEmailDraft(id, { subject, body, revision: draftVersion.revision });
    const url = new URL("https://mail.google.com/mail/u/0/");
    url.search = new URLSearchParams({ view: "cm", fs: "1", to: item.email, su: subject, body }).toString();
    window.open(url.href, "_blank", "noopener,noreferrer"); setGmailOpened(true);
    } catch (err) { setError(errorMessage(err)); }
    finally { setBusy(false); }
  };
  const timeline = item ? [...item.events.map((event) => ({ ...event, type: "event", date: event.created_at })), ...item.email_logs.map((log) => ({ ...log, type: "mail", date: log.sent_at }))].sort((a, b) => new Date(b.date) - new Date(a.date)) : [];
  const mailDisabled = !draftVersion.revision || draftVersion.approved_revision !== draftVersion.revision || busy || dirty || draftSaving || !draftReady || currentSignature !== savedSignature || !item?.email || item.status === "do_not_contact" || item.qualification_status !== "approved" || !subject.trim() || !body.trim();
  return <div className="p-overlay" onMouseDown={(e) => { if (e.target === e.currentTarget) close(); }}><aside className="p-drawer" role="dialog" aria-modal="true" aria-label={item ? `Fiche ${item.nom}` : "Fiche prospect"}><header className="p-drawer-head"><h2>{item?.nom || "Fiche prospect"}</h2><IconButton icon={X} label="Fermer" onClick={close} /></header><Notice>{error}</Notice><Notice kind="success">{success}</Notice>{!item || !form ? <Loading /> : <>
    <div className="p-tabs">{[["fiche", "Fiche"], ["email", "Email"], ["history", `Historique (${timeline.length})`]].map(([key, label]) => <button key={key} className={tab === key ? "active" : ""} onClick={() => setTab(key)}>{label}</button>)}</div>
    {tab === "fiche" && <form onSubmit={save} className="p-section"><div className="p-form-grid"><label className="p-full">Entreprise<input value={form.nom} onChange={(e) => update("nom", e.target.value)} required maxLength={255} /></label><label>Ville<input value={form.ville} onChange={(e) => update("ville", e.target.value)} required maxLength={100} /></label><label>Telephone<input value={form.telephone} onChange={(e) => update("telephone", e.target.value)} maxLength={30} /></label><label className="p-full">Adresse<input value={form.adresse} onChange={(e) => update("adresse", e.target.value)} /></label><label className="p-full">Email<input type="email" value={form.email} onChange={(e) => update("email", e.target.value)} /></label><label className="p-full">Site internet<input type="url" value={form.website} onChange={(e) => update("website", e.target.value)} /></label><label>Statut<select value={form.status} onChange={(e) => update("status", e.target.value)}>{statuses.map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label><label>Priorite<select value={form.priority} onChange={(e) => update("priority", e.target.value)}><option value="low">Basse</option><option value="normal">Normale</option><option value="high">Haute</option></select></label><label className="p-full">Prochaine relance<input type="datetime-local" value={form.next_followup_at} onChange={(e) => update("next_followup_at", e.target.value)} disabled={["won", "lost", "ignored", "do_not_contact"].includes(form.status)} /></label><label className="p-full">Notes<textarea rows={5} value={form.notes} onChange={(e) => update("notes", e.target.value)} /></label></div><div className="p-actions p-form-footer"><button className="p-button primary" disabled={busy || !dirty}><Save size={16} /> Enregistrer</button><button type="button" className="p-button" disabled={busy || dirty || item.jobs.some((j) => ["queued", "running", "paused"].includes(j.status))} onClick={enrich}><Search size={16} /> Rechercher un email</button>{externalUrl(item.website) && <a className="p-icon" href={externalUrl(item.website)} target="_blank" rel="noreferrer" title="Ouvrir le site"><ExternalLink size={17} /></a>}</div>
      <div className="p-section p-metadata"><p>Source email : {/^https?:\/\//.test(item.email_source) ? <a className="p-link" href={externalUrl(item.email_source)} target="_blank" rel="noreferrer">{item.email_source}</a> : item.email_source || "-"}</p><p>Derniere recherche : {formatDate(item.enriched_at)} / {({ pending: "En attente", found: "Email trouve", not_found: "Introuvable", error: "Erreur, a retenter" })[item.enrichment_status]}</p><p>Dernier contact : {formatDate(item.last_contacted_at)}</p><p>Recherches : {item.campaign_names.map((c) => c.label).join(", ") || "Ajout manuel"}</p></div>
      {item.jobs.slice(0, 3).map((job) => <div className="p-job" key={job.id}><div className="p-job-content"><span>{job.stage || "En attente"}</span><small>{job.error}</small></div>{["queued", "running", "paused", "error"].includes(job.status) && <IconButton icon={["paused", "error"].includes(job.status) ? Play : Pause} label={["paused", "error"].includes(job.status) ? "Reprendre" : "Mettre en pause"} onClick={async () => { try { await controlJob(job.id, ["paused", "error"].includes(job.status) ? "resume" : "pause"); await load(); } catch (err) { setError(errorMessage(err)); } }} />}</div>)}
    </form>}
    {tab === "email" && <section className="p-section p-composer"><div className="p-email-to">A : <strong>{item.email || "Adresse email manquante"}</strong><Status value={item.status} /></div><Notice>{dirty ? "Enregistre les changements de la fiche avant l'envoi." : item.status === "do_not_contact" ? "Ce contact est exclu des envois." : item.qualification_status !== "approved" ? "Brouillon modifiable. Approuve d'abord cette proposition dans Qualification pour deverrouiller tout envoi." : draftSaving ? "Enregistrement du brouillon..." : currentSignature === savedSignature ? "Brouillon enregistre. Chaque envoi demandera confirmation du destinataire et du texte exact." : "En attente de l'enregistrement du brouillon."}</Notice><p>Version {draftVersion.revision || "non enregistrée"} · {draftVersion.revision && draftVersion.approved_revision === draftVersion.revision ? "approuvée" : "à faire approuver dans Qualification"}</p>
      {browserDraft && <button className="p-button" onClick={() => {
        if (!window.confirm("Restaurer le texte local dans l’éditeur ? Son enregistrement créera une nouvelle version à approuver.")) return;
        setSubject(browserDraft.subject || ""); setBody(browserDraft.body || ""); setTemplateId(browserDraft.templateId || "");
        setBrowserDraft(null); setGmailOpened(false);
      }}>Restaurer le texte local non enregistré</button>}
      <div className="p-settings-fields"><label>Modele<select value={templateId} onChange={(e) => chooseTemplate(e.target.value)}><option value="">Message libre</option>{templates.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</select></label><label>Objet<input value={subject} maxLength={200} onChange={(e) => composeChange(setSubject, e.target.value)} /></label><label>Message<textarea value={body} maxLength={50000} onChange={(e) => composeChange(setBody, e.target.value)} /></label></div><div className="p-actions p-form-footer"><button className="p-button primary" disabled={mailDisabled} onClick={() => send()}><Send size={16} /> Confirmer puis envoyer</button><button className="p-button" disabled={mailDisabled} onClick={gmail}><Mail size={16} /> Ouvrir Gmail</button>{gmailOpened && <button className="p-button" disabled={mailDisabled} onClick={() => send(true)}>Confirmer l'envoi Gmail</button>}</div></section>}
    {tab === "history" && <section className="p-section"><div className="p-actions"><IconButton icon={RefreshCw} label="Actualiser l'historique" onClick={() => load()} /></div>{!timeline.length ? <Empty>Aucun evenement.</Empty> : <ul className="p-timeline">{timeline.map((entry) => <li key={`${entry.type}-${entry.id}`}><time>{formatDate(entry.date)}</time>{entry.type === "event" ? <p>{entry.message}</p> : <><strong>{entry.subject}</strong><p>{deliveryLabels[entry.delivery_status] || entry.delivery_status} / {entry.source}</p><small>{entry.recipient}</small>{entry.error_message && <Notice>{entry.error_message}</Notice>}<details><summary>Voir le message</summary><pre>{entry.body}</pre></details></>}</li>)}</ul>}</section>}
  </>}</aside></div>;
}
