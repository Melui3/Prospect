import { test } from "node:test";
import assert from "node:assert/strict";
import { desktopAccessFromFragment, renderMessageTemplate } from "./personal-utils.js";

test("desktop access fragment is ignored outside the personal desktop app", () => {
  assert.equal(desktopAccessFromFragment(false, "#/?access=fake-test-token"), null);
  assert.equal(desktopAccessFromFragment(true, "#/dashboard?access=fake"), null);
  assert.equal(desktopAccessFromFragment(true, "#/?access=fake%20test%2Btoken"), "fake test+token");
});
test("personal mail preview substitutes supported variables and escaped braces", () => {
  assert.equal(renderMessageTemplate("Bonjour {nom}, {{ville}} : {ville}", { nom: "Atelier", ville: "Rennes" }), "Bonjour Atelier, {ville} : Rennes");
  assert.equal(renderMessageTemplate("Site : {website}", { website: "" }), "Site : ");
});
test("unknown variables cannot silently reach the recipient", () => {
  assert.throws(() => renderMessageTemplate("Bonjour {entreprise}", { nom: "Atelier" }), /Variable inconnue/);
});
