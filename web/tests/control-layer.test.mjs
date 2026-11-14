import test from "node:test";
import assert from "node:assert/strict";

const origin = process.env.TEST_ORIGIN || "http://127.0.0.1:5173";
const command = {
  action: "reject",
  reason: "Occlusion in the demo observation.",
  expectedRevision: 1,
  requestId: "test-request-0001",
};
const post = (body, headers = {}, id = "alert-718") =>
  fetch(`${origin}/api/alerts/${id}/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...headers },
    body: typeof body === "string" ? body : JSON.stringify(body),
  });

test("overview fixture preserves roster, observation and identity invariants", async () => {
  const response = await fetch(`${origin}/api/overview`);
  const raw = await response.text();
  assert.equal(response.status, 200, raw);
  const { data } = JSON.parse(raw);
  assert.equal(data.mode, "demo");
  assert.equal(data.animals.length, 90);
  assert.equal(new Set(data.animals.map((a) => a.id)).size, 90);
  assert.equal(new Set(data.animals.map((a) => a.tag)).size, 90);
  assert.equal(data.animals.filter((a) => a.observedAt).length, 82);
  assert.equal(
    data.animals.filter((a) => a.assessment === "unobserved").length,
    8,
  );
  assert.ok(
    data.animals
      .filter((a) => a.assessment === "unobserved")
      .every((a) => a.mapPosition === null),
  );
  assert.ok(
    data.animals.every((a) => data.herds.some((h) => h.id === a.herdId)),
  );
  assert.ok(
    data.alerts.every((a) => data.animals.some((cow) => cow.id === a.animalId)),
  );
  assert.equal(data.capabilities.liveConnected, false);
  assert.equal(data.nonCowDetections.length, 2);
  assert.ok(
    data.nonCowDetections.every(
      (item) => !data.animals.some((animal) => animal.id === item.id),
    ),
  );
  assert.ok(
    data.nonCowDetections.every((item) =>
      data.herds.some((herd) => herd.pastureId === item.pastureId),
    ),
  );
});

test("latest recording lookup does not invent cow footage or signed URLs", async () => {
  const response = await fetch(`${origin}/api/cattle/cow-718/recording`);
  assert.equal(response.status, 200);
  const { data } = await response.json();
  assert.equal(data.animalId, "cow-718");
  assert.equal(data.availability, "unavailable");
  assert.equal(data.playbackUrl, null);
  assert.equal(data.capturedAt, null);
  assert.equal(
    (await fetch(`${origin}/api/cattle/other-1/recording`)).status,
    404,
  );
});

test("review requires a reason; no silent negative assessment", async () => {
  const response = await post({ ...command, reason: " " });
  assert.equal(response.status, 400);
  assert.equal((await response.json()).error.code, "REASON_REQUIRED");
});

test("review commands distinguish missing findings and invalid input", async () => {
  assert.equal((await post(command, {}, "does-not-exist")).status, 404);
  assert.equal((await post({ ...command, action: "diagnose" })).status, 400);
  assert.equal((await post({ ...command, expectedRevision: 0 })).status, 400);
  assert.equal((await post("not json")).status, 400);
  assert.equal(
    (await post(command, { "Content-Type": "text/plain" })).status,
    415,
  );
});

test("cross-origin commands are rejected", async () => {
  const response = await post(command, { Origin: "https://unrelated.example" });
  assert.equal(response.status, 403);
  // The framework may reject before the application handler; either boundary must deny it.
  assert.match(await response.text(), /Forbidden|ORIGIN_REJECTED/);
});

test("valid rejection returns explicit nonpersistent demo receipt and leaves source immutable", async () => {
  const response = await post(command, { Origin: origin });
  const raw = await response.text();
  assert.equal(response.status, 200, raw);
  const { data } = JSON.parse(raw);
  assert.equal(data.lifecycle, "invalidated");
  assert.equal(data.revision, 2);
  assert.equal(data.persisted, false);
  assert.equal(data.actor, "Demo reviewer");
  const source = await (await fetch(`${origin}/api/overview`)).json();
  assert.equal(
    source.data.alerts.find((a) => a.id === "alert-718").lifecycle,
    "open",
  );
});
