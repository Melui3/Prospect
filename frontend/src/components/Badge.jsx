const styles = {
  new: "bg-slate-100 text-slate-600",
  contacted: "bg-blue-100 text-blue-700",
  replied: "bg-green-100 text-green-700",
  ignored: "bg-red-100 text-red-600",
  draft: "bg-slate-100 text-slate-500",
  running: "bg-yellow-100 text-yellow-700",
  done: "bg-green-100 text-green-700",
  error: "bg-red-100 text-red-700",
};

const labels = {
  new: "Nouveau",
  contacted: "Contacté",
  replied: "Répondu",
  ignored: "Ignoré",
  draft: "Brouillon",
  running: "En cours…",
  done: "Terminée",
  error: "Erreur",
};

export default function Badge({ value }) {
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
        styles[value] ?? "bg-slate-100 text-slate-600"
      }`}
    >
      {labels[value] ?? value}
    </span>
  );
}
