import { useEffect, useState } from "react";
import { Outlet, NavLink } from "react-router-dom";
import {
  clearOwnerApiFailed,
  clearOwnerToken,
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
          auth_required: true,
        })
      );

  useEffect(() => {
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

  const handleLock = async () => {
    clearOwnerApiFailed();
    clearOwnerToken();
    setOwnerApiFailed("");
    await refreshSession({ force: true });
  };

  const isOwner = session?.is_owner;
  const authRequired = session?.mode === "locked" || Boolean(session?.auth_required);
  const isLocked = Boolean(session && authRequired && !isOwner);
  const sessionTitle = !session
    ? "Verification"
    : !authRequired
      ? "Acces local"
      : isOwner
        ? "Session privee"
        : "Verrouille";
  const sessionSubtitle = !session
    ? "Controle en cours"
    : !authRequired
      ? "Token non requis"
      : isOwner
        ? "Donnees reelles"
        : "Token requis";

  return (
    <div className="flex min-h-screen">
      <aside className="w-60 bg-slate-900 text-white flex flex-col">
        <div className="px-6 py-5 border-b border-slate-700">
          <h1 className="text-xl font-bold tracking-tight">ProspectApp</h1>
          <p className="text-xs text-slate-400 mt-0.5">Prospection privee</p>
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

          {authRequired && !isOwner && (
            <div className="space-y-2">
              {ownerApiFailed && (
                <p className="rounded border border-amber-500/30 bg-amber-500/10 px-2 py-1.5 text-[11px] leading-snug text-amber-100">
                  {ownerApiFailed}
                </p>
              )}
              {unlockError && <p className="text-[11px] text-red-300">{unlockError}</p>}
              <button
                type="button"
                onClick={handleUnlock}
                className="w-full rounded bg-blue-600 px-2 py-1.5 text-xs font-medium text-white hover:bg-blue-700"
              >
                Deverrouiller
              </button>
            </div>
          )}

          {authRequired && isOwner && (
            <button
              type="button"
              onClick={handleLock}
              className="w-full rounded border border-slate-700 px-2 py-1.5 text-xs text-slate-300 hover:bg-slate-800"
            >
              Verrouiller
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
          <div className="flex min-h-screen items-center justify-center px-8">
            <div className="w-full max-w-md rounded-xl border border-slate-200 bg-white p-6 text-center">
              <p className="text-xs uppercase tracking-wide text-blue-600">Acces prive</p>
              <h2 className="mt-2 text-2xl font-bold text-slate-800">
                Outil verrouille
              </h2>
              <p className="mt-2 text-sm text-slate-500">
                Entre ton token pour charger tes vraies campagnes, prospects et templates.
              </p>
              {unlockError && <p className="mt-3 text-sm text-red-500">{unlockError}</p>}
              <button
                type="button"
                onClick={handleUnlock}
                className="mt-5 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
              >
                Entrer le token
              </button>
            </div>
          </div>
        ) : (
          <Outlet />
        )}
      </main>
    </div>
  );
}
