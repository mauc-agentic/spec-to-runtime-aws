import assert from "node:assert/strict";
import { test } from "node:test";
import { PAUSED_MESSAGE, describeFailure } from "../errors.js";

test("el corte de presupuesto avisa que la demo está en pausa y no ofrece reintentar", () => {
  const failure = describeFailure({ status: "Failed", error_code: "AccessDeniedException" });
  assert.equal(failure.text, PAUSED_MESSAGE);
  assert.equal(failure.retry, false);
  assert.match(failure.text, /pausa/);
  assert.match(failure.text, /ponente/);
});

test("un tiempo de espera agotado se puede reintentar", () => {
  const failure = describeFailure({ error_code: "timeout" });
  assert.equal(failure.retry, true);
  assert.match(failure.text, /tardó demasiado/);
});

test("cualquier otro fallo se puede reintentar y aclara que no descontó cuota", () => {
  for (const data of [{ error_code: "agent_failed" }, { error_code: "ClientError" }, {}, null, undefined]) {
    const failure = describeFailure(data);
    assert.equal(failure.retry, true);
    assert.match(failure.text, /no se descontó/);
  }
});

test("los avisos conocidos se traducen, sin repetir, y los desconocidos se ignoran", async () => {
  const { noticeTexts, NOTICES } = await import("../errors.js");
  assert.deepEqual(noticeTexts(["personal_data_masked", "personal_data_masked", "otro"]), [
    NOTICES.personal_data_masked,
  ]);
  assert.match(NOTICES.memory_unavailable, /solo con tu pregunta actual/);
  assert.deepEqual(noticeTexts(undefined), []);
});
