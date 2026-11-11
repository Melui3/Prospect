import { HashRouter, Routes, Route, Navigate } from "react-router-dom";
import { lazy, Suspense } from "react";
import { STATIC_DEMO } from "./api/client";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import Campaigns from "./pages/Campaigns";
import Prospects from "./pages/Prospects";
import Templates from "./pages/Templates";
const PersonalApp = lazy(() => import("./personal/App"));

export default function App() {
  if (!STATIC_DEMO) {
    return <Suspense fallback={<div className="p-8">Chargement...</div>}><PersonalApp /></Suspense>;
  }
  return (
    <HashRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="campaigns" element={<Campaigns />} />
          <Route path="prospects" element={<Prospects />} />
          <Route path="templates" element={<Templates />} />
        </Route>
      </Routes>
    </HashRouter>
  );
}
