import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getStats, getCampaigns, isDemoMode } from "../api/client";
import StatCard from "../components/StatCard";
import Badge from "../components/Badge";

const EMPTY_STATS = {
  done_campaigns: 0,
  total_campaigns: 0,
  total_prospects: 0,
  prospects_with_email: 0,
  emails_sent: 0,
  prospects_contacted: 0,
  prospects_replied: 0,
};

function DemoIntro() {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-6">
      <div className="max-w-4xl">
        <p className="text-xs uppercase tracking-wide text-blue-600">
          Prospect - outil interne de prospection
        </p>
        <h1 className="mt-2 text-3xl font-bold leading-tight text-slate-800">
          Rechercher, qualifier et suivre des prospects locaux depuis une seule interface.
        </h1>
        <p className="mt-3 text-sm leading-6 text-slate-500">
          Prospect est une application concue pour automatiser une partie de mon workflow
          de prospection commerciale. L'outil permet de lancer des recherches par secteur,
          ville et rayon, puis de centraliser les prospects trouves avec statut, email,
          site web, telephone et historique de contact.
        </p>
        <p className="mt-3 text-sm leading-6 text-slate-500">
          L'objectif est de gagner du temps sur les taches repetitives: reperer des
          entreprises ou associations locales, qualifier rapidement les contacts utiles,
          filtrer les prospects selon leur situation, preparer des templates d'email
          personnalises et suivre l'avancement des campagnes.
        </p>
      </div>

      <div className="mt-5 grid gap-3 md:grid-cols-3">
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
          <p className="font-semibold text-slate-800">Demo anonymisee</p>
          <p className="mt-1 text-sm leading-5 text-slate-500">
            Les entreprises, emails et statuts affiches ici sont fictifs.
          </p>
        </div>
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
          <p className="font-semibold text-slate-800">Actions sensibles bloquees</p>
          <p className="mt-1 text-sm leading-5 text-slate-500">
            Aucun email reel, scraping externe ou changement persistant n'est lance.
          </p>
        </div>
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
          <p className="font-semibold text-slate-800">Donnees privees protegees</p>
          <p className="mt-1 text-sm leading-5 text-slate-500">
            Ma vraie base de prospects reste separee et protegee par token.
          </p>
        </div>
      </div>
    </section>
  );
}

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [campaigns, setCampaigns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let isMounted = true;

    Promise.all([getStats(), getCampaigns()])
      .then(([s, c]) => {
        if (!isMounted) return;
        setStats(s);
        setCampaigns(c.slice(0, 5));
      })
      .catch((err) => {
        console.error("Dashboard load error", err);
        if (!isMounted) return;
        setStats(EMPTY_STATS);
        setCampaigns([]);
        setError("Impossible de charger les donnees du dashboard.");
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
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
      {isDemoMode() && <DemoIntro />}

      <div>
        <h2 className="text-2xl font-bold text-slate-800">Dashboard</h2>
        <p className="text-slate-500 text-sm mt-1">Vue d'ensemble de votre prospection</p>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

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
