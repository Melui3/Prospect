import { Outlet, NavLink, useNavigate } from "react-router-dom";
import { logout } from "../api/client";

const navItems = [
  { to: "/dashboard", label: "Dashboard", icon: "📊" },
  { to: "/campaigns", label: "Campagnes", icon: "🚀" },
  { to: "/prospects", label: "Prospects", icon: "🎯" },
  { to: "/templates", label: "Templates email", icon: "✉️" },
];

export default function Layout() {
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate("/login", { replace: true });
  }

  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
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
              <span>{icon}</span>
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="px-6 py-4 border-t border-slate-700 flex items-center justify-between">
          <span className="text-xs text-slate-500">OSM + Pages Jaunes</span>
          <button
            onClick={handleLogout}
            className="text-xs text-slate-400 hover:text-white transition-colors"
          >
            Déconnexion
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
