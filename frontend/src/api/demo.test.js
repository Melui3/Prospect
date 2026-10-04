import test from "node:test";
import assert from "node:assert/strict";
import axios from "axios";
import { createDemoAdapter } from "./demo.js";
import { useStaticDemo } from "./mode.js";

test("GitHub Pages always uses the static demo; desktop uses the real local API", () => {
  assert.equal(useStaticDemo("melui3.github.io", "false"), true);
  assert.equal(useStaticDemo("127.0.0.1", "false"), false);
  assert.equal(useStaticDemo("localhost", "true"), true);
});

test("demo ignores owner credentials and cannot use a real API transport", async () => {
  const api = axios.create({
    baseURL: "https://private-api.invalid/api",
    adapter: createDemoAdapter(),
    headers: { "X-Owner-Token": "any-token" },
  });
  const { data: session } = await api.get("/session/");
  assert.equal(session.is_owner, false);
  assert.equal(session.static_demo, true);
  assert.equal(session.mode, "demo");
  const { data: contacts } = await api.get("/prospects/");
  assert.ok(contacts.length > 0);
  assert.ok(contacts.every((p) => !p.email || p.email.endsWith(".example")));
  const { data: sent } = await api.post("/prospects/1001/send-email/", { template_id: 201 });
  assert.equal(sent.demo_blocked, true);
  const { data: launch } = await api.post("/campaigns/104/launch/");
  assert.equal(launch.demo_blocked, true);
  await assert.rejects(api.post("/unknown/"), /indisponible/);
});

test("filters, stats and simulated changes stay consistent and reset in a new session", async () => {
  const api = axios.create({ adapter: createDemoAdapter() });
  const { data: filtered } = await api.get("/prospects/", {
    params: { campaign: "101", has_email: "true", has_website: "false" },
  });
  assert.deepEqual(filtered.map((p) => p.id), [1001]);
  const { data: before } = await api.get("/stats/");
  await api.patch("/prospects/1003/", { status: "replied" });
  const { data: after } = await api.get("/stats/");
  assert.equal(after.prospects_replied, before.prospects_replied + 1);

  const { data: created } = await api.post("/campaigns/", {
    secteur: "association", ville: "Lille", rayon_km: 10,
  });
  const { data: campaigns } = await api.get("/campaigns/");
  assert.ok(campaigns.some((c) => c.id === created.id));
  await api.delete(`/campaigns/${created.id}/`);
  const { data: removed } = await api.get("/campaigns/");
  assert.ok(!removed.some((c) => c.id === created.id));

  await api.patch("/templates/201/", { name: "Test local" });
  assert.equal((await api.get("/templates/201/")).data.name, "Test local");
  const fresh = axios.create({ adapter: createDemoAdapter() });
  assert.notEqual((await fresh.get("/templates/201/")).data.name, "Test local");
  assert.equal((await fresh.get("/stats/")).data.prospects_replied, before.prospects_replied);
});

test("returned fixtures cannot mutate subsequent demo responses", async () => {
  const api = axios.create({ adapter: createDemoAdapter() });
  const { data } = await api.get("/prospects/");
  data[0].email = "private@example.com";
  assert.notEqual((await api.get("/prospects/")).data[0].email, data[0].email);
});
