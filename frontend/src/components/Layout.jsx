import { useEffect, useState } from "react";
import { Outlet, NavLink } from "react-router-dom";
import {
  DESKTOP_APP,
  clearOwnerApiFailed,
  clearOwnerToken,
  enterDemoMode,
  exitDemoMode,
  getOwnerApiFailed,
  getSession,
  setOwnerToken,
} from "../api/client";

const navItems = [
  { to: "/dashboard", label: "Dashboard", icon: "DB" },
  { to: "/campaigns", label: "Campagnes", icon: "CA" },
  { to: "/prospects", label: "Prospects", icon: "PR" },
  { to: "/templates", label: "Templates email", icon: "TE" },
];

const hasDemoIntent = () => {
  const search = new URLSearchParams(window.location.search);
  return search.get("demo") === "1" || window.location.hash.includes("demo=1");
};

export default function Layout() {
  const [session, setSession] = useState(null);
  const [unlockError, setUnlockError] = useState("");
  const [ownerApiFailed, setOwnerApiFailed] = useState(getOwnerApiFailed());

  const refreshSession = (options = {}) =>
    getSession(options)
      .then(setSession)
      .catch(() =>
        setSession({
          mode: "locked",
          is_owner: false,
          is_demo: false,
          auth_required: true,
          demo_available: false,
        })
      );

  useEffect(() => {
    if (!DESKTOP_APP && hasDemoIntent()) {
      enterDemoMode();
    }
    refreshSession({ force: true });
  }, []);

  const handleUnlock = async () => {
    const token = window.prompt("Token prive");
    const trimmedToken = token?.trim();
    if (!trimmedToken) return;

    setUnlockError("");
    clearOwnerApiFailed();
    setOwnerApiFailed("");
    setOwnerToken(trimmedToken);

    try {
      const nextSession = await getSession({ force: true });
      if (nextSession.is_owner) {
        setSession(nextSession);
        return;
      }

      clearOwnerToken();
      setSession(nextSession);
      setUnlockError("Token invalide");
    } catch (err) {
      console.error("Owner token validation error", err);
      clearOwnerToken();
      setUnlockError("Validation impossible pour le moment");
    }
  };

  const handleEnterDemo = async () => {
    setUnlockError("");
    clearOwnerApiFailed();
    setOwnerApiFailed("");
    enterDemoMode();

    try {
      const nextSession = await getSession({ force: true });
      if (nextSession.is_demo) {
        setSession(nextSession);
        return;
      }

      exitDemoMode();
      setSession(nextSession);
      setUnlockError("La demo anonymisee n'est pas activee pour le moment");
    } catch (err) {
      console.error("Demo session error", err);
      exitDemoMode();
      setUnlockError("Demo indisponible pour le moment");
    }
  };

  const handleLock = async () => {
    clearOwnerApiFailed();
    clearOwnerToken();
    setOwnerApiFailed("");
    await refreshSession({ force: true });
  };

  const handleExitDemo = async () => {
    exitDemoMode();
    await refreshSession({ force: true });
  };

  const isOwner = session?.is_owner;
  const isDemo = session?.is_demo || session?.mode === "demo";
  const isLocked = Boolean(session && session.mode === "locked");
  const demoAvailable = Boolean(session?.demo_available);
  const sessionTitle = !session
    ? "Verification"
    : isDemo
      ? "Mode demo"
      : isOwner
        ? "Session privee"
        : "Verrouille";
  const sessionSubtitle = !session
    ? "Controle en cours"
    : isDemo
      ? "Donnees anonymisees"
      : isOwner
        ? "Donnees reelles"
        : demoAvailable
          ? "Demo disponible"
          : "Token requis";

  return (
    <div className="flex min-h-screen">
      <aside className="w-60 bg-slate-900 text-white flex flex-col">
        <div className="px-6 py-5 border-b border-slate-700">
          <h1 className="text-xl font-bold tracking-tight">Prospect</h1>
          <p className="text-xs text-slate-400 mt-0.5">Outil interne de prospection</p>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-1">
          {navItems.map(({ to, label, icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-blue-600 text-white"
                    : "text-slate-300 hover:bg-slate-700 hover:text-white"
                }`
              }
            >
              <span className="w-6 text-[10px] font-bold tracking-wide text-center">
                {icon}
              </span>
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="px-4 py-4 border-t border-slate-700 space-y-3">
          <div>
            <p className="text-xs font-medium text-slate-200">{sessionTitle}</p>
            <p className="text-[11px] text-slate-500 mt-0.5">{sessionSubtitle}</p>
          </div>

          {ownerApiFailed && (
            <p className="rounded border border-amber-500/30 bg-amber-500/10 px-2 py-1.5 text-[11px] leading-snug text-amber-100">
              {ownerApiFailed}
            </p>
          )}
          {unlockError && <p className="text-[11px] text-red-300">{unlockError}</p>}

          {isLocked && demoAvailable && (
            <button
              type="button"
              onClick={handleEnterDemo}
              className="w-full rounded bg-blue-600 px-2 py-1.5 text-xs font-medium text-white hover:bg-blue-700"
            >
              Voir la demo
            </button>
          )}

          {isLocked && (
            <button
              type="button"
              onClick={handleUnlock}
              className="w-full rounded border border-slate-700 px-2 py-1.5 text-xs text-slate-300 hover:bg-slate-800"
            >
              Acces prive
            </button>
          )}

          {isOwner && session.auth_required && (
            <button
              type="button"
              onClick={handleLock}
              className="w-full rounded border border-slate-700 px-2 py-1.5 text-xs text-slate-300 hover:bg-slate-800"
            >
              Verrouiller
            </button>
          )}

          {isDemo && !session.static_demo && (
            <button
              type="button"
              onClick={handleExitDemo}
              className="w-full rounded border border-slate-700 px-2 py-1.5 text-xs text-slate-300 hover:bg-slate-800"
            >
              Quitter la demo
            </button>
          )}
        </div>
      </aside>

      <main className="flex-1 overflow-auto">
        {!session ? (
          <div className="flex min-h-screen items-center justify-center px-8">
            <p className="text-sm text-slate-400">Verification de la session...</p>
          </div>
        ) : isLocked ? (
          <div className="flex min-h-screen items-center justify-center px-8 py-10">
            <div className="w-full max-w-5xl space-y-6">
              <div className="rounded-xl border border-slate-200 bg-white p-8">
                <p className="text-xs uppercase tracking-wide text-blue-600">
                  Prospect - outil interne de prospection
                </p>
                <h2 className="mt-3 max-w-3xl text-4xl font-bold leading-tight text-slate-800">
                  Une app pour trouver, qualifier et suivre des prospects locaux sans exposer mes donnees reelles.
                </h2>
                <p className="mt-4 max-w-3xl text-sm leading-6 text-slate-500">
                  Prospect centralise le workflow de prospection: lancer une recherche par secteur,
                  ville et rayon, enrichir les fiches avec site, email et telephone, filtrer les
                  contacts utiles, preparer des templates personnalises et suivre les relances.
                  La version publique ci-dessous montre la logique produit avec des entreprises
                  anonymisees et des actions sensibles simulees.
                </p>

                <div className="mt-6 grid gap-3 md:grid-cols-4">
                  {[
                    "Recherches locales par secteur",
                    "Qualification email/site/statut",
                    "Templates avec variables",
                    "Dashboard de suivi",
                  ].map((item) => (
                    <div key={item} className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-300">
                      {item}
                    </div>
                  ))}
                </div>

                <div className="mt-7 flex flex-wrap gap-3">
                  <button
                    type="button"
                    onClick={handleEnterDemo}
                    disabled={!demoAvailable}
                    className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                  >
                    Voir la demo anonymisee
                  </button>
                  <button
                    type="button"
                    onClick={handleUnlock}
                    className="rounded-lg border border-slate-200 px-4 py-2 text-sm text-slate-300 hover:bg-slate-800"
                  >
                    Entrer dans l'outil prive
                  </button>
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-3">
                <div className="rounded-xl border border-slate-200 bg-white p-5">
                  <p className="font-semibold text-slate-800">Ce que la demo montre</p>
                  <p className="mt-2 text-sm leading-6 text-slate-500">
                    L'interface complete, les filtres, les campagnes pretes, les prospects
                    anonymises et les apercus d'emails.
                  </p>
                </div>
                <div className="rounded-xl border border-slate-200 bg-white p-5">
                  <p className="font-semibold text-slate-800">Ce qui est bloque</p>
                  <p className="mt-2 text-sm leading-6 text-slate-500">
                    Aucun email reel, aucun scraping externe, aucune suppression ou sauvegarde
                    durable depuis l'acces public.
                  </p>
                </div>
                <div className="rounded-xl border border-slate-200 bg-white p-5">
                  <p className="font-semibold text-slate-800">Ce qui reste prive</p>
                  <p className="mt-2 text-sm leading-6 text-slate-500">
                    Ma vraie base de prospects, mes templates operationnels et les actions de
                    prospection reelles restent derriere le token.
                  </p>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <>
            {isDemo && (
              <div className="border-b border-slate-200 bg-blue-50 px-8 py-3 text-sm text-blue-700">
                Demo anonymisee: les donnees sont fictives, les emails ne partent pas et les actions sont simulees.
              </div>
            )}
            <Outlet />
          </>
        )}
      </main>
    </div>
  );
}
