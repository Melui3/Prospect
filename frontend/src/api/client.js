import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? "/api",
  headers: { "Content-Type": "application/json" },
});

// ── Campaigns ─────────────────────────────────────────────────
export const getCampaigns = () => api.get("/campaigns/").then((r) => r.data);
export const createCampaign = (data) => api.post("/campaigns/", data).then((r) => r.data);
export const deleteCampaign = (id) => api.delete(`/campaigns/${id}/`);
export const launchCampaign = (id) => api.post(`/campaigns/${id}/launch/`).then((r) => r.data);

// ── Prospects ─────────────────────────────────────────────────
export const getProspects = (params = {}) =>
  api.get("/prospects/", { params }).then((r) => r.data);
export const updateProspect = (id, data) =>
  api.patch(`/prospects/${id}/`, data).then((r) => r.data);
export const sendProspectEmail = (id, templateId) =>
  api.post(`/prospects/${id}/send-email/`, { template_id: templateId }).then((r) => r.data);

// ── Templates ─────────────────────────────────────────────────
export const getTemplates = () => api.get("/templates/").then((r) => r.data);
export const createTemplate = (data) => api.post("/templates/", data).then((r) => r.data);
export const updateTemplate = (id, data) =>
  api.patch(`/templates/${id}/`, data).then((r) => r.data);
export const deleteTemplate = (id) => api.delete(`/templates/${id}/`);

// ── Stats ─────────────────────────────────────────────────────
export const getStats = () => api.get("/stats/").then((r) => r.data);
