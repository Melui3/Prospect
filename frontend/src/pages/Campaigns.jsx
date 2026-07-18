import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  getCampaigns,
  createCampaign,
  deleteCampaign,
  launchCampaign,
} from "../api/client";
import Badge from "../components/Badge";

const SECTEURS = [
  "association",
  "restaurant",
  "boulangerie",
  "coiffeur",
  "fleuriste",
  "garage",
  "plombier",
  "electricien",
  "epicerie",
  "opticien",
  "dentiste",
  "veterinaire",
  "avocat",
  "comptable",
  "architecte",
  "pharmacie",
];

const CAMPAIGN_PRESETS = [
  {
    title: "Rennes assos",
    secteur: "association",
    ville: "Rennes",
    rayon_km: 15,
    tag: "volume",
  },
  {
    title: "Rennes restos",
    secteur: "restaurant",
    ville: "Rennes",
    rayon_km: 10,
    tag: "dense",
  },
  {
    title: "Rennes coiffeurs",
    secteur: "coiffeur",
    ville: "Rennes",
    rayon_km: 10,
    tag: "local",
  },
  {
    title: "Rennes artisans",
    secteur: "plombier",
    ville: "Rennes",
    rayon_km: 18,
    tag: "B2B",
  },
  {
    title: "Nantes restos",
    secteur: "restaurant",
    ville: "Nantes",
    rayon_km: 10,
    tag: "dense",
  },
  {
    title: "Nantes assos",
    secteur: "association",
    ville: "Nantes",
    rayon_km: 15,
    tag: "volume",
  },
  {
    title: "Angers commerces",
    secteur: "fleuriste",
    ville: "Angers",
    rayon_km: 12,
    tag: "vitrine",
  },
  {
    title: "Saint-Malo restos",
    secteur: "restaurant",
    ville: "Saint-Malo",
    rayon_km: 12,
    tag: "tourisme",
  },
  {
    title: "Combourg large",
    secteur: "boulangerie",
    ville: "Combourg",
    rayon_km: 25,
    tag: "local",
  },
];

const EMPTY_FORM = { secteur: "association", ville: "Rennes", rayon_km: 15 };

const campaignPayload = (data) => ({
  secteur: data.secteur,
  ville: data.ville.trim(),
  rayon_km: Number(data.rayon_km),
});

const apiErrorMessage = (err, fallback) => {
  const data = err.response?.data;
  if (!data) return fallback;
  if (typeof data === "string") return data.slice(0, 240);
  if (data.error) return data.error;
  if (data.detail) return data.detail;

  const fieldErrors = Object.entries(data)
    .map(([field, message]) => `${field}: ${Array.isArray(message) ? message.join(", ") : message}`)
    .join(" ");

  return fieldErrors || fallback;
};

