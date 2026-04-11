import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  getProspects,
  getCampaigns,
  getTemplates,
  sendProspectEmail,
  updateProspect,
} from "../api/client";
import Badge from "../components/Badge";

const STATUS_OPTIONS = [
  { value: "", label: "Tous les statuts" },
  { value: "new", label: "Nouveaux" },
  { value: "contacted", label: "Contactés" },
  { value: "replied", label: "Répondus" },
  { value: "ignored", label: "Ignorés" },
];

export default function Prospects() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [prospects, setProspects] = useState([]);
  const [campaigns, setCampaigns] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [sendingId, setSendingId] = useState(null);

  // Filtres
  const [filterCampaign, setFilterCampaign] = useState(searchParams.get("campaign") ?? "");
  const [filterStatus, setFilterStatus] = useState("");
  const [filterEmail, setFilterEmail] = useState("");

  // Modal d'envoi email
  const [emailModal, setEmailModal] = useState(null); // prospect
  const [selectedTemplate, setSelectedTemplate] = useState("");

  const loadProspects = () => {
    const params = {};
    if (filterCampaign) params.campaign = filterCampaign;
    if (filterStatus) params.status = filterStatus;
    if (filterEmail) params.has_email = filterEmail;

    return getProspects(params)
      .then(setProspects)
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    Promise.all([getCampaigns(), getTemplates()]).then(([c, t]) => {
      setCampaigns(c);
      setTemplates(t);
      if (t.length > 0) setSelectedTemplate(String(t[0].id));
    });
  }, []);

  useEffect(() => {
    loadProspects();
  }, [filterCampaign, filterStatus, filterEmail]);

  const handleSendEmail = async () => {
    if (!selectedTemplate || !emailModal) return;
    setSendingId(emailModal.id);
    try {
      await sendProspectEmail(emailModal.id, Number(selectedTemplate));
      alert(`✅ Email envoyé à ${emailModal.email} !`);
      setEmailModal(null);
      loadProspects();
    } catch (err) {
      const msg = err.response?.data?.error ?? "Erreur d'envoi.";
      alert(`❌ ${msg}`);
    } finally {
      setSendingId(null);
    }
  };

  const handleStatusChange = async (prospect, newStatus) => {
    await updateProspect(prospect.id, { status: newStatus });
    setProspects((prev) =>
      prev.map((p) => (p.id === prospect.id ? { ...p, status: newStatus } : p))
    );
  };

  return (
    <div className="p-8 space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-800">Prospects</h2>
        <p className="text-slate-500 text-sm mt-1">
          {prospects.length} résultat{prospects.length !== 1 ? "s" : ""}
        </p>
      </div>

      {/* Filtres */}
      <div className="flex flex-wrap gap-3">
        <select
          value={filterCampaign}
          onChange={(e) => setFilterCampaign(e.target.value)}
          className="border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
        >
          <option value="">Toutes les campagnes</option>
          {campaigns.map((c) => (
            <option key={c.id} value={c.id}>
              {c.secteur} — {c.ville}
            </option>
          ))}
        </select>

        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          className="border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
        >
          {STATUS_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>

        <select
          value={filterEmail}
          onChange={(e) => setFilterEmail(e.target.value)}
          className="border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
        >
          <option value="">Tous</option>
          <option value="true">Avec email</option>
          <option value="false">Sans email</option>
        </select>
      </div>

      {/* Table */}
      {loading ? (
        <p className="text-slate-400 text-sm">Chargement…</p>
      ) : prospects.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-200 p-12 text-center text-slate-400 text-sm">
          Aucun prospect trouvé. Lancez une campagne d'abord.
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-500 uppercase text-xs">
              <tr>
                <th className="px-4 py-3 text-left">Nom</th>
                <th className="px-4 py-3 text-left">Ville</th>
                <th className="px-4 py-3 text-left">Email</th>
                <th className="px-4 py-3 text-left">Téléphone</th>
                <th className="px-4 py-3 text-left">Secteur</th>
                <th className="px-4 py-3 text-left">Statut</th>
                <th className="px-4 py-3 text-right">Emails envoyés</th>
                <th className="px-4 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {prospects.map((p) => (
                <tr key={p.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-medium">{p.nom}</td>
                  <td className="px-4 py-3 text-slate-500">{p.ville}</td>
                  <td className="px-4 py-3">
                    {p.email ? (
                      <a
                        href={`mailto:${p.email}`}
                        className="text-blue-600 hover:underline"
                      >
                        {p.email}
                      </a>
                    ) : (
                      <span className="text-slate-300 text-xs">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-slate-500 text-xs">
                    {p.telephone || "—"}
                  </td>
                  <td className="px-4 py-3 text-slate-500 capitalize text-xs">
                    {p.campaign_secteur}
                  </td>
                  <td className="px-4 py-3">
                    <select
                      value={p.status}
                      onChange={(e) => handleStatusChange(p, e.target.value)}
                      className="text-xs border-0 bg-transparent focus:outline-none cursor-pointer"
                    >
                      <option value="new">Nouveau</option>
                      <option value="contacted">Contacté</option>
                      <option value="replied">Répondu</option>
                      <option value="ignored">Ignoré</option>
                    </select>
                  </td>
                  <td className="px-4 py-3 text-right text-slate-500">
                    {p.emails_sent > 0 ? (
                      <span className="text-blue-600 font-medium">{p.emails_sent}</span>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {p.email ? (
                      <button
                        onClick={() => setEmailModal(p)}
                        disabled={sendingId === p.id}
                        className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white px-3 py-1 rounded text-xs font-medium transition-colors"
                      >
                        {sendingId === p.id ? "Envoi…" : "Envoyer email"}
                      </button>
                    ) : (
                      <span className="text-slate-300 text-xs">Pas d'email</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Modal envoi email */}
      {emailModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg mx-4 p-6 space-y-4">
            <h3 className="font-bold text-slate-800 text-lg">
              Envoyer un email à {emailModal.nom}
            </h3>
            <p className="text-sm text-slate-500">
              Destinataire :{" "}
              <span className="font-medium text-slate-700">{emailModal.email}</span>
            </p>

            {templates.length === 0 ? (
              <p className="text-sm text-orange-600 bg-orange-50 rounded-lg p-3">
                Aucun template configuré. Créez-en un dans l'onglet "Templates email".
              </p>
            ) : (
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">
                  Template à utiliser
                </label>
                <select
                  value={selectedTemplate}
                  onChange={(e) => setSelectedTemplate(e.target.value)}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {templates.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name} — {t.subject}
                    </option>
                  ))}
                </select>
                {selectedTemplate && (
                  <div className="mt-3 p-3 bg-slate-50 rounded-lg text-xs text-slate-500">
                    <p className="font-medium text-slate-600 mb-1">Aperçu sujet :</p>
                    <p>
                      {templates
                        .find((t) => String(t.id) === selectedTemplate)
                        ?.subject.replace("{nom}", emailModal.nom)
                        .replace("{ville}", emailModal.ville)
                        .replace("{secteur}", emailModal.campaign_secteur)}
                    </p>
                  </div>
                )}
              </div>
            )}

            <div className="flex gap-3 pt-2">
              <button
                onClick={handleSendEmail}
                disabled={!selectedTemplate || sendingId === emailModal.id}
                className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white py-2 rounded-lg text-sm font-medium transition-colors"
              >
                {sendingId === emailModal.id ? "Envoi en cours…" : "Envoyer"}
              </button>
              <button
                onClick={() => setEmailModal(null)}
                className="flex-1 border border-slate-200 hover:bg-slate-50 py-2 rounded-lg text-sm text-slate-600 transition-colors"
              >
                Annuler
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
