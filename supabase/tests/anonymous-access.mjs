// Uses public project configuration only. Never provide a service/secret key.
// Run from the repo root: node --env-file=.env.local supabase/tests/anonymous-access.mjs
const base = process.env.SUPABASE_URL;
const key = process.env.SUPABASE_PUBLISHABLE_KEY;
if (!base || !key?.startsWith('sb_publishable_')) {
  throw new Error('Set project URL and a modern publishable key in .env.local');
}
const response = await fetch(`${base}/rest/v1/animal?select=id`, {
  headers: { apikey: key, 'Accept-Profile': 'cattle' },
  signal: AbortSignal.timeout(15000)
});
const body = await response.json();
if (response.status === 406 && body.code === 'PGRST106') {
  console.log('PASS: private cattle schema is not exposed through the Data API.');
} else if ([401,403].includes(response.status) && body.code === '42501') {
  console.log('PASS: cattle API exists; anonymous cattle access is denied.');
} else {
  throw new Error(`Unexpected anonymous response: status=${response.status}, code=${body.code ?? 'none'}`);
}
