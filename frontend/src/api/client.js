import axios from "axios";

export const API_URL = import.meta.env.VITE_API_URL
  ?? (import.meta.env.DEV ? "/api" : "https://very-annalise-honeygroup-12ff0f9f.koyeb.app/api");

const OWNER_TOKEN_KEY = "prospect_owner_token";
const OWNER_API_FAILED_KEY = "prospect_owner_api_failed";
const GET_CACHE_TTL_MS = 60_000;

const getCache = new Map();

export const clearApiCache = () => {
  getCache.clear();
};

export const getOwnerToken = () => localStorage.getItem(OWNER_TOKEN_KEY) ?? "";
export const getOwnerApiFailed = () => sessionStorage.getItem(OWNER_API_FAILED_KEY) ?? "";
export const clearOwnerApiFailed = () => sessionStorage.removeItem(OWNER_API_FAILED_KEY);

export const setOwnerToken = (token) => {
  localStorage.setItem(OWNER_TOKEN_KEY, token);
  clearApiCache();
};

export const clearOwnerToken = () => {
  localStorage.removeItem(OWNER_TOKEN_KEY);
  clearApiCache();
};

const invalidateCache = (...prefixes) => {
  for (const key of getCache.keys()) {
    if (prefixes.some((prefix) => key.startsWith(prefix))) {
      getCache.delete(key);
    }
  }
};

const sortedParams = (params = {}) =>
  new URLSearchParams(
    Object.entries(params)
      .filter(([, value]) => value !== "" && value !== null && value !== undefined)
      .sort(([a], [b]) => a.localeCompare(b))
  ).toString();

const cachedGet = (key, request, { force = false, ttl = GET_CACHE_TTL_MS } = {}) => {
  const now = Date.now();
  const entry = getCache.get(key);

  if (!force && entry?.data !== undefined && now - entry.time < ttl) {
    return Promise.resolve(entry.data);
  }

  if (!force && entry?.promise) {
    return entry.promise;
  }

  const promise = request()
    .then((data) => {
      getCache.set(key, { data, time: Date.now() });
      return data;
    })
    .catch((err) => {
      if (getCache.get(key)?.promise === promise) {
        getCache.delete(key);
      }
      throw err;
    });

  getCache.set(key, { data: entry?.data, time: entry?.time ?? 0, promise });
  return promise;
};

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

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    const method = error.config?.method?.toLowerCase();

    if (status >= 500 && method === "get" && getOwnerToken()) {
      clearOwnerToken();
      sessionStorage.setItem(
        OWNER_API_FAILED_KEY,
        "L'acces prive a ete desactive car l'API repond 500."
      );
      window.location.reload();
      return new Promise(() => {});
    }

    return Promise.reject(error);
  }
);

export const getSession = (options = {}) =>
  cachedGet("session", () => api.get("/session/").then((r) => r.data), {
    ttl: 5 * GET_CACHE_TTL_MS,
    ...options,
  });

export const getCampaigns = (options = {}) =>
  cachedGet("campaigns", () => api.get("/campaigns/").then((r) => r.data), options);

export const createCampaign = (data) =>
  api.post("/campaigns/", data).then((r) => {
    invalidateCache("campaigns", "stats");
    return r.data;
  });

export const deleteCampaign = (id) =>
  api.delete(`/campaigns/${id}/`).then((r) => {
    invalidateCache("campaigns", "prospects", "stats");
    return r;
  });

export const launchCampaign = (id) =>
  api.post(`/campaigns/${id}/launch/`).then((r) => {
    invalidateCache("campaigns", "prospects", "stats");
    return r.data;
  });

export const getProspects = (params = {}, options = {}) =>
  cachedGet(
    `prospects:${sortedParams(params)}`,
    () => api.get("/prospects/", { params }).then((r) => r.data),
    options
  );

export const updateProspect = (id, data) =>
  api.patch(`/prospects/${id}/`, data).then((r) => {
    invalidateCache("prospects", "stats");
    return r.data;
  });

export const sendProspectEmail = (id, templateId) =>
  api.post(`/prospects/${id}/send-email/`, { template_id: templateId }).then((r) => {
    invalidateCache("prospects", "stats");
    return r.data;
  });

export const getTemplates = (options = {}) =>
  cachedGet("templates", () => api.get("/templates/").then((r) => r.data), options);

export const createTemplate = (data) =>
  api.post("/templates/", data).then((r) => {
    invalidateCache("templates");
    return r.data;
  });

export const updateTemplate = (id, data) =>
  api.patch(`/templates/${id}/`, data).then((r) => {
    invalidateCache("templates");
    return r.data;
  });

export const deleteTemplate = (id) =>
  api.delete(`/templates/${id}/`).then((r) => {
    invalidateCache("templates");
    return r;
  });

export const getStats = (options = {}) =>
  cachedGet("stats", () => api.get("/stats/").then((r) => r.data), options);
