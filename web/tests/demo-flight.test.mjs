import { test } from 'node:test';
import assert from 'node:assert/strict';
const base = process.env.TEST_ORIGIN || 'http://127.0.0.1:8790';
const root = `${base}/api/demo-flight`;
const post = body => ({ method: 'POST', headers: { 'Content-Type': 'application/json', Origin: base }, body: JSON.stringify(body) });

test('demo control layer restricts operation paths, origins and payloads', async () => {
  for (const path of ['/jobs/invalid', '/assets/secrets', '/jobs/'+'A'.repeat(32)]) {
    assert.equal((await fetch(root+path)).status, 400);
  }
  assert.equal((await fetch(`${root}/jobs/${'a'.repeat(32)}`)).status, 404);
  assert.equal((await fetch(`${root}/jobs`, { ...post({}), headers: { 'Content-Type': 'application/json', Origin: 'https://foreign.example' } })).status, 403);
  assert.equal((await fetch(`${root}/jobs`, {method: 'POST', body: '{}'})).status, 415);
  assert.equal((await fetch(`${root}/jobs`, {...post({}), body:'{'})).status, 400);
  assert.equal((await fetch(`${root}/jobs`, post({assetId:'../../private', mode:'inference', requestId:'a'.repeat(32)}))).status, 400);
});

test('prepared evidence, HTTP seeking and durable review through Worker', async () => {
  const command = { assetId: 'scene-flight', mode: 'precomputed', requestId: crypto.randomUUID().replaceAll('-', '') };
  let response = await fetch(`${root}/jobs`, post(command));
  assert.equal(response.status, 200);
  let job = (await response.json()).data;
  assert.equal(job.mode, 'precomputed', 'Run after any active inference job finishes');
  assert.equal(job.state, 'queued');
  for (let n = 0; n < 100 && ['queued','running'].includes(job.state); n++) {
    await new Promise(resolve => setTimeout(resolve, 100));
    job = (await (await fetch(`${root}/jobs/${job.id}`)).json()).data;
  }
  assert.equal(job.state, 'completed');
  assert.equal(job.result.frames.length, Math.round(job.result.duration * job.result.fps));
  assert.ok(job.result.frames.length > 0);
  assert.equal(job.result.illustrativeScores, true);
  assert.match(job.result.pipeline, /YOLO11/);
  assert.equal((await (await fetch(`${root}/jobs`, post(command))).json()).data.id, job.id);
  response = await fetch(`${root}/assets/scene-video`, {headers:{Range:'bytes=100-199'}});
  assert.equal(response.status, 206);
  assert.equal((await response.arrayBuffer()).byteLength, 100);
  const detection = job.result.frames.flatMap(frame => frame.detections)[0];
  assert.equal(detection.keypoints.length, 17);
  const review = {detectionId:detection.id, action:'flag', note:'HTTP integration test observation', expectedSeq:0};
  assert.equal((await fetch(`${root}/jobs/${job.id}/reviews`, post({...review, note:''}))).status, 400);
  job = (await (await fetch(`${root}/jobs/${job.id}/reviews`, post(review))).json()).data;
  assert.equal(job.reviews[0].note, review.note);
  assert.equal((await fetch(`${root}/jobs/${job.id}/reviews`, post(review))).status, 409);
  job = (await (await fetch(`${root}/jobs/${job.id}/reviews`, post({...review, action:'reject', note:'Reviewed: possible false positive', expectedSeq:job.reviews[0].seq}))).json()).data;
  const reloaded = (await (await fetch(`${root}/jobs/${job.id}`)).json()).data;
  assert.deepEqual(reloaded.reviews.map(r => r.action), ['flag','reject']);
  assert.equal(reloaded.mode, 'precomputed');
});
