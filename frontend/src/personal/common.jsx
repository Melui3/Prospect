import { LoaderCircle } from "lucide-react";

export const statuses = [
  ["new", "Nouveau"], ["contacted", "Contacte"], ["replied", "Repondu"],
  ["interested", "Interesse"], ["proposal", "Devis envoye"], ["won", "Gagne"],
  ["lost", "Refuse"], ["ignored", "Ignore"], ["do_not_contact", "Ne plus contacter"],
];
export const statusLabel = (status) => statuses.find(([key]) => key === status)?.[1] ?? status;
export const formatDate = (value) => value ? new Intl.DateTimeFormat("fr-FR", { dateStyle: "short", timeStyle: "short" }).format(new Date(value)) : "-";
export const externalUrl = (value) => {
  if (!value) return null;
  try {
    const url = new URL(/^https?:\/\//i.test(value) ? value : `https://${value}`);
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch { return null; }
};
export function IconButton({ icon: Icon, label, ...props }) {
  return <button type="button" className="p-icon" title={label} aria-label={label} {...props}><Icon size={17} /></button>;
}
export function Status({ value }) { return <span className={`p-status status-${value}`}>{statusLabel(value)}</span>; }
export function Notice({ children, kind = "error" }) { return children ? <div role={kind === "error" ? "alert" : "status"} className={`p-notice ${kind}`}>{children}</div> : null; }
export function Loading() { return <div className="p-loading"><LoaderCircle size={20} className="p-spin" /> Chargement...</div>; }
export function Empty({ children }) { return <div className="p-empty">{children}</div>; }
