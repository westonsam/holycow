import { test } from 'node:test';
import assert from 'node:assert/strict';
const origin = process.env.TEST_ORIGIN || 'http://127.0.0.1:8790';
const root = `${origin}/api/notifications`;
const post = body => ({method:'POST', headers:{'Content-Type':'application/json', Origin:origin}, body:JSON.stringify(body)});
async function snapshot() {
  const response = await fetch(`${root}/status`);
  assert.equal(response.status, 200);
  return (await response.json()).data;
}
async function until(predicate) {
  for (let n=0; n<80; n++) {
    const data = await snapshot();
    if (predicate(data)) return data;
    await new Promise(resolve=>setTimeout(resolve,100));
  }
  assert.fail('Notification worker did not reach expected state');
}

test('notification control layer restricts commands and validates input', async()=>{
  assert.equal((await fetch(`${root}/alerts`,post({source:'live'}))).status,400);
  assert.equal((await fetch(`${root}/sample`,{...post({}),headers:{'Content-Type':'application/json',Origin:'https://foreign.example'}})).status,403);
  assert.equal((await fetch(`${root}/simulate-reply`,{method:'POST',body:'{}'})).status,415);
  assert.equal((await fetch(`${root}/simulate-reply`,post({body:'x',messageId:'short'}))).status,422);
  assert.equal((await fetch(`${root}/sample`,{...post({}),body:'{'})).status,400);
});

test('simulated notification includes context and persists correlated feedback', async()=>{
  const response=await fetch(`${root}/sample`,post({}));
  assert.equal(response.status,200);
  const alert=(await response.json()).data;
  const delivered=await until(data=>data.alerts.find(a=>a.id===alert.id)?.state==='simulated');
  const message=delivered.messages.find(m=>m.alert===alert.id && m.direction==='outgoing');
  assert.equal(message.transport,'simulator');
  for(const content of ['Cow 718','Netherlands','Reason:','Video:']) assert.ok(message.body.includes(content));
  assert.equal(message.body.split('\n').length,4);
  assert.ok(!message.body.includes(alert.code));
  assert.ok(!message.body.includes(alert.modelVersion));
  const token=message.body.match(/\/v\/([A-Za-z0-9_-]{32})$/)?.[1];
  if(token) {
    const video=await fetch(`${root}/video/${token}`,{headers:{Range:'bytes=0-31'}});
    assert.equal(video.status,206);
    assert.equal((await video.arrayBuffer()).byteLength,32);
    assert.equal(video.headers.get('content-type'),'video/mp4');
  }
  const command={body:`${alert.code} FALSE Test review: animal was resting.`,messageId:crypto.randomUUID().replaceAll('-','')};
  assert.equal((await fetch(`${root}/simulate-reply`,post(command))).status,200);
  assert.equal((await fetch(`${root}/simulate-reply`,post(command))).status,200);
  const saved=await until(data=>data.alerts.find(a=>a.id===alert.id)?.feedback.length===1);
  const reviewed=saved.alerts.find(a=>a.id===alert.id);
  assert.equal(reviewed.feedback[0].verdict,'false_positive');
  const exported=(await (await fetch(`${root}/training-candidates`)).json()).data.find(item=>item.alertCode===alert.code);
  assert.equal(exported.eligibleForTraining,false);
  assert.equal(exported.requiresIndependentReview,true);
  assert.equal(exported.modelVersion,alert.modelVersion);
});

test('everyday feedback uses a short confirmation instead of command syntax', async()=>{
  const alert=(await (await fetch(`${root}/sample`,post({}))).json()).data;
  const reply=async body=>fetch(`${root}/simulate-reply`,post({body:`${alert.code} ${body}`,messageId:crypto.randomUUID().replaceAll('-','')}));
  assert.equal((await reply("She's fine, just resting.")).status,200);
  const draft=await until(data=>data.messages.some(m=>m.alert===alert.id && m.body.includes('Is that right?')));
  assert.equal(draft.alerts.find(a=>a.id===alert.id).feedback.length,0);
  assert.equal((await reply('yep!')).status,200);
  const saved=await until(data=>data.alerts.find(a=>a.id===alert.id)?.feedback.length===1);
  assert.equal(saved.alerts.find(a=>a.id===alert.id).feedback[0].verdict,'false_positive');
});

test('reply context is separate metadata and rancher text contains no alert code', async()=>{
  const alert=(await (await fetch(`${root}/sample`,post({}))).json()).data;
  const sent=await until(data=>data.messages.some(m=>m.alert===alert.id && m.direction==='outgoing' && m.state==='simulated'));
  const previous=sent.messages.find(m=>m.alert===alert.id && m.direction==='outgoing');
  const body="She's fine, just resting.";
  const command={body,messageId:crypto.randomUUID().replaceAll('-',''),replyToMessageId:previous.id};
  assert.equal((await fetch(`${root}/simulate-reply`,post(command))).status,200);
  const proposed=await until(data=>data.messages.some(m=>m.alert===alert.id && m.body.includes('Is that right?')));
  assert.ok(proposed.messages.some(m=>m.alert===alert.id && m.direction==='incoming' && m.body===body));
  const question=proposed.messages.find(m=>m.alert===alert.id && m.body.includes('Is that right?'));
  assert.equal((await fetch(`${root}/simulate-reply`,post({body:'yep',messageId:crypto.randomUUID().replaceAll('-',''),replyToMessageId:question.id}))).status,200);
  const saved=await until(data=>data.alerts.find(a=>a.id===alert.id)?.feedback.length===1);
  assert.equal(saved.alerts.find(a=>a.id===alert.id).feedback[0].note,body);
  assert.equal((await fetch(`${root}/simulate-reply`,post({body:'fine',messageId:crypto.randomUUID().replaceAll('-',''),replyToMessageId:'a'.repeat(32)}))).status,422);
});
