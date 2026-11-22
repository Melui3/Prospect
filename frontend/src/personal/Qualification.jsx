import { useEffect, useState } from "react";
import { Check, Clock3, RefreshCw, Search, X } from "lucide-react";
import { decideQualification, errorMessage, getQualifications, runQualifications, saveEmailDraft, saveQualificationEvidence, generateEmailDraft } from "./api";
import { Empty, IconButton, Loading, Notice, formatDate, externalUrl } from "./common";

const tabs = [
  ["selection", "Sélection commerciale"], ["ready", "Propositions (dont historiques)"], ["pilot", "Pilote commercial"],
  ["enrich", "À enrichir"], ["deferred", "Reportés"], ["approved", "Approuvés / à relire"],
  ["no_opportunity", "Sans opportunité démontrée"], ["excluded", "Exclus"],
];
const outcome = { creation: "Création de site", refonte: "Refonte / amélioration" };
const emptyProof = { origin: "human", search_url: "", contact_url: "", method: "", limits: "", confirmed: false };

export function Evidence({ items }) {
  const current = items.filter((item) => !item.historical);
  const historical = items.filter((item) => item.historical);
  const render = (rows) => rows.map((item, index) => <div className="p-qualification-evidence-item" key={index}>
    <strong>{item.source}</strong> · {formatDate(item.observed_at)}
    <small>{({ automatic: "Observation automatique", human: "Observation humaine", assisted: "Observation assistée" })[item.origin] || "Origine non renseignée"}</small>
    <p>{item.detail}</p>
    {item.method && <p>Méthode — {item.method}</p>}
    {item.limits && <p>Limites — {item.limits}</p>}
    {externalUrl(item.url) && <a className="p-link" href={externalUrl(item.url)} target="_blank" rel="noreferrer">Consulter la source</a>}
  </div>);
  return <div className="p-qualification-evidence">
    <strong>Preuves et limites</strong>
    {render(current)}
    {historical.length > 0 && <details><summary>Observations précédentes ({historical.length})</summary>{render(historical)}</details>}
  </div>;
}

