import assert from "node:assert/strict";
import { test } from "node:test";

globalThis.window = { APP_CONFIG: { region: "us-east-1", clientId: "x" } };
const { subOf } = await import("../cognito.js");

const token = (claims) => `h.${Buffer.from(JSON.stringify(claims)).toString("base64url")}.s`;

test("UC-004 A1: subOf identifica la cuenta para no devolver la pregunta a otra persona", () => {
  assert.equal(subOf(token({ sub: "abc-123" })), "abc-123");
});

test("UC-004 A1: un token ilegible o sin sub no identifica a nadie", () => {
  assert.equal(subOf(token({})), null);
  assert.equal(subOf("no-es-un-token"), null);
  assert.equal(subOf(null), null);
});
