import { env } from "cloudflare:workers";
import { ControlError } from "./monitoring-service";

export const laptopBindings = () => env as unknown as {
  DB?: D1Database;
  HOLYCOW_LAPTOP_TOKEN?: string;
};

export async function laptopConnection() {
  const { DB, HOLYCOW_LAPTOP_TOKEN: token } = laptopBindings();
  if (!DB || !token) return null;
  const row = await DB.prepare("SELECT url, updated FROM laptop_connection WHERE id = 1").first<{url: string; updated: number}>();
  if (!row || Date.now() - row.updated > 90000) return null;
  return { url: row.url, token };
}

export async function requireLaptop() {
  const connection = await laptopConnection();
  if (!connection) throw new ControlError("BACKEND_OFFLINE", "Demo backend offline. The presenter can turn it on from their laptop.", 503);
  return connection;
}
