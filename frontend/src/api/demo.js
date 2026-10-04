const createdAt = "2026-07-10T09:15:00+02:00";
const demoNotice = "Modification simulee: rien n'est sauvegarde apres rechargement.";

const campaign = (id, secteur, ville, rayon_km, status = "done") => ({
  id, secteur, ville, rayon_km, status, created_at: createdAt,
  launched_at: status === "draft" ? null : createdAt, error_message: "",
});

const prospect = (id, campaignId, secteur, nom, ville, email, website, status = "new", emailsSent = 0) => ({
  id, campaign: campaignId, campaign_secteur: secteur, nom, ville, email, website,
  adresse: "Adresse fictive", telephone: "", has_website: Boolean(website),
  status, emails_sent: emailsSent, created_at: createdAt,
});

// All fixtures are fictional and stay in this browser's memory.
export function createDemoAdapter() {
  let campaigns = [
    campaign(101, "association", "Rennes", 15),
    campaign(102, "restaurant", "Nantes", 10),
    campaign(103, "coiffeur", "Rennes", 10),
    campaign(104, "boulangerie", "Combourg", 25, "draft"),
  ];
  let prospects = [
    prospect(1001, 101, "association", "Collectif Horizon Local", "Rennes", "contact@horizon-local.example", "", "contacted", 1),
    prospect(1002, 101, "association", "Maison des Voisins", "Cesson-Sevigne", "bonjour@maison-voisins.example", "https://maison-voisins.example", "replied", 2),
    prospect(1003, 101, "association", "Atelier Partage", "Rennes", "", ""),
    prospect(1004, 102, "restaurant", "Le Comptoir du Canal", "Nantes", "reservation@comptoir-canal.example", "", "contacted", 1),
    prospect(1005, 102, "restaurant", "Table Nocturne", "Nantes", "", "https://table-nocturne.example", "ignored"),
    prospect(1006, 102, "restaurant", "Bistro des Halles", "Nantes", "hello@bistro-halles.example", ""),
    prospect(1007, 103, "coiffeur", "Studio Carmin", "Rennes", "contact@studio-carmin.example", ""),
  ];
  let templates = [
    {
      id: 201, name: "Sans site - premier contact",
      subject: "Bonjour {nom} - une presence web simple pour {ville}",
      body: "Bonjour,\n\nJe vous contacte car je n'ai pas trouve de site pour {nom} a {ville}.\n\nJe cree des sites pour les structures locales. Seriez-vous ouvert a un court echange ?",
      created_at: createdAt, updated_at: createdAt,
    },
    {
      id: 202, name: "Site existant - prise de contact",
      subject: "Une proposition pour {nom}",
      body: "Bonjour,\n\nJ'ai consulte votre site ({website}). Je peux vous envoyer quelques pistes pour faciliter la prise de contact sur mobile.\n\nCela vous interesserait-il ?",
      created_at: createdAt, updated_at: createdAt,
    },
  ];
  let nextId = 2000;

  const campaignData = (item) => {
    const contacts = prospects.filter((p) => p.campaign === item.id);
    return {
      ...item, total_prospects: contacts.length,
      prospects_with_email: contacts.filter((p) => p.email).length,
    };
  };

  return async (config) => {
    const method = config.method?.toLowerCase() ?? "get";
    const route = config.url.replace(/^\/+|\/+$/g, "").split("/");
    const [resource, id, action] = route;
    const payload = typeof config.data === "string" ? JSON.parse(config.data) : config.data ?? {};
    const params = config.params ?? {};
    let data;
    let status = 200;

    if (method === "get" && resource === "session") {
      data = { mode: "demo", is_demo: true, is_owner: false, auth_required: false, demo_available: true, static_demo: true };
    } else if (method === "get" && resource === "stats") {
      data = {
        total_campaigns: campaigns.length,
        done_campaigns: campaigns.filter((c) => c.status === "done").length,
        total_prospects: prospects.length,
        prospects_with_email: prospects.filter((p) => p.email).length,
        emails_sent: prospects.reduce((total, p) => total + p.emails_sent, 0),
        prospects_contacted: prospects.filter((p) => ["contacted", "replied"].includes(p.status)).length,
        prospects_replied: prospects.filter((p) => p.status === "replied").length,
      };
    } else if (resource === "campaigns") {
      const item = campaigns.find((c) => String(c.id) === id);
      if (method === "get") {
        data = id ? item && campaignData(item) : campaigns.map(campaignData);
      } else if (method === "post" && !id) {
        const created = campaign(nextId++, payload.secteur, payload.ville, Number(payload.rayon_km), "draft");
        campaigns.unshift(created);
        data = { ...campaignData(created), demo_notice: demoNotice };
        status = 201;
      } else if (method === "post" && action === "launch" && item) {
        data = { demo_blocked: true, message: "Mode demo: aucune recherche externe n'est lancee.", status: item.status };
      } else if (method === "delete" && item) {
        campaigns = campaigns.filter((c) => c !== item);
        prospects = prospects.filter((p) => p.campaign !== item.id);
        data = null;
        status = 204;
      }
    } else if (resource === "prospects") {
      const item = prospects.find((p) => String(p.id) === id);
      if (method === "get") {
        data = id ? item : prospects.filter((p) =>
          (!params.campaign || String(p.campaign) === String(params.campaign)) &&
          (!params.status || p.status === params.status) &&
          (!params.has_email || Boolean(p.email) === (String(params.has_email) === "true")) &&
          (!params.has_website || p.has_website === (String(params.has_website) === "true"))
        );
      } else if (method === "patch" && item) {
        if (["new", "contacted", "replied", "ignored"].includes(payload.status)) item.status = payload.status;
        data = { ...item, demo_notice: demoNotice };
      } else if (method === "post" && action === "send-email" && item) {
        data = { demo_blocked: true, message: "Mode demo: aucun email reel n'a ete envoye." };
      }
    } else if (resource === "templates") {
      const item = templates.find((t) => String(t.id) === id);
      if (method === "get") {
        data = id ? item : templates;
      } else if (method === "post" && !id) {
        const created = {
          id: nextId++, name: payload.name, subject: payload.subject, body: payload.body,
          created_at: new Date().toISOString(), updated_at: new Date().toISOString(),
        };
        templates.unshift(created);
        data = { ...created, demo_notice: demoNotice };
        status = 201;
      } else if (method === "patch" && item) {
        for (const key of ["name", "subject", "body"]) {
          if (payload[key] !== undefined) item[key] = payload[key];
        }
        data = { ...item, demo_notice: demoNotice };
      } else if (method === "delete" && item) {
        templates = templates.filter((t) => t !== item);
        data = null;
        status = 204;
      }
    }

    if (data === undefined) {
      throw Object.assign(new Error("Action indisponible en demonstration."), {
        config, response: { status: 404, data: { detail: "Introuvable." } },
      });
    }

    return { data: structuredClone(data), status, statusText: "OK", headers: {}, config };
  };
}
