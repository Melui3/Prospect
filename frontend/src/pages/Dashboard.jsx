import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getStats, getCampaigns } from "../api/client";
import StatCard from "../components/StatCard";
import Badge from "../components/Badge";

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [campaigns, setCampaigns] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getStats(), getCampaigns()])
      .then(([s, c]) => {
        setStats(s);
        setCampaigns(c.slice(0, 5));
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 text-slate-400">
        Chargement…
      </div>
    );
  }

  return (
    <div className="p-8 space-y-8">
      <div>
        <h2 className="text-2xl font-bold text-slate-800">Dashboard</h2>
        <p className="text-slate-500 text-sm mt-1">Vue d'ensemble de votre prospection</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Campagnes lancées"
          value={stats?.done_campaigns}
          sub={`${stats?.total_campaigns} au total`}
          color="blue"
        />
        <StatCard
          label="Prospects trouvés"
          value={stats?.total_prospects}
          sub={`${stats?.prospects_with_email} avec email`}
          color="green"
        />
        <StatCard
          label="Emails envoyés"
          value={stats?.emails_sent}
          sub={`${stats?.prospects_contacted} contactés`}
          color="orange"
        />
        <StatCard
          label="Réponses reçues"
          value={stats?.prospects_replied}
          sub={
            stats?.emails_sent > 0
              ? `${Math.round((stats.prospects_replied / stats.emails_sent) * 100)}% taux`
              : "—"
          }
          color="purple"
        />
      </div>

      {/* Dernières campagnes */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-semibold text-slate-700">Dernières campagnes</h3>
          <Link to="/campaigns" className="text-sm text-blue-600 hover:underline">
            Voir tout →
          </Link>
        </div>

        {campaigns.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-200 p-8 text-center text-slate-400 text-sm">
            Aucune campagne pour l'instant.{" "}
            <Link to="/campaigns" className="text-blue-600 hover:underline">
              Créer la première →
            </Link>
          </div>
        ) : (
          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-slate-500 uppercase text-xs">
                <tr>
                  <th className="px-4 py-3 text-left">Secteur</th>
                  <th className="px-4 py-3 text-left">Ville</th>
                  <th className="px-4 py-3 text-left">Statut</th>
                  <th className="px-4 py-3 text-right">Prospects</th>
                  <th className="px-4 py-3 text-right">Avec email</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {campaigns.map((c) => (
                  <tr key={c.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 font-medium capitalize">{c.secteur}</td>
                    <td className="px-4 py-3 text-slate-500">{c.ville}</td>
                    <td className="px-4 py-3">
                      <Badge value={c.status} />
                    </td>
                    <td className="px-4 py-3 text-right">{c.total_prospects}</td>
                    <td className="px-4 py-3 text-right text-green-600">
                      {c.prospects_with_email}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