function ReviewCard({ review, onUpdate, onDecision, dirty, setDirty, disabled }) {
  const [draft, setDraft] = useState(review.draft || { subject: "", body: "", revision: 0, versions: [] });
  const [proof, setProof] = useState(emptyProof);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const { prospect } = review;
  const editable = Boolean(review.opportunity || review.draft && ["pending", "deferred", "approved"].includes(review.status));
  const actionable = ["ready", "enrich", "deferred", "approved"].includes(review.bucket);
  const busy = working || disabled;

  const act = async (operation) => {
    setWorking(true); setError(""); setNotice("");
    try { await operation(); }
    catch (err) { setError(errorMessage(err)); }
    finally { setWorking(false); }
  };
  const save = async () => {
    const saved = await saveEmailDraft(prospect.id, { subject: draft.subject, body: draft.body, expected_revision: draft.revision || 0 });
    setDraft(saved); setDirty(false);
    setNotice(saved.approved_revision === saved.revision ? "Version approuvée inchangée." : "Version enregistrée. Une approbation de ce texte exact est nécessaire.");
    return saved;
  };
  const decide = (decision) => act(async () => {
    const current = dirty ? await save() : draft;
    await onDecision(review, decision, current.revision);
  });
  const change = (field, value) => { setDraft((previous) => ({ ...previous, [field]: value })); setDirty(true); };
  const record = (value) => act(async () => {
    await saveQualificationEvidence(review.id, value);
    await onUpdate();
  });

  return <article className="p-section p-qualification-card">
    <header className="p-section-head">
      <div><h2>{prospect.nom}</h2><p>{prospect.ville} · {prospect.email || "Email manquant"}</p></div>
      <strong>{outcome[review.opportunity] || tabs.find(([key]) => key === review.bucket)?.[1]}</strong>
    </header>
    {review.selection && <section className="p-settings-fields">
      <h3>Rang {review.selection.rank} · {review.selection.signal}</h3>
      <p>{review.selection.fit}</p>
      <a className="p-link" href={review.selection.service.url} target="_blank" rel="noreferrer">
        Prestation NateOS correspondante · {review.selection.service.title}
      </a>
      <ul>{review.selection.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>
      <p>Plus ancienne preuve nécessaire du {formatDate(review.selection.oldest_required_evidence_at)}.</p>
      <details><summary>Preuves du classement</summary>
        {review.selection.evidence.map((proof) => <p key={proof.id}>
          {proof.source} · {formatDate(proof.observed_at)} · {proof.detail}{" "}
          {externalUrl(proof.url) && <a className="p-link" href={externalUrl(proof.url)} target="_blank" rel="noreferrer">Source</a>}
        </p>)}
        <ul>{review.selection.limits.map((limit) => <li key={limit}>{limit}</li>)}</ul>
      </details>
    </section>}
    <p className="p-qualification-meta">Analyse du {formatDate(review.checked_at)}</p>
    {externalUrl(prospect.website) && <a className="p-link" href={externalUrl(prospect.website)} target="_blank" rel="noreferrer">Site renseigné</a>}
    <ul className="p-qualification-reasons">{review.reasons.map((reason, index) => <li key={index}>{reason}</li>)}</ul>
    {review.selection_diagnostic?.code && <section aria-label="Motif de non-sélection">
      <h3>Non retenu dans la sélection actuelle</h3>
      <p>{review.selection_diagnostic.label}</p>
      <p>{review.selection_diagnostic.usable_proof_count} preuve(s) recevable(s) sur {review.selection_diagnostic.active_proof_count} ; {review.selection_diagnostic.missing_origin_count} sans origine démontrée.</p>
      {review.selection_diagnostic.historical_recovery && <p>{review.selection_diagnostic.historical_recovery}</p>}
    </section>}
    <Evidence items={review.evidence} />
    <Notice>{error}</Notice><Notice kind="success">{notice}</Notice>
    {review.selection && <button className="p-button" disabled={busy} onClick={() => act(async () => {
      if ((dirty || draft.revision) && !window.confirm("Créer une nouvelle version personnalisée ? Les versions enregistrées seront conservées ; le texte non enregistré sera abandonné. Une nouvelle approbation sera obligatoire.")) return;
      await generateEmailDraft(prospect.id, draft.revision || 0);
      setDirty(false); await onUpdate();
    })}>{draft.revision ? "Générer une nouvelle version personnalisée" : "Préparer le brouillon personnalisé"}</button>}
    {editable && <section className="p-settings-fields">
      <h3>Brouillon · version {draft.revision || "non enregistrée"}</h3>
      {draft.origin === "legacy" && <p>Brouillon historique conservé. Il ne provient pas du générateur personnalisé. Sa régénération exige un dossier retenu dans la sélection actuelle.</p>}
      <p>{draft.approved_revision === draft.revision && draft.revision ? "Cette version est approuvée." : "Cette version n’est pas approuvée. Toute modification exige une nouvelle validation."}</p>
      <label>Objet<input disabled={busy} value={draft.subject} maxLength={200} onChange={(e) => change("subject", e.target.value)} /></label>
      <label>Message<textarea disabled={busy} rows={12} value={draft.body} maxLength={50000} onChange={(e) => change("body", e.target.value)} /></label>
      <div className="p-actions">
        <button className="p-button" disabled={busy || !dirty || !draft.subject.trim() || !draft.body.trim()} onClick={() => act(save)}>Enregistrer le brouillon</button>
      </div>
    </section>}
    {draft.versions?.length > 0 && <details className="p-qualification-draft"><summary>Historique des versions ({draft.versions.length})</summary>
      {draft.versions.map((version) => <section key={version.number}>
        <h3>Version {version.number} · {formatDate(version.created_at)}</h3>
        <p>{({ conditional: "Rédaction conditionnelle", human: "Modification humaine", legacy: "Brouillon historique", manual: "Saisie manuelle" })[version.origin] || version.origin}
          {version.approved_at && ` · approuvée le ${formatDate(version.approved_at)}`}</p>
        <p>Destinataire : {version.recipient}</p><strong>{version.subject}</strong><pre>{version.body}</pre>
        {version.evidence?.records?.length > 0 && <Evidence items={version.evidence.records} />}
      </section>)}
    </details>}
    {!editable && review.draft && <details className="p-qualification-draft">
      <summary>Brouillon conservé · non prêt à envoyer</summary><strong>{review.draft.subject}</strong><pre>{review.draft.body}</pre>
    </details>}
    {actionable && !editable && prospect.website && <button className="p-button" disabled={busy} onClick={() => record({ check_site: true })}>Vérifier la page renseignée</button>}
    {actionable && !editable && prospect.email && !prospect.website && <details>
      <summary>Consigner une recherche publique</summary>
      <form className="p-settings-fields" onSubmit={(e) => { e.preventDefault(); record(proof); }}>
        {[["search_url", "Adresse de la recherche ou des résultats consultés"], ["contact_url", "Page qui publie l’adresse professionnelle"],
          ["method", "Requêtes effectuées et critères d’identification"], ["limits", "Périmètre et limites de la recherche"]].map(([key, label]) =>
          <label key={key}>{label}<input type={key.endsWith("_url") ? "url" : "text"} required disabled={busy}
            value={proof[key]} onChange={(e) => setProof({ ...proof, [key]: e.target.value })} /></label>)}
        <label><input type="checkbox" required checked={proof.confirmed} disabled={busy}
          onChange={(e) => setProof({ ...proof, confirmed: e.target.checked })} /> J’ai vérifié l’identité et l’email publié. Aucun site officiel n’a été identifié dans les résultats consultés.</label>
        <button className="p-button" disabled={busy}>Enregistrer les preuves</button>
      </form>
    </details>}
    {actionable && <div className="p-actions p-form-footer">
      {editable && <button className="p-button primary" disabled={busy || !draft.subject.trim() || !draft.body.trim()} onClick={() => decide("approve")}><Check size={15} /> Approuver cette version</button>}
      {["deferred", "approved"].includes(review.bucket)
        ? <button className="p-button" disabled={busy} onClick={() => decide("reopen")}><RefreshCw size={15} /> Remettre à examiner</button>
        : <button className="p-button" disabled={busy} onClick={() => decide("defer")}><Clock3 size={15} /> Reporter</button>}
      <button className="p-button p-danger" disabled={busy} onClick={() => decide("reject")}><X size={15} /> Rejeter</button>
    </div>}
  </article>;
}

export default function Qualification() {
  const [status, setStatus] = useState("selection");
  const [data, setData] = useState(null);
  const [selected, setSelected] = useState(null);
  const [revision, setRevision] = useState(0);
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [running, setRunning] = useState(false);
  const [busy, setBusy] = useState(false);
  const fetchData = () => getQualifications(status, true);
  const refresh = async () => { const value = await fetchData(); setData(value); };
  const report = (err) => setError(errorMessage(err));
  useEffect(() => {
    let current = true;
    fetchData().then((value) => { if (current) setData(value); }).catch((err) => { if (current) report(err); });
    return () => { current = false; };
  }, [status]);
  useEffect(() => {
    if (!running || dirty) return undefined;
    let current = true;
    const timer = setInterval(() => fetchData().then((value) => { if (current) setData(value); }).catch(report), 4000);
    const stop = setTimeout(() => setRunning(false), 60000);
    return () => { current = false; clearInterval(timer); clearTimeout(stop); };
  }, [running, status, dirty]);

  const changeSelection = (action) => {
    if (dirty && !window.confirm("Quitter cette fiche sans enregistrer le brouillon ?")) return;
    setDirty(false); setError(""); action();
  };
  const run = async () => {
    setBusy(true); setError(""); setMessage("");
    try {
      const result = await runQualifications();
      setMessage(`${result.queued} analyse(s) dans la file${result.remaining ? ` · ${result.remaining} fiche(s) hors de ce lot` : ""}.`);
      setRunning(result.queued > 0);
      await refresh();
    } catch (err) { report(err); }
    finally { setBusy(false); }
  };
  const results = data?.results || [];
  const index = Math.max(0, results.findIndex((item) => item.id === selected));
  const review = results[index];
  const decide = async (item, decision, draftRevision) => {
    await decideQualification(item.id, decision, draftRevision);
    const next = results[index + 1]?.id || results[index - 1]?.id || null;
    setSelected(next); setDirty(false); setMessage("Décision enregistrée.");
    await refresh();
  };
  return <div className="p-page">
    <header className="p-heading"><div><h1>Qualification</h1><p>Preuves, brouillons et décisions</p></div><div className="p-actions">
      <IconButton icon={RefreshCw} label="Actualiser" onClick={() => refresh().catch(report)} />
      <button className="p-button" disabled={busy} onClick={run}><Search size={16} /> Analyser les fiches sans analyse</button>
    </div></header>
    <Notice>{error}</Notice><Notice kind="success">{message}</Notice>
    {status === "selection" && data?.selection && <section className="p-section">
      <h2>{data.count} opportunité(s) retenue(s) sur {data.selection.limit} maximum</h2>
      <p>Preuves nécessaires de moins de {data.selection.max_evidence_age_days} jours et contact corroboré. Validation humaine requise.</p>
      <p>Les anciennes propositions et le pilote historique sont conservés séparément ; ils ne satisfont pas nécessairement les critères actuels.</p>
      <details><summary>Motifs de non-sélection</summary>
        <ul>{Object.entries(data.selection.omitted_counts || {}).map(([code, count]) => <li key={code}>{({contact_invalid: "Adresse absente ou invalide", contact_unverified_or_stale: "Contact non corroboré ou périmé", business_evidence_insufficient_or_stale: "Preuves commerciales insuffisantes ou périmées", human_decision_or_contacted_duplicate: "Décision humaine ou contact antérieur, doublons inclus", decision_or_status: "Décision ou statut incompatible", exclusion_or_outreach: "Exclusion ou contact antérieur", duplicate: "Doublon"})[code] || "Dossier non recevable"} : {count}</li>)}</ul>
        <p>Le premier motif bloquant est compté pour chaque fiche. Aucun critère commercial n’a été assoupli.</p>
      </details>
      <details><summary>Critères de classement</summary>
        <ol>{data.selection.criteria.map((criterion) => <li key={criterion}>{criterion}</li>)}</ol>
        <p>{data.selection.held_by_limit} autre(s) dossier(s) justifié(s) au-delà des cinq places.</p>
      </details>
    </section>}
    <div className="p-tabs">{tabs.map(([key, label]) => <button key={key} className={key === status ? "active" : ""}
      onClick={() => key !== status && changeSelection(() => { setStatus(key); setSelected(null); setData(null); })}>{label}{data ? ` (${data.counts?.[key] ?? 0})` : ""}</button>)}</div>
    {!data ? <Loading /> : !review ? <Empty>{status === "selection" ? "Aucune opportunité ne dispose actuellement de toutes les preuves nécessaires." : "Aucune fiche dans ce filtre."}</Empty> : <>
      <div className="p-actions">
        <button className="p-button" disabled={index === 0} onClick={() => changeSelection(() => setSelected(results[index - 1].id))}>Précédente</button>
        <span>{index + 1} / {data.count}</span>
        <button className="p-button" disabled={index >= results.length - 1} onClick={() => changeSelection(() => setSelected(results[index + 1].id))}>Suivante</button>
      </div>
      <ReviewCard key={`${review.id}-${revision}`} review={review} onUpdate={async () => {
        const updated = await fetchData(); setData(updated); setRevision((value) => value + 1);
      }} onDecision={decide} dirty={dirty} setDirty={setDirty} disabled={busy} />
    </>}
  </div>;
}
