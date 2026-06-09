import axios from "axios";

export const API_URL = import.meta.env.VITE_API_URL
  ?? (import.meta.env.DEV ? "/api" : "https://very-annalise-honeygroup-12ff0f9f.koyeb.app/api");

const OWNER_TOKEN_KEY = "prospect_owner_token";

export const getOwnerToken = () => localStorage.getItem(OWNER_TOKEN_KEY) ?? "";
export const setOwnerToken = (token) => localStorage.setItem(OWNER_TOKEN_KEY, token);
export const clearOwnerToken = () => localStorage.removeItem(OWNER_TOKEN_KEY);

const api = axios.create({
  baseURL: API_URL,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config) => {
  const token = getOwnerToken();
  if (token) {
    config.headers["X-Owner-Token"] = token;
  }
  return config;
});

export const getSession = () => api.get("/session/").then((r) => r.data);

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
