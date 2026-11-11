export function desktopAccessFromFragment(desktop, hash) {
  if (!desktop || !hash.startsWith("#/?access=")) return null;
  return new URLSearchParams(hash.slice(3)).get("access") || null;
}

export function renderMessageTemplate(text, variables) {
  return text.replace(/\{\{|\}\}|\{([^{}]+)\}/g, (match, key) => {
    if (match === "{{") return "{";
    if (match === "}}") return "}";
    if (!Object.hasOwn(variables, key)) throw new Error(`Variable inconnue : ${key}`);
    return variables[key] ?? "";
  });
}
