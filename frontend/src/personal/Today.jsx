import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { RefreshCw, ArrowRight, Radar } from "lucide-react";
import { getToday, errorMessage } from "./api";
import { Evidence } from "./Qualification";
import { Empty, IconButton, Loading, Notice, Status, formatDate, statusLabel } from "./common";

function ContactList({ items, followup = false }) {
  return !items.length ? <Empty>{followup ? "Aucune relance en retard." : "Aucune nouvelle fiche avec email."}</Empty> : <div className="p-table-wrap"><table className="p-table"><thead><tr><th>Entreprise</th><th>Email</th><th>{followup ? "Relance" : "Priorite"}</th><th>Statut</th><th /></tr></thead><tbody>{items.map((item) => <tr key={item.id}><td><Link className="p-name" to={`/prospects?open=${item.id}`}>{item.nom}</Link><small>{item.ville}</small></td><td>{item.email || "-"}</td><td>{followup ? formatDate(item.next_followup_at) : item.priority === "high" ? "Haute" : "Normale"}</td><td><Status value={item.status} /></td><td><Link className="p-icon" title="Ouvrir la fiche" to={`/prospects?open=${item.id}`}><ArrowRight size={17} /></Link></td></tr>)}</tbody></table></div>;
}

const jobKinds = {
  qualification: ["Qualification", "/qualification"],
  search: ["Recherche", "/campaigns"],
  enrichment: ["Recherche d’email", "/prospects"],
};

function JobProgress({ counts = {}, active, recent = [] }) {
  const metrics = [
    ["queued", "En attente"], ["running", "En cours"],
    ["done", "Terminées"], ["error", "En erreur"],
  ];
  if (counts.paused) metrics.push(["paused", "En pause"]);
  return <section className="p-section">
    <h2>Suivi des tâches</h2>
    <div className="p-pipeline">{metrics.map(([status, label]) =>
      <div key={status}><span>{label}</span> <strong>{counts[status] ?? 0}</strong></div>
    )}</div>
    {active.map((job) => {
      const [label, path] = jobKinds[job.kind] ?? ["Tâche", "/campaigns"];
      return <div className="p-job" key={job.id}>
        <Radar size={18} />
        <div className="p-job-content">
          <Link to={path}>{label} · {job.stage}</Link>
          <small>{job.processed} / {job.total || "?"} fiches</small><small>{job.outcome_label}</small>{job.status === "queued" && job.error && <small>{job.error} · Reprise au plus tôt {formatDate(job.next_run_at)}</small>}
          <progress value={job.processed} max={job.total || 1} />
          {job.observations?.length > 0 && <details><summary>Observations de la découverte</summary><Evidence items={job.observations} /></details>}
        </div>
      </div>;
    })}
    {recent.length > 0 && <div>
      <h3>Derniers résultats</h3>
      {recent.map((job) => {
        const [label, path] = jobKinds[job.kind] ?? ["Tâche", "/campaigns"];
        return <div className="p-job" key={job.id}><div className="p-job-content">
          <Link to={path}>{label} · {job.status === "error" ? "En erreur" : job.stage}</Link>
          <small>{job.outcome_label}</small>{job.status === "error" && <small>{job.error}</small>}{job.failure_explanation && <small>{job.failure_explanation}</small>}
          {job.observations?.length > 0 && <details><summary>Observations de la découverte</summary><Evidence items={job.observations} /></details>}
        </div></div>;
      })}
    </div>}
  </section>;
}

export default function Today() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const load = (force = false) => getToday(force).then((value) => { setData(value); setError(""); }).catch((e) => setError(errorMessage(e)));
  useEffect(() => { load(); }, []);
  useEffect(() => {
    if (!data?.jobs.some((job) => ["running", "queued"].includes(job.status))) return;
    const timer = setInterval(() => load(true), 4000);
    return () => clearInterval(timer);
  }, [data?.jobs]);
  return <div className="p-page"><header className="p-heading"><div><h1>Aujourd'hui</h1><p>{data ? `${data.total} entreprises uniques` : "Ton espace de prospection"}</p></div><div className="p-actions"><IconButton icon={RefreshCw} label="Actualiser" onClick={() => load(true)} /><Link className="p-button primary" to="/campaigns"><Radar size={16} /> Nouvelle recherche</Link></div></header><Notice>{error}</Notice>{!data ? <Loading /> : <>
    <div className="p-metrics">{[[data.due_count, "Relances dues", "due"], [data.contactable_count, "Avec email", "contactable"], [data.incomplete_count, "Sans email", "incomplete"], [data.won_count, "Clients gagnes", "won"]].map(([count, label, view]) => <Link key={view} className="p-metric" to={`/prospects?${view === "won" ? "status=won" : `view=${view}`}`}><strong>{count}</strong><span>{label}</span></Link>)}</div>
    <section className="p-section"><div className="p-section-head"><h2>Relances prioritaires</h2><Link className="p-link" to="/prospects?view=due">Tout voir</Link></div><ContactList items={data.due} followup /></section>
    <section className="p-section"><div className="p-section-head"><h2>Nouvelles fiches avec email</h2><Link className="p-link" to="/prospects?view=contactable">Tout voir</Link></div><ContactList items={data.contactable} /></section>
    <section className="p-section"><h2>Pipeline</h2><div className="p-pipeline">{data.pipeline.map(({ status, count }) => <Link key={status} to={`/prospects?status=${status}`}><span>{statusLabel(status)}</span><strong>{count}</strong></Link>)}</div></section>
    <JobProgress counts={data.job_counts} active={data.jobs} recent={data.recent_jobs} />
  </>}</div>;
}
