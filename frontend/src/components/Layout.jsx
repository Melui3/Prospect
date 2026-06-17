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

  useEffect(() => {
    getSession().then(setSession).catch(() => setSession({ mode: "demo", is_owner: false }));
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
      const nextSession = await getSession();
      if (nextSession.is_owner) {
        window.location.reload();
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

  const handleLock = () => {
    clearOwnerApiFailed();
    clearOwnerToken();
    window.location.reload();
  };

  const isOwner = session?.is_owner;
  const demoEnabled = session?.demo_enabled;
  const sessionTitle = !session
    ? "Chargement"
    : !demoEnabled
      ? "Protection inactive"
      : isOwner
        ? "Session privee"
        : "Mode demo";
  const sessionSubtitle = !session
    ? "Verification en cours"
    : !demoEnabled
      ? "OWNER_ACCESS_TOKEN absent"
      : isOwner
        ? "Donnees reelles"
        : "Donnees publiques fictives";

  return (
    <div className="flex min-h-screen">
      <aside className="w-60 bg-slate-900 text-white flex flex-col">
        <div className="px-6 py-5 border-b border-slate-700">
          <h1 className="text-xl font-bold tracking-tight">ProspectApp</h1>
          <p className="text-xs text-slate-400 mt-0.5">Trouvez vos prochains clients</p>
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
            <p className="text-xs font-medium text-slate-200">
              {sessionTitle}
            </p>
            <p className="text-[11px] text-slate-500 mt-0.5">
              {sessionSubtitle}
            </p>
          </div>

          {demoEnabled && !isOwner && (
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
                Acces prive
              </button>
            </div>
          )}

          {demoEnabled && isOwner && (
            <button
              type="button"
              onClick={handleLock}
              className="w-full rounded border border-slate-700 px-2 py-1.5 text-xs text-slate-300 hover:bg-slate-800"
            >
              Repasser en demo
            </button>
          )}

          {!demoEnabled && (
            <p className="text-xs text-slate-500">
              Ajoute la variable sur le backend pour activer la demo publique.
            </p>
          )}
        </div>
      </aside>

      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
