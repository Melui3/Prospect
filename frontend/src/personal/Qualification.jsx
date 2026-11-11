import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Check, Clock3, ExternalLink, RefreshCw, Search, X } from "lucide-react";
import { decideQualification, errorMessage, getQualifications, runQualifications } from "./api";
import { Empty, IconButton, Loading, Notice, formatDate, externalUrl } from "./common";

const priorities = { high: "Priorite haute", medium: "Priorite moyenne", low: "Priorite basse" };
const tabs = [["pending", "A examiner"], ["deferred", "Reportes"]];

export default function Qualification() {
  const navigate = useNavigate();
  const [status, setStatus] = useState("pending");
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(null);
  const [running, setRunning] = useState(false);

  const load = (force = true) => getQualifications(status, force).then((value) => { setData(value); setError(""); }).catch((err) => setError(errorMessage(err)));
  useEffect(() => { setData(null); load(); }, [status]);
  useEffect(() => {
    if (!running) return undefined;
    const timer = setInterval(() => { load(true); }, 4000);
    const stop = setTimeout(() => setRunning(false), 60000);
    return () => { clearInterval(timer); clearTimeout(stop); };
  }, [running, status]);

  const run = async () => {
    setBusy("run"); setMessage(""); setError("");
    try {
      const result = await runQualifications();
      setMessage(`${result.queued} analyse(s) ajoutee(s) a la file${result.remaining ? `; ${result.remaining} autre(s) attendent` : ""}. Aucun email ne sera envoye par cette analyse.`);
      setRunning(result.queued > 0 || result.remaining > 0);
      await load(true);
    } catch (err) { setError(errorMessage(err)); }
    finally { setBusy(null); }
  };

  const decide = async (review, action) => {
    setBusy(review.id); setError(""); setMessage("");
    try { await decideQualification(review.id, action); await load(true); }
    catch (err) { setError(errorMessage(err)); }
    finally { setBusy(null); }
  };

  const openDraft = (review) => navigate(`/prospects?open=${review.prospect.id}&tab=email`);

  return <div className="p-page">
    <header className="p-heading"><div><h1>Qualification</h1><p>Observations verifiables et brouillons a relire</p></div><div className="p-actions">
      <IconButton icon={RefreshCw} label="Actualiser" onClick={() => load(true)} />
      <button className="p-button" disabled={busy === "run"} onClick={run}><Search size={16} /> Analyser les anciennes fiches</button>
    </div></header>
    <Notice>{error}</Notice><Notice kind="success">{message}</Notice>
    <div className="p-tabs">{tabs.map(([key, label]) => <button key={key} className={key === status ? "active" : ""} onClick={() => setStatus(key)}>{label}{key === status && data ? ` (${data.count})` : ""}</button>)}</div>
    {!data ? <Loading /> : !data.results.length ? <Empty>{status === "pending" ? "Aucune proposition a examiner. Les nouvelles recherches seront qualifiees automatiquement." : "Aucune proposition reportee."}</Empty> : <div className="p-qualification-list">{data.results.map((review) => <article className="p-section p-qualification-card" key={review.id}>
      <header className="p-section-head"><div><h2>{review.prospect.nom}</h2><p>{review.prospect.ville} · {review.prospect.email || "Email manquant"}</p></div><span className={`p-priority p-priority-${review.priority}`}>{priorities[review.priority] || "A examiner"}</span></header>
      <p className="p-qualification-meta">Analyse du {formatDate(review.checked_at)} · Statut : {status === "deferred" ? "Reportee" : "A examiner"}</p>
      <ul className="p-qualification-reasons">{review.reasons.map((reason, index) => <li key={`${review.id}-reason-${index}`}>{reason}</li>)}</ul>
      <div className="p-qualification-evidence"><strong>Preuves et limites</strong>{review.evidence.map((evidence, index) => <div className="p-qualification-evidence-item" key={`${review.id}-evidence-${index}`}><div><b>{evidence.source}</b> · {formatDate(evidence.observed_at)}</div><p>{evidence.detail}</p>{externalUrl(evidence.url) && <a className="p-link" href={externalUrl(evidence.url)} target="_blank" rel="noreferrer">Ouvrir la page observee <ExternalLink size={13} /></a>}</div>)}</div>
      {review.draft && <details className="p-qualification-draft"><summary>Brouillon prepare — a verifier avant tout envoi</summary><p><strong>Objet :</strong> {review.draft.subject}</p><pre>{review.draft.body}</pre></details>}
      <div className="p-actions p-form-footer"><button className="p-button" onClick={() => openDraft(review)}><ExternalLink size={15} /> Relire la fiche et le message</button>
        {status === "deferred" && <button className="p-button" disabled={busy === review.id} onClick={() => decide(review, "reopen")}><RefreshCw size={15} /> Remettre a examiner</button>}
        <button className="p-button primary" disabled={busy === review.id} onClick={() => decide(review, "approve")}><Check size={15} /> Approuver le prospect</button>
        {status === "pending" && <button className="p-button" disabled={busy === review.id} onClick={() => decide(review, "defer")}><Clock3 size={15} /> Reporter</button>}
        <button className="p-button p-danger" disabled={busy === review.id} onClick={() => decide(review, "reject")}><X size={15} /> Rejeter</button>
      </div>
    </article>)}</div>}
    <p className="p-qualification-note">Les recherches de site restent limitees aux pages publiques accessibles. Une panne ou une absence dans OpenStreetMap ne prouve pas qu'un site n'existe pas. L'analyse n'envoie aucun email.</p>
  </div>;
}
