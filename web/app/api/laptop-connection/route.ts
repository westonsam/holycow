import { laptopBindings } from "@/server/control/laptop";

export async function POST(request: Request) {
  const { DB, HOLYCOW_LAPTOP_TOKEN: token } = laptopBindings();
  if (!DB || !token || request.headers.get("Authorization") !== `Bearer ${token}`)
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  if (request.headers.has("Origin")) return new Response(null, { status: 403 });
  const raw = await request.text();
  if (raw.length > 1000) return new Response(null, { status: 413 });
  try {
    const { url, offline } = JSON.parse(raw);
    if (offline === true) {
      await DB.prepare("DELETE FROM laptop_connection WHERE id = 1").run();
    } else {
      const endpoint = new URL(url);
      if (endpoint.protocol !== "https:" || !/^[a-z0-9-]+\.trycloudflare\.com$/.test(endpoint.hostname) || endpoint.port || endpoint.username || endpoint.password || endpoint.pathname !== "/" || endpoint.search || endpoint.hash)
        return new Response(null, { status: 400 });
      await DB.prepare("INSERT INTO laptop_connection (id, url, updated) VALUES (1, ?, ?) ON CONFLICT(id) DO UPDATE SET url=excluded.url, updated=excluded.updated").bind(endpoint.origin, Date.now()).run();
    }
    return Response.json({ connected: offline !== true }, { headers: { "Cache-Control": "no-store" } });
  } catch {
    return Response.json({ error: "Invalid connection request" }, { status: 400 });
  }
}
