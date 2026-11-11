import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Play, Pause, RefreshCw, Trash2, Plus, Radar } from "lucide-react";
import { controlJob, createCampaign, deleteCampaign, errorMessage, getCampaigns, launchCampaign, setCampaignSchedule } from "./api";
import { Empty, IconButton, Loading, Notice, formatDate } from "./common";

const sectors = ["Restaurant", "Boulangerie", "Coiffeur", "Garage", "Plombier", "Electricien", "Association", "Commerce", "Fleuriste", "Institut de beaute"];
const presets = [["Restaurant", "Rennes", 8], ["Boulangerie", "Saint-Malo", 10], ["Coiffeur", "Fougeres", 12], ["Garage", "Vitre", 12], ["Plombier", "Rennes", 15], ["Association", "Rennes", 10]];
const stateLabels = { draft: "Non lancee", queued: "En file d'attente", running: "En cours", paused: "En pause", done: "Terminee", error: "Interrompue" };

export default function Campaigns() {
  const [data, setData] = useState(null);
  const [form, setForm] = useState({ secteur: "Restaurant", ville: "Rennes", rayon_km: 8, repeat_days: 0 });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(null);
  const [success, setSuccess] = useState("");
  const load = (force = false) => getCampaigns(force).then((value) => { setData(value); setError(""); }).catch((e) => setError(errorMessage(e)));
  useEffect(() => { load(); }, []);
  useEffect(() => {
    if (!data?.some((item) => ["running", "queued"].includes(item.job?.status))) return;
    const timer = setInterval(() => load(true), 3000);
    return () => clearInterval(timer);
  }, [data]);
  const execute = async (key, action) => { setBusy(key); setError(""); try { await action(); await load(true); } catch (err) { setError(errorMessage(err)); } finally { setBusy(null); } };
  const create = (e) => {
    e.preventDefault();
    execute("create", async () => {
      const campaign = await createCampaign({ ...form, rayon_km: Number(form.rayon_km), repeat_days: Number(form.repeat_days) });
      await launchCampaign(campaign.id);
      setSuccess("Recherche ajoutee a la file.");
    });
  };
  const updateSchedule = (campaign, repeatDays) => execute(`schedule-${campaign.id}`, async () => {
    await setCampaignSchedule(campaign.id, repeatDays);
    setSuccess(repeatDays ? `Recherche automatique activee pour ${campaign.secteur} / ${campaign.ville}.` : `Recherche automatique desactivee pour ${campaign.secteur} / ${campaign.ville}.`);
  });

  return <div className="p-page">
    <header className="p-heading"><div><h1>Recherches</h1><p>{data?.length || 0} campagnes</p></div><IconButton icon={RefreshCw} label="Actualiser" onClick={() => load(true)} /></header>
    <Notice>{error}</Notice><Notice kind="success">{success}</Notice>
    <section className="p-section">
      <h2>Nouvelle recherche</h2>
      <div className="p-presets">{presets.map(([secteur, ville, rayon]) => <button className="p-button" key={`${secteur}-${ville}`} onClick={() => setForm((previous) => ({ ...previous, secteur, ville, rayon_km: rayon }))}><span>{secteur}<small>{ville} / {rayon} km</small></span><Plus size={16} /></button>)}</div>
      <form className="p-campaign-form" onSubmit={create}>
        <label>Secteur<select value={form.secteur} onChange={(e) => setForm({ ...form, secteur: e.target.value })}>{sectors.map((sector) => <option key={sector}>{sector}</option>)}</select></label>
        <label>Ville<input value={form.ville} onChange={(e) => setForm({ ...form, ville: e.target.value })} required maxLength={100} /></label>
        <label>Rayon (km)<input type="number" min={1} max={30} value={form.rayon_km} onChange={(e) => setForm({ ...form, rayon_km: e.target.value })} required /></label>
        <label>Répéter la recherche<select value={form.repeat_days} onChange={(e) => setForm({ ...form, repeat_days: e.target.value })}><option value="0">Non</option><option value="7">Chaque semaine</option><option value="14">Toutes les deux semaines</option><option value="30">Chaque mois</option></select><small>La première recherche démarre au clic; les suivantes alimentent la file de validation sans envoyer d’email.</small></label>
        <button className="p-button primary" disabled={busy === "create"}><Radar size={17} /> Lancer</button>
      </form>
    </section>
    <section className="p-section">
      <h2>Historique des recherches</h2>
      {!data ? <Loading /> : !data.length ? <Empty>Aucune recherche.</Empty> : <div className="p-table-wrap"><table className="p-table"><thead><tr><th>Recherche</th><th>Avancement</th><th>Entreprises</th><th>Avec email</th><th>Récurrence</th><th>Actions</th></tr></thead><tbody>{data.map((campaign) => {
        const job = campaign.job;
        const active = ["queued", "running"].includes(job?.status);
        const resume = ["paused", "error"].includes(job?.status);
        return <tr key={campaign.id}>
          <td><Link className="p-name" to={`/prospects?campaign=${campaign.id}`}>{campaign.secteur}</Link><small>{campaign.ville} / {campaign.rayon_km} km</small></td>
          <td><span>{stateLabels[job?.status || campaign.status]}</span>{job && <div className="p-job-content"><small>{job.stage} {job.total ? `(${job.processed}/${job.total})` : ""}</small>{active && <progress value={job.processed} max={job.total || 1} />}<small className="p-danger">{job.error || campaign.error_message}</small></div>}</td>
          <td>{campaign.total_prospects}</td><td>{campaign.prospects_with_email}</td>
          <td><div className="p-campaign-repeat"><select aria-label={`Récurrence ${campaign.secteur} ${campaign.ville}`} value={campaign.repeat_days || 0} disabled={busy === `schedule-${campaign.id}`} onChange={(e) => updateSchedule(campaign, Number(e.target.value))}><option value="0">Aucune</option><option value="7">Chaque semaine</option><option value="14">Toutes les deux semaines</option><option value="30">Chaque mois</option></select>{campaign.next_search_at && <small>Prochaine : {formatDate(campaign.next_search_at)}</small>}</div></td>
          <td><div className="p-actions"><IconButton icon={active ? Pause : Play} label={active ? "Mettre en pause" : resume ? "Reprendre" : "Relancer la recherche"} disabled={busy === campaign.id} onClick={() => execute(campaign.id, () => active || resume ? controlJob(job.id, active ? "pause" : "resume") : launchCampaign(campaign.id))} /><IconButton icon={Trash2} label="Supprimer la recherche, conserver les contacts" disabled={active || busy === campaign.id} onClick={() => { if (window.confirm("Supprimer cette recherche ? Les entreprises et leur historique sont conserves.")) execute(campaign.id, () => deleteCampaign(campaign.id)); }} /></div></td>
        </tr>;
      })}</tbody></table></div>}
    </section>
  </div>;
}
