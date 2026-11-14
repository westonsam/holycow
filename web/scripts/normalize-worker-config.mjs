import { readFileSync, writeFileSync } from 'node:fs';

// The supplied Vite adapter emits a field removed by current Wrangler releases.
// Removing it preserves the former default (each environment is its own Worker).
const path = new URL('../dist/server/wrangler.json', import.meta.url);
const config = JSON.parse(readFileSync(path, 'utf8'));
if ('legacy_env' in config) {
  delete config.legacy_env;
  writeFileSync(path, JSON.stringify(config));
}