export default function Campaigns() {
  const [campaigns, setCampaigns] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [loading, setLoading] = useState(true);
  const [launching, setLaunching] = useState(null);
  const [presetBusy, setPresetBusy] = useState("");
  const [error, setError] = useState("");

  const load = (options = {}) =>
    getCampaigns(options)
      .then((data) => {
        setCampaigns(data);
        setError("");
      })
      .catch((err) => {
        console.error("Campaigns load error", err);
        setCampaigns([]);
        setError(apiErrorMessage(err, "Impossible de charger les campagnes."));
      })
      .finally(() => setLoading(false));

  useEffect(() => {
    load();
  }, []);

  const refreshAfterLaunch = () => {
    load({ force: true });
    setTimeout(() => load({ force: true }), 5000);
    setTimeout(() => load({ force: true }), 15000);
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    setError("");

    try {
      await createCampaign(campaignPayload(form));
      setShowForm(false);
      setForm(EMPTY_FORM);
      load({ force: true });
    } catch (err) {
      setError(apiErrorMessage(err, "Erreur lors de la creation."));
    }
  };

  const handlePreset = async (preset, launch = false) => {
    const busyKey = `${preset.title}:${launch ? "launch" : "create"}`;
    setPresetBusy(busyKey);
    setError("");

    try {
      const created = await createCampaign(campaignPayload(preset));
      if (launch) {
        const result = await launchCampaign(created.id);
        if (result.demo_blocked) {
          await load({ force: true });
          setError(result.message);
          return;
        }
        refreshAfterLaunch();
      } else {
        load({ force: true });
      }
    } catch (err) {
      setError(apiErrorMessage(err, "Impossible de lancer ce raccourci."));
    } finally {
      setPresetBusy("");
    }
  };

  const applyPresetToForm = (preset) => {
    setForm(campaignPayload(preset));
    setShowForm(true);
    setError("");
  };

  const handleLaunch = async (id) => {
    setError("");
    setLaunching(id);

    try {
      const result = await launchCampaign(id);
      if (result.demo_blocked) {
        await load({ force: true });
        setError(result.message);
        return;
      }
      if (result.status === "running") {
        refreshAfterLaunch();
        return;
      }
      if (result.status === "error" || result.error) {
        setError(result.error ?? "Prospection interrompue.");
        load({ force: true });
        return;
      }
      load({ force: true });
    } catch (err) {
      setError(apiErrorMessage(err, "Erreur lors du lancement."));
      load({ force: true });
    } finally {
      setLaunching(null);
    }
  };

  const handleDelete = async (id) => {
    setError("");
    if (!confirm("Supprimer cette campagne et tous ses prospects ?")) return;

    try {
      await deleteCampaign(id);
      load({ force: true });
    } catch (err) {
      console.error("Campaign delete error", err);
      setError(apiErrorMessage(err, "Impossible de supprimer cette campagne."));
    }
  };

  return (
    <div className="p-8 space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-slate-800">Campagnes</h2>
          <p className="text-slate-500 text-sm mt-1">
            Presets rapides et prospection par secteur
          </p>
        </div>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
        >
          + Nouvelle campagne
        </button>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <section className="space-y-3">
        <div className="flex items-center justify-between gap-3">
          <h3 className="font-semibold text-slate-700">Recherches pretes</h3>
          <p className="text-xs text-slate-500">Rayons 10-25 km</p>
        </div>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {CAMPAIGN_PRESETS.map((preset) => {
            const createKey = `${preset.title}:create`;
            const launchKey = `${preset.title}:launch`;
            const isBusy = presetBusy === createKey || presetBusy === launchKey;

            return (
              <div
                key={preset.title}
                className="rounded-xl border border-slate-200 bg-white p-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-semibold text-slate-800">{preset.title}</p>
                    <p className="mt-1 text-xs text-slate-500">
                      {preset.secteur} - {preset.ville} - {preset.rayon_km} km
                    </p>
                  </div>
                  <span className="rounded-full border border-slate-200 px-2 py-0.5 text-[11px] text-blue-600">
                    {preset.tag}
                  </span>
                </div>
                <div className="mt-4 grid grid-cols-3 gap-2">
                  <button
                    type="button"
                    onClick={() => applyPresetToForm(preset)}
                    className="rounded border border-slate-200 px-2 py-1.5 text-xs text-slate-300 hover:bg-slate-800"
                  >
                    Ajuster
                  </button>
                  <button
                    type="button"
                    onClick={() => handlePreset(preset)}
                    disabled={isBusy}
                    className="rounded border border-slate-200 px-2 py-1.5 text-xs text-slate-300 hover:bg-slate-800 disabled:opacity-50"
                  >
                    Creer
                  </button>
                  <button
                    type="button"
                    onClick={() => handlePreset(preset, true)}
                    disabled={isBusy}
                    className="rounded bg-green-600 px-2 py-1.5 text-xs font-medium text-white hover:bg-green-700 disabled:opacity-50"
                  >
                    {presetBusy === launchKey ? "Lancement..." : "Lancer"}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {showForm && (
        <form
          onSubmit={handleCreate}
          className="bg-white border border-slate-200 rounded-xl p-6 space-y-4"
        >
          <h3 className="font-semibold text-slate-700">Nouvelle campagne</h3>
          <div className="grid gap-4 md:grid-cols-3">
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">
                Secteur d'activite
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
                placeholder="Rennes, Nantes, Angers..."
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
                max={30}
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
              Creer
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

      {loading ? (
        <p className="text-slate-400 text-sm">Chargement...</p>
      ) : campaigns.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-200 p-12 text-center text-slate-400 text-sm">
          Aucune campagne. Lance un preset pour commencer.
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
                          {launching === c.id ? "Scraping..." : "Lancer"}
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
                        x
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
