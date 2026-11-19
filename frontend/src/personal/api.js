import api from "../api/client";

const root = "/personal";
const cache = new Map();
let generation = 0;
function cached(path, params = {}, force = false) {
  const key = path + JSON.stringify(params);
  const previous = cache.get(key);
  if (!force && previous && Date.now() - previous.time < 40000) return Promise.resolve(previous.data);
  const version = generation;
  return api.get(path, { params }).then((r) => { if (version === generation) cache.set(key, { data: r.data, time: Date.now() }); return r.data; });
}
function changed(promise) { return promise.then((r) => { generation++; cache.clear(); return r.data; }); }
export const getToday = (force = false) => cached(`${root}/today/`, {}, force);
export const getContacts = (params, force = false) => cached(`${root}/contacts/`, params, force);
export const getContact = (id, force = false) => cached(`${root}/contacts/${id}/`, {}, force);
export const saveContact = (id, data) => changed(id ? api.patch(`${root}/contacts/${id}/`, data) : api.post(`${root}/contacts/`, data));
export const enrichContact = (id) => changed(api.post(`${root}/contacts/${id}/enrich/`));
export const sendMessage = (id, data, key) => changed(api.post(`${root}/contacts/${id}/send-email/`, data, { headers: { "Idempotency-Key": key } }));
export const getCampaigns = (force = false) => cached(`${root}/campaigns/`, {}, force);
export const createCampaign = (data) => changed(api.post(`${root}/campaigns/`, data));
export const launchCampaign = (id) => changed(api.post(`${root}/campaigns/${id}/launch/`));
export const setCampaignSchedule = (id, repeat_days) => changed(api.post(`${root}/campaigns/${id}/schedule/`, { repeat_days }));
export const deleteCampaign = (id) => changed(api.delete(`${root}/campaigns/${id}/`));
export const controlJob = (id, action) => changed(api.post(`${root}/jobs/${id}/${action}/`));
export const getQualifications = (status = "pending", force = false) => cached(`${root}/qualification/`, { status }, force);
export const runQualifications = () => changed(api.post(`${root}/qualification/run/`));
export const decideQualification = (id, decision) => changed(api.post(`${root}/qualification/${id}/${decision}/`));
export const saveQualificationEvidence = (id, data) => changed(api.post(`${root}/qualification/${id}/evidence/`, data));
export const getEmailDraft = (id) => api.get(`${root}/contacts/${id}/draft/`).then((r) => r.data);
export const saveEmailDraft = (id, data) => changed(api.put(`${root}/contacts/${id}/draft/`, data));
export const getEmailSettings = () => api.get(`${root}/email-settings/`).then((r) => r.data);
export const saveEmailSettings = (data) => api.post(`${root}/email-settings/`, data).then((r) => r.data);
export const syncDelivery = () => changed(api.post(`${root}/delivery-sync/`));
export const getBackups = () => api.get(`${root}/backups/`).then((r) => r.data);
export const createBackup = () => api.post(`${root}/backups/`).then((r) => r.data);
export const restoreBackup = (name) => changed(api.post(`${root}/restore/`, { name, confirmation: "RESTAURER" }));

export const errorMessage = (error) => {
  const data = error.response?.data;
  if (data?.error) return data.error;
  if (data?.detail) return data.detail;
  if (data) return Object.entries(data).map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(", ") : value}`).join(" ");
  return "Connexion impossible. Verifie que Prospect est lance.";
};
