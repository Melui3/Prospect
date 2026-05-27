import { HashRouter, Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import Campaigns from "./pages/Campaigns";
import Prospects from "./pages/Prospects";
import Templates from "./pages/Templates";

export default function App() {
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
