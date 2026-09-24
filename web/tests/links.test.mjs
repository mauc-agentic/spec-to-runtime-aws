import assert from "node:assert/strict";
import { test } from "node:test";
import { sessionUrl } from "../links.js";

test("arma el enlace a la sesión en GenAI Observability de CloudWatch", () => {
  assert.equal(
    sessionUrl("us-east-1", "sess-cacf5904992341aaaf47235457574c85"),
    "https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#gen-ai-observability/agent-core/session/sess-cacf5904992341aaaf47235457574c85",
  );
});

test("un identificador con formato raro no produce enlace (evita inyectar contenido)", () => {
  const bad = ["", "abc", "sess-xyz", "sess-CACF5904992341AAAF47235457574C85", 'sess-cacf5904992341aaaf47235457574c85"><script>', "javascript:alert(1)", "1-6ab4c4ab-7ab5933bc56e7bc501f8550d"];
  for (const value of bad) assert.equal(sessionUrl("us-east-1", value), null, value);
});
