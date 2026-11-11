import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { RefreshCw, ArrowRight, Radar } from "lucide-react";
import { getToday, errorMessage } from "./api";
import { Empty, IconButton, Loading, Notice, Status, formatDate, statusLabel } from "./common";

function ContactList({ items, followup = false }) {
  return !items.length ? <Empty>{followup ? "Aucune relance en retard." : "Aucune nouvelle fiche avec email."}</Empty> : <div className="p-table-wrap"><table className="p-table"><thead><tr><th>Entreprise</th><th>Email</th><th>{followup ? "Relance" : "Priorite"}</th><th>Statut</th><th /></tr></thead><tbody>{items.map((item) => <tr key={item.id}><td><Link className="p-name" to={`/prospects?open=${item.id}`}>{item.nom}</Link><small>{item.ville}</small></td><td>{item.email || "-"}</td><td>{followup ? formatDate(item.next_followup_at) : item.priority === "high" ? "Haute" : "Normale"}</td><td><Status value={item.status} /></td><td><Link className="p-icon" title="Ouvrir la fiche" to={`/prospects?open=${item.id}`}><ArrowRight size={17} /></Link></td></tr>)}</tbody></table></div>;
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
    <div className="p-metrics">{[[data.due_count, "Relances dues", "due"], [data.contactable_count, "Prets a contacter", "contactable"], [data.incomplete_count, "Sans email", "incomplete"], [data.won_count, "Clients gagnes", "won"]].map(([count, label, view]) => <Link key={view} className="p-metric" to={`/prospects?${view === "won" ? "status=won" : `view=${view}`}`}><strong>{count}</strong><span>{label}</span></Link>)}</div>
    <section className="p-section"><div className="p-section-head"><h2>Relances prioritaires</h2><Link className="p-link" to="/prospects?view=due">Tout voir</Link></div><ContactList items={data.due} followup /></section>
    <section className="p-section"><div className="p-section-head"><h2>A contacter</h2><Link className="p-link" to="/prospects?view=contactable">Tout voir</Link></div><ContactList items={data.contactable} /></section>
    <section className="p-section"><h2>Pipeline</h2><div className="p-pipeline">{data.pipeline.map(({ status, count }) => <Link key={status} to={`/prospects?status=${status}`}><span>{statusLabel(status)}</span><strong>{count}</strong></Link>)}</div></section>
    {data.jobs.length > 0 && <section className="p-section"><h2>Recherches en cours</h2>{data.jobs.map((job) => <div className="p-job" key={job.id}><Radar size={18} /><div className="p-job-content"><Link to="/campaigns">{job.stage || "En attente"}</Link><small>{job.processed} / {job.total || "?"} fiches, {job.with_email} emails</small><progress value={job.processed} max={job.total || 1} /></div></div>)}</section>}
  </>}</div>;
}
