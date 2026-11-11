import { useEffect, useState } from "react";
import { HashRouter, Navigate, NavLink, Outlet, Route, Routes } from "react-router-dom";
import { CalendarDays, Users, Radar, Mail, Settings, LockKeyhole, CheckCircle2 } from "lucide-react";
import { clearOwnerToken, getSession, setOwnerToken } from "../api/client";
import Templates from "../pages/Templates";
import Today from "./Today";
import Contacts from "./Contacts";
import Campaigns from "./Campaigns";
import Qualification from "./Qualification";
import Preferences from "./Preferences";
import { Loading, Notice } from "./common";
import "./personal.css";

const nav = [["/dashboard", "Aujourd'hui", CalendarDays], ["/prospects", "Prospects", Users], ["/qualification", "Qualification", CheckCircle2], ["/campaigns", "Recherches", Radar], ["/templates", "Modeles email", Mail], ["/settings", "Reglages", Settings]];

function Layout() {
  const [session, setSession] = useState(null);
  const [error, setError] = useState("");
  const [token, setToken] = useState("");
  const refresh = () => getSession({ force: true }).then(setSession).catch(() => setError("Le service local ne repond pas."));
  useEffect(() => { refresh(); }, []);
  const unlock = async (event) => {
    event.preventDefault();
    setOwnerToken(token.trim());
    try {
      const next = await getSession({ force: true });
      if (!next.is_owner) { clearOwnerToken(); setError("Acces refuse."); } else { setSession(next); setError(""); setToken(""); }
    } catch { clearOwnerToken(); setError("Le service local ne repond pas."); }
  };
  return <div className="personal">
    <aside className="p-sidebar">
      <div className="p-brand"><img src={`${import.meta.env.BASE_URL}prospect-favicon.svg`} alt="" /><div><strong>Prospect</strong><span>Espace personnel</span></div></div>
      <nav>{nav.map(([to, label, Icon]) => <NavLink key={to} to={to}><Icon size={18} /><span>{label}</span></NavLink>)}</nav>
      <div className="p-session"><LockKeyhole size={15} /><span>{session?.is_owner ? "Session privee" : "Acces prive"}</span>{session?.auth_required && session?.is_owner && <button title="Verrouiller" onClick={async () => { clearOwnerToken(); await refresh(); }}>Verrouiller</button>}</div>
    </aside>
    <main className="p-main">{!session ? <><Notice>{error}</Notice><Loading /></> : !session.is_owner ? <form className="p-unlock" onSubmit={unlock}><LockKeyhole size={30} /><h1>Acces personnel</h1><Notice>{error}</Notice><label>Token prive<input type="password" value={token} onChange={(e) => setToken(e.target.value)} required autoComplete="off" /></label><button className="p-button primary">Deverrouiller</button></form> : <Outlet />}</main>
  </div>;
}

export default function PersonalApp() {
  return <HashRouter><Routes><Route element={<Layout />}>
    <Route index element={<Navigate to="/dashboard" replace />} />
    <Route path="dashboard" element={<Today />} />
    <Route path="prospects" element={<Contacts />} />
    <Route path="qualification" element={<Qualification />} />
    <Route path="campaigns" element={<Campaigns />} />
    <Route path="templates" element={<Templates />} />
    <Route path="settings" element={<Preferences />} />
    <Route path="*" element={<Navigate to="/dashboard" replace />} />
  </Route></Routes></HashRouter>;
}
