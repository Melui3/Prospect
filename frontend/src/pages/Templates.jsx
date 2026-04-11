import { useEffect, useState } from "react";
import { getTemplates, createTemplate, updateTemplate, deleteTemplate } from "../api/client";

const EMPTY_FORM = { name: "", subject: "", body: "" };

const HELP_TEXT = `Variables disponibles dans le sujet et le corps :
  {nom}     → Nom du commerce
  {ville}   → Ville du prospect
  {secteur} → Secteur d'activité`;

const DEFAULT_TEMPLATE = {
  name: "Premier contact",
  subject: "Bonjour {nom} — Je peux créer votre site web",
  body: `Bonjour,

Je me permets de vous contacter car j'ai remarqué que {nom} à {ville} n'a pas encore de présence en ligne.

En tant que développeur web, je crée des sites professionnels pour les {secteur}s locaux : rapides, modernes et optimisés pour Google.

Seriez-vous intéressé(e) par un devis gratuit et sans engagement ?

Cordialement,
[Votre nom]`,
};

export default function Templates() {
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null); // null | "new" | {id, ...}
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

  const load = () =>
    getTemplates()
      .then(setTemplates)
      .finally(() => setLoading(false));

  useEffect(() => { load(); }, []);

  const openNew = () => {
    setForm(DEFAULT_TEMPLATE);
    setEditing("new");
  };

  const openEdit = (t) => {
    setForm({ name: t.name, subject: t.subject, body: t.body });
    setEditing(t);
  };

  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      if (editing === "new") {
        await createTemplate(form);
      } else {
        await updateTemplate(editing.id, form);
      }
      setEditing(null);
      load();
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id) => {
    if (!confirm("Supprimer ce template ?")) return;
    await deleteTemplate(id);
    load();
  };

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-800">Templates email</h2>
          <p className="text-slate-500 text-sm mt-1">
            Créez vos modèles d'email avec variables dynamiques
          </p>
        </div>
        <button
          onClick={openNew}
          className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
        >
          + Nouveau template
        </button>
      </div>

      {/* Variables help */}
      <div className="bg-blue-50 border border-blue-100 rounded-xl p-4">
        <pre className="text-xs text-blue-700 whitespace-pre-wrap">{HELP_TEXT}</pre>
      </div>

      {/* Form */}
      {editing && (
        <form
          onSubmit={handleSave}
          className="bg-white border border-slate-200 rounded-xl p-6 space-y-4"
        >
          <h3 className="font-semibold text-slate-700">
            {editing === "new" ? "Nouveau template" : `Modifier : ${editing.name}`}
          </h3>

          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">
              Nom du template
            </label>
            <input
              required
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              placeholder="Premier contact"
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">
              Sujet
            </label>
            <input
              required
              value={form.subject}
              onChange={(e) => setForm((f) => ({ ...f, subject: e.target.value }))}
              placeholder="Bonjour {nom} — Je peux créer votre site web"
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">
              Corps de l'email
            </label>
            <textarea
              required
              rows={10}
              value={form.body}
              onChange={(e) => setForm((f) => ({ ...f, body: e.target.value }))}
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"
            />
          </div>

          <div className="flex gap-3">
            <button
              type="submit"
              disabled={saving}
              className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm font-medium"
            >
              {saving ? "Sauvegarde…" : "Sauvegarder"}
            </button>
            <button
              type="button"
              onClick={() => setEditing(null)}
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
      ) : templates.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-200 p-12 text-center text-slate-400 text-sm">
          Aucun template. Créez-en un pour commencer à envoyer des emails.
        </div>
      ) : (
        <div className="space-y-3">
          {templates.map((t) => (
            <div
              key={t.id}
              className="bg-white border border-slate-200 rounded-xl p-5 flex items-start justify-between gap-4"
            >
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-slate-800">{t.name}</p>
                <p className="text-sm text-slate-500 mt-0.5">{t.subject}</p>
                <p className="text-xs text-slate-400 mt-2 line-clamp-2 whitespace-pre-wrap">
                  {t.body}
                </p>
              </div>
              <div className="flex gap-2 shrink-0">
                <button
                  onClick={() => openEdit(t)}
                  className="text-slate-500 hover:text-blue-600 text-xs border border-slate-200 hover:border-blue-300 px-3 py-1.5 rounded-lg transition-colors"
                >
                  Modifier
                </button>
                <button
                  onClick={() => handleDelete(t.id)}
                  className="text-slate-400 hover:text-red-500 text-xs border border-slate-200 hover:border-red-200 px-3 py-1.5 rounded-lg transition-colors"
                >
                  Supprimer
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
