import axios from "axios";

export const API_URL = import.meta.env.VITE_API_URL
  ?? (import.meta.env.DEV ? "/api" : "https://very-annalise-honeygroup-12ff0f9f.koyeb.app/api");

const api = axios.create({
  baseURL: API_URL,
  headers: { "Content-Type": "application/json" },
});

// ── Auth helpers ───────────────────────────────────────────────
export function getAccessToken() {
  return localStorage.getItem("access_token");
}

export function isAuthenticated() {
  return !!getAccessToken();
}

export async function login(username, password) {
  const res = await axios.post(
    API_URL.replace(/\/api$/, "") + "/api/token/",
    { username, password }
  );
  localStorage.setItem("access_token", res.data.access);
  localStorage.setItem("refresh_token", res.data.refresh);
}

export function logout() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
}

// ── Interceptors ───────────────────────────────────────────────
api.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true;
      const refresh = localStorage.getItem("refresh_token");
      if (refresh) {
        try {
          const base = API_URL.replace(/\/api$/, "");
          const res = await axios.post(base + "/api/token/refresh/", { refresh });
          localStorage.setItem("access_token", res.data.access);
          original.headers.Authorization = `Bearer ${res.data.access}`;
          return api(original);
        } catch {
          // refresh failed
        }
      }
      logout();
      window.location.replace(window.location.origin + window.location.pathname.split("#")[0] + "#/login");
    }
    return Promise.reject(error);
  }
);

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
