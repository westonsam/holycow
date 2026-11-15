import { env } from "cloudflare:workers";
import { context, failure } from "./http";
import { ControlError } from "./monitoring-service";
import { requireLaptop } from "./laptop";

// Only this server module knows the private loopback service URL.
export async function demoFlight(request: Request, path: string[]) {
  const ctx = context();
  try {
    const route = path.join("/");
    const read = request.method === "GET";
    const allowed = read
      ? /^(jobs|jobs\/[a-f0-9]{32}|assets\/(scene-video|reference-video))$/.test(route)
      : /^(jobs|jobs\/[a-f0-9]{32}\/reviews|reset)$/.test(route);
    if (!allowed) throw new ControlError("INVALID_DEMO_PATH", "Unknown demo operation or invalid ID.", 400);
    let body: string | undefined;
    if (!read) {
      const origin = request.headers.get("origin");
      if (origin && origin !== new URL(request.url).origin)
        throw new ControlError("ORIGIN_REJECTED", "Use this application to review demo evidence.", 403);
      if (!request.headers.get("content-type")?.includes("application/json"))
        throw new ControlError("INVALID_CONTENT_TYPE", "Send JSON.", 415);
      body = await request.text();
      if (body.length > 6000) throw new ControlError("BODY_TOO_LARGE", "Request too large.", 413);
      try { JSON.parse(body); } catch { throw new ControlError("INVALID_JSON", "Invalid JSON."); }
    }
    const local = ["127.0.0.1", "localhost", "[::1]"].includes(new URL(request.url).hostname);
    const remote = local ? null : await requireLaptop();
    const service = remote ? `${remote.url}/flight/` : (env as unknown as { HOLYCOW_DEMO_SERVICE_URL?: string }).HOLYCOW_DEMO_SERVICE_URL;
    if (!service) throw new ControlError("DEMO_UNAVAILABLE", "Demo backend offline. Start the laptop backend to process flights.", 503);
    const base = new URL(service);
    if (!['http:', 'https:'].includes(base.protocol) || base.username || base.password)
      throw new ControlError("DEMO_UNAVAILABLE", "Invalid local service configuration.", 503);
    const headers = new Headers();
    if (remote) headers.set("Authorization", `Bearer ${remote.token}`);
    if (!read) headers.set("Content-Type", "application/json");
    if (read && request.headers.has("range")) headers.set("Range", request.headers.get("range")!);
    let response: Response;
    try {
      response = await fetch(new URL(route, base), { method: request.method, headers, body, signal: AbortSignal.timeout(15000), redirect: "manual" });
      if (response.status >= 300 && response.status < 400) throw new Error("Unexpected service redirect");
    } catch (error) {
      console.error("Demo HTTP service request failed", error instanceof Error ? error.message : "Network error");
      throw new ControlError("DEMO_UNAVAILABLE", "Demo backend offline. Start it on the laptop and retry; existing jobs and reviews are retained.", 503);
    }
    const output = new Headers({ "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff" });
    for (const name of ["content-type", "content-length", "accept-ranges", "content-range"])
      if (response.headers.has(name)) output.set(name, response.headers.get(name)!);
    return new Response(response.body, { status: response.status, headers: output });
  } catch (error) {
    if (request.body && !request.bodyUsed) await request.body.cancel().catch(() => undefined);
    return failure(error, ctx.requestId);
  }
}
