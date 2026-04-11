import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getCampaigns, createCampaign, deleteCampaign, launchCampaign } from "../api/client";
import Badge from "../components/Badge";

const SECTEURS = [
  "boulangerie","restaurant","coiffeur","pharmacie","plombier",
  "electricien","garage","fleuriste","epicerie","opticien",
  "dentiste","veterinaire","avocat","comptable","architecte",
];

export default function Campaigns() {
  const [campaigns, setCampaigns] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ secteur: "boulangerie", ville: "", rayon_km: 5 });
  const [loading, setLoading] = useState(true);
  const [launching, setLaunching] = useState(null);
  const [error, setError] = useState("");

  const load = () =>
    getCampaigns()
      .then(setCampaigns)
      .finally(() => setLoading(false));

  useEffect(() => { load(); }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    setError("");
    try {
      await createCampaign(form);
      setShowForm(false);
      setForm({ secteur: "boulangerie", ville: "", rayon_km: 5 });
      load();
    } catch {
      setError("Erreur lors de la création.");
    }
  };

  const handleLaunch = async (id) => {
    setLaunching(id);
    try {
      const result = await launchCampaign(id);
      alert(`✅ Terminé ! ${result.total_found} prospects trouvés (${result.with_email} avec email)`);
      load();
    } catch (err) {
      const msg = err.response?.data?.error ?? "Erreur lors du lancement.";
      alert(`❌ ${msg}`);
      load();
    } finally {
      setLaunching(null);
    }
  };

  const handleDelete = async (id) => {
    if (!confirm("Supprimer cette campagne et tous ses prospects ?")) return;
    await deleteCampaign(id);
    load();
  };

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-800">Campagnes</h2>
          <p className="text-slate-500 text-sm mt-1">Lancez une prospection par secteur et ville</p>
        </div>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
        >
          + Nouvelle campagne
        </button>
      </div>

      {/* Formulaire création */}
      {showForm && (
        <form
          onSubmit={handleCreate}
          className="bg-white border border-slate-200 rounded-xl p-6 space-y-4"
        >
          <h3 className="font-semibold text-slate-700">Nouvelle campagne</h3>
          {error && <p className="text-red-500 text-sm">{error}</p>}
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">
                Secteur d'activité
              </label>
              <select
                value={form.secteur}
                onChange={(e) => setForm((f) => ({ ...f, secteur: e.target.value }))}
                className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {SECTEURS.map((s) => (
                  <option key={s} value={s}>
                    {s.charAt(0).toUpperCase() + s.slice(1)}
                  </option>
                ))}
                <option value="">Autre (saisir ci-dessous)</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">
                Ville
              </label>
              <input
                required
                value={form.ville}
                onChange={(e) => setForm((f) => ({ ...f, ville: e.target.value }))}
                placeholder="Paris, Lyon, Bordeaux…"
                className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">
                Rayon (km)
              </label>
              <input
                type="number"
                min={1}
                max={50}
                value={form.rayon_km}
                onChange={(e) => setForm((f) => ({ ...f, rayon_km: Number(e.target.value) }))}
                className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
          <div className="flex gap-3 pt-1">
            <button
              type="submit"
              className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium"
            >
              Créer
            </button>
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="text-slate-500 hover:text-slate-700 px-4 py-2 text-sm"
            >
              Annuler
            </button>
          </div>
        </form>
      )}

      {/* Liste */}
      {loading ? (
        <p className="text-slate-400 text-sm">Chargement…</p>
      ) : campaigns.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-200 p-12 text-center text-slate-400 text-sm">
          Aucune campagne. Créez-en une pour commencer.
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-500 uppercase text-xs">
              <tr>
                <th className="px-4 py-3 text-left">Secteur</th>
                <th className="px-4 py-3 text-left">Ville</th>
                <th className="px-4 py-3 text-left">Rayon</th>
                <th className="px-4 py-3 text-left">Statut</th>
                <th className="px-4 py-3 text-right">Prospects</th>
                <th className="px-4 py-3 text-right">Avec email</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {campaigns.map((c) => (
                <tr key={c.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-medium capitalize">{c.secteur}</td>
                  <td className="px-4 py-3 text-slate-600">{c.ville}</td>
                  <td className="px-4 py-3 text-slate-500">{c.rayon_km} km</td>
                  <td className="px-4 py-3">
                    <Badge value={c.status} />
                    {c.status === "error" && (
                      <p className="text-xs text-red-500 mt-1 max-w-xs truncate">
                        {c.error_message}
                      </p>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">{c.total_prospects}</td>
                  <td className="px-4 py-3 text-right text-green-600">
                    {c.prospects_with_email}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex justify-end gap-2">
                      {(c.status === "draft" || c.status === "done" || c.status === "error") && (
                        <button
                          onClick={() => handleLaunch(c.id)}
                          disabled={launching === c.id}
                          className="bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white px-3 py-1 rounded text-xs font-medium transition-colors"
                        >
                          {launching === c.id ? "Scraping…" : "Lancer"}
                        </button>
                      )}
                      {c.total_prospects > 0 && (
                        <Link
                          to={`/prospects?campaign=${c.id}`}
                          className="bg-blue-100 hover:bg-blue-200 text-blue-700 px-3 py-1 rounded text-xs font-medium transition-colors"
                        >
                          Voir prospects
                        </Link>
                      )}
                      <button
                        onClick={() => handleDelete(c.id)}
                        className="text-slate-400 hover:text-red-500 px-2 py-1 text-xs transition-colors"
                      >
                        ✕
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
