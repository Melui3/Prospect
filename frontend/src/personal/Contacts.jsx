import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Search, Plus, RefreshCw, Bookmark, ChevronLeft, ChevronRight, Globe, Star, X } from "lucide-react";
import { errorMessage, getContacts, getCampaigns, saveContact } from "./api";
import { Empty, IconButton, Loading, Notice, Status, statuses, formatDate, externalUrl } from "./common";
import ContactDrawer from "./ContactDrawer";

const FILTER_KEY = "prospect_personal_filters";
const SAVED_KEY = "prospect_saved_filters";
const views = [["", "Tous"], ["contactable", "A contacter"], ["due", "A relancer"], ["incomplete", "Sans email"]];
function readStored(key, fallback) { try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; } }

export default function Contacts() {
  const [params, setParams] = useSearchParams();
  const filterQuery = new URLSearchParams([...params].filter(([key]) => !["open", "tab"].includes(key))).toString();
  const [filters, setFilters] = useState(() => params.size && [...params.keys()].some((key) => !["open", "tab"].includes(key)) ? Object.fromEntries([...params].filter(([key]) => !["open", "tab"].includes(key))) : readStored(FILTER_KEY, {}));
  const [search, setSearch] = useState(filters.search || "");
  const [data, setData] = useState(null);
  const [campaigns, setCampaigns] = useState([]);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(() => readStored(SAVED_KEY, []));
  const [savingFilter, setSavingFilter] = useState(false);
  const [filterName, setFilterName] = useState("");
  const [adding, setAdding] = useState(false);
  const [busy, setBusy] = useState(false);
  const request = useRef(0);
  const load = (force = false) => {
    const sequence = ++request.current;
    return getContacts({ ...filters, page_size: 40 }, force).then((value) => { if (sequence === request.current) { setData(value); setError(""); } }).catch((e) => { if (sequence === request.current) setError(errorMessage(e)); });
  };
  useEffect(() => { getCampaigns().then(setCampaigns).catch((e) => setError(errorMessage(e))); }, []);
  useEffect(() => { localStorage.setItem(FILTER_KEY, JSON.stringify(filters)); load(); }, [filters]);
  useEffect(() => { const timer = setTimeout(() => { if (search !== (filters.search || "")) setFilters((prev) => ({ ...prev, search, page: 1 })); }, 300); return () => clearTimeout(timer); }, [search, filters.search]);
  // Links from the daily view can replace filters while this route stays mounted.
  useEffect(() => { const next = Object.fromEntries(new URLSearchParams(filterQuery)); if (Object.keys(next).length) { setFilters(next); setSearch(next.search || ""); } }, [filterQuery]);
  const update = (key, value) => setFilters((prev) => ({ ...prev, [key]: value, page: 1 }));
  const open = (id, tab = "fiche") => setParams({ ...Object.fromEntries(params), open: id, ...(tab === "email" ? { tab } : {}) });
  const close = () => { const next = new URLSearchParams(params); next.delete("open"); next.delete("tab"); setParams(next, { replace: true }); };
  const storeSaved = (next) => { setSaved(next); localStorage.setItem(SAVED_KEY, JSON.stringify(next)); };
  const add = async (event) => {
    event.preventDefault(); setBusy(true); setError("");
    const form = new FormData(event.currentTarget);
    try { const item = await saveContact(null, Object.fromEntries(form)); setAdding(false); await load(true); open(item.id); } catch (e) { setError(errorMessage(e)); } finally { setBusy(false); }
  };
  return <div className="p-page"><header className="p-heading"><div><h1>Prospects</h1><p>{data ? `${data.count} entreprises` : "Entreprises et suivi"}</p></div><div className="p-actions"><IconButton icon={RefreshCw} label="Actualiser" onClick={() => load(true)} /><button className="p-button primary" onClick={() => setAdding(true)}><Plus size={17} /> Ajouter</button></div></header><Notice>{error}</Notice>
    <div className="p-tabs">{views.map(([value, label]) => <button key={value} className={value === (filters.view || "") ? "active" : ""} onClick={() => { setFilters({ view: value, page: 1 }); setSearch(""); }}>{label}</button>)}</div>
    <div className="p-filters"><div className="p-search"><Search size={16} /><input aria-label="Rechercher un prospect" placeholder="Entreprise, ville, email, notes..." value={search} onChange={(e) => setSearch(e.target.value)} /></div>
      <select aria-label="Statut" value={filters.status || ""} onChange={(e) => update("status", e.target.value)}><option value="">Tous les statuts</option>{statuses.map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select>
      <select aria-label="Site internet" value={filters.has_website || ""} onChange={(e) => update("has_website", e.target.value)}><option value="">Avec ou sans site</option><option value="true">Avec site</option><option value="false">Sans site</option></select>
      <select aria-label="Adresse email" value={filters.has_email || ""} onChange={(e) => update("has_email", e.target.value)}><option value="">Avec ou sans email</option><option value="true">Avec email</option><option value="false">Sans email</option></select>
      <select aria-label="Priorite" value={filters.priority || ""} onChange={(e) => update("priority", e.target.value)}><option value="">Toutes les priorites</option><option value="high">Haute</option><option value="normal">Normale</option><option value="low">Basse</option></select>
      <select aria-label="Recherche d'origine" value={filters.campaign || ""} onChange={(e) => update("campaign", e.target.value)}><option value="">Toutes les recherches</option>{campaigns.map((item) => <option key={item.id} value={item.id}>{item.secteur} - {item.ville}</option>)}</select>
      <select aria-label="Ordre de tri" value={filters.ordering || "-priority_rank,-created_at"} onChange={(e) => update("ordering", e.target.value)}><option value="-priority_rank,-created_at">Priorite, recents</option><option value="nom">Nom A-Z</option><option value="ville,nom">Ville A-Z</option><option value="next_followup_at">Date de relance</option><option value="-created_at">Plus recents</option></select>
      <IconButton icon={Bookmark} label="Enregistrer ces filtres" onClick={() => setSavingFilter(true)} /><IconButton icon={X} label="Effacer les filtres" onClick={() => { setFilters({}); setSearch(""); }} />
    </div>
    {saved.length > 0 && <div className="p-filters">{saved.map((item, index) => <span className="p-saved-filter" key={index}><button className="p-link" onClick={() => { setFilters({ ...item.filters, page: 1 }); setSearch(item.filters.search || ""); }}>{item.name}</button><button aria-label={`Supprimer le filtre ${item.name}`} title="Supprimer le filtre" onClick={() => storeSaved(saved.filter((_, i) => i !== index))}><X size={13} /></button></span>)}</div>}
    {!data ? <Loading /> : !data.results.length ? <Empty>Aucune entreprise pour ces filtres.</Empty> : <><div className="p-table-wrap"><table className="p-table"><thead><tr><th>Entreprise</th><th>Contact</th><th>Site</th><th>Statut</th><th>Relance</th></tr></thead><tbody>{data.results.map((item) => <tr key={item.id}><td><button className="p-name" onClick={() => open(item.id)}>{item.priority === "high" && <Star size={12} className="p-inline-star" />} {item.nom}</button><small>{item.ville} {item.campaign_names.length > 1 && ` / ${item.campaign_names.length} recherches`}</small></td><td>{item.email ? <button className="p-link" onClick={() => open(item.id)}>{item.email}</button> : <span className="p-muted">{item.enrichment_status === "pending" ? "A enrichir" : item.enrichment_status === "error" ? "Recherche a retenter" : "Email introuvable"}</span>}<small>{item.telephone || ""}</small></td><td>{externalUrl(item.website) ? <a className="p-icon" title="Ouvrir le site" href={externalUrl(item.website)} target="_blank" rel="noreferrer"><Globe size={16} /></a> : <span className="p-muted">-</span>}</td><td><Status value={item.status} /></td><td>{formatDate(item.next_followup_at)}</td></tr>)}</tbody></table></div><div className="p-pagination"><span>{filters.page || 1} / {Math.max(1, Math.ceil(data.count / 40))}</span><IconButton icon={ChevronLeft} label="Page precedente" disabled={!data.previous} onClick={() => setFilters((p) => ({ ...p, page: Number(p.page || 1) - 1 }))} /><IconButton icon={ChevronRight} label="Page suivante" disabled={!data.next} onClick={() => setFilters((p) => ({ ...p, page: Number(p.page || 1) + 1 }))} /></div></>}
    {params.get("open") && <ContactDrawer id={params.get("open")} initialTab={params.get("tab")} onClose={close} onChanged={() => load(true)} />}
    {adding && <div className="p-overlay"><form className="p-modal" role="dialog" aria-modal="true" aria-label="Ajouter une entreprise" onSubmit={add}><div className="p-drawer-head"><h2>Nouvelle entreprise</h2><IconButton icon={X} label="Fermer" onClick={() => setAdding(false)} /></div><Notice>{error}</Notice><div className="p-form-grid"><label className="p-full">Nom<input name="nom" required maxLength={255} autoFocus /></label><label>Ville<input name="ville" required maxLength={100} /></label><label>Email<input name="email" type="email" /></label><label className="p-full">Adresse<input name="adresse" /></label><label>Site<input name="website" type="url" /></label><label>Telephone<input name="telephone" /></label></div><div className="p-actions p-form-footer"><button className="p-button primary" disabled={busy}>Ajouter</button></div></form></div>}
    {savingFilter && <div className="p-overlay"><form className="p-modal" role="dialog" aria-modal="true" aria-label="Enregistrer les filtres" onSubmit={(e) => { e.preventDefault(); storeSaved([...saved, { name: filterName.trim(), filters }]); setSavingFilter(false); setFilterName(""); }}><div className="p-drawer-head"><h2>Filtre favori</h2><IconButton icon={X} label="Fermer" onClick={() => setSavingFilter(false)} /></div><label>Nom<input required maxLength={50} value={filterName} onChange={(e) => setFilterName(e.target.value)} autoFocus /></label><button className="p-button primary p-form-footer">Enregistrer</button></form></div>}
  </div>;
}
