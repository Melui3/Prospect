import axios from "axios";
import { useStaticDemo } from "./mode";
import { desktopAccessFromFragment } from "./personal-utils";

export const STATIC_DEMO = useStaticDemo(window.location.hostname, import.meta.env.VITE_STATIC_DEMO);
export const DESKTOP_APP = !STATIC_DEMO && import.meta.env.VITE_DESKTOP_MODE === "true";

export const API_URL = import.meta.env.VITE_API_URL || "/api";

const OWNER_TOKEN_KEY = "prospect_owner_token";
const OWNER_API_FAILED_KEY = "prospect_owner_api_failed";
const ACCESS_MODE_KEY = "prospect_access_mode";
const GET_CACHE_TTL_MS = 60_000;

const getCache = new Map();

export const clearApiCache = () => {
  getCache.clear();
};

export const getOwnerToken = () => STATIC_DEMO ? "" : localStorage.getItem(OWNER_TOKEN_KEY) ?? "";
export const getAccessMode = () => STATIC_DEMO ? "demo" : localStorage.getItem(ACCESS_MODE_KEY) ?? "locked";
export const isDemoMode = () => STATIC_DEMO || (!DESKTOP_APP && getAccessMode() === "demo");
export const getOwnerApiFailed = () => STATIC_DEMO ? "" : sessionStorage.getItem(OWNER_API_FAILED_KEY) ?? "";
export const clearOwnerApiFailed = () => sessionStorage.removeItem(OWNER_API_FAILED_KEY);

const setOwnerApiFailed = (message) => {
  sessionStorage.setItem(OWNER_API_FAILED_KEY, message);
};

export const setOwnerToken = (token) => {
  if (STATIC_DEMO) return;
  localStorage.setItem(OWNER_TOKEN_KEY, token);
  localStorage.setItem(ACCESS_MODE_KEY, "owner");
  clearApiCache();
};

export const clearOwnerToken = () => {
  localStorage.removeItem(OWNER_TOKEN_KEY);
  if (getAccessMode() === "owner") {
    localStorage.setItem(ACCESS_MODE_KEY, "locked");
  }
  clearApiCache();
};

export const enterDemoMode = () => {
  if (DESKTOP_APP) return;
  localStorage.setItem(ACCESS_MODE_KEY, "demo");
  clearApiCache();
};

// Fragments are never transmitted in HTTP requests or server logs.
if (DESKTOP_APP && window.location.hash.startsWith("#/?access=")) {
  const access = desktopAccessFromFragment(DESKTOP_APP, window.location.hash);
  if (access) setOwnerToken(access);
  window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}#/dashboard`);
}

export const exitDemoMode = () => {
  if (getAccessMode() === "demo") {
    localStorage.setItem(ACCESS_MODE_KEY, getOwnerToken() ? "owner" : "locked");
  }
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

if (STATIC_DEMO) {
  const adapter = import("./demo").then(({ createDemoAdapter }) => createDemoAdapter());
  api.defaults.adapter = async (config) => (await adapter)(config);
}

api.interceptors.request.use((config) => {
  const token = getOwnerToken();
  if (isDemoMode()) {
    config.headers["X-Demo-Mode"] = "true";
  } else if (token) {
    config.headers["X-Owner-Token"] = token;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;

    if ((status === 401 || status === 403) && !isDemoMode() && getOwnerToken()) {
      clearOwnerToken();
      setOwnerApiFailed("Le token prive a ete refuse par l'API.");
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

export default api;
