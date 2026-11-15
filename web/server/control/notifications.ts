import { env } from "cloudflare:workers";
import { context, failure } from "./http";
import { ControlError } from "./monitoring-service";

export async function notifications(request: Request, path: string) {
  const ctx = context();
  try {
    // The current dashboard has no production user authentication. This operator
    // console is local-only until a verified user/tenant boundary is integrated.
    if (!["127.0.0.1", "localhost", "[::1]"].includes(new URL(request.url).hostname))
      throw new ControlError("NOT_CONFIGURED", "The messaging console is only available in the local operator app.", 403);
    const read = request.method === "GET";
    const videoToken = path.match(/^video\/([A-Za-z0-9_-]{32})$/)?.[1];
    const target = read ? videoToken ? `/v/${videoToken}` : { status: "/v1/notifications", "training-candidates": "/v1/training-candidates" }[path]
      : { sample: "/v1/sample", "simulate-reply": "/v1/simulate-reply", "telegram-demo": "/v1/telegram-demo" }[path];
    if (!target) throw new ControlError("INVALID_OPERATION", "Unknown notification operation.", 400);
    let body: string | undefined;
    if (!read) {
      if (request.headers.get("origin") && request.headers.get("origin") !== new URL(request.url).origin)
        throw new ControlError("ORIGIN_REJECTED", "Use this application to request notifications.", 403);
      if (!request.headers.get("content-type")?.includes("application/json"))
        throw new ControlError("INVALID_CONTENT_TYPE", "Send JSON.", 415);
      body = await request.text();
      if (body.length > 6000) throw new ControlError("BODY_TOO_LARGE", "Request too large.", 413);
      try { JSON.parse(body); } catch { throw new ControlError("INVALID_JSON", "Invalid JSON."); }
    }
    const bindings = env as unknown as { HOLYCOW_NOTIFICATIONS_URL?: string; HOLYCOW_NOTIFICATIONS_TOKEN?: string };
    if (!bindings.HOLYCOW_NOTIFICATIONS_URL || !bindings.HOLYCOW_NOTIFICATIONS_TOKEN)
      throw new ControlError("NOT_CONFIGURED", "Start the notification backend and configure its server-side URL and token. See backend/README.md.", 503);
    const base = new URL(bindings.HOLYCOW_NOTIFICATIONS_URL);
    if (!['http:', 'https:'].includes(base.protocol) || base.username || base.password)
      throw new ControlError("NOT_CONFIGURED", "Invalid backend configuration.", 503);
    let response: Response;
    try {
      response = await fetch(new URL(target, base), {
        method: request.method, body, redirect: "manual", signal: AbortSignal.timeout(15000),
        headers: { Authorization: `Bearer ${bindings.HOLYCOW_NOTIFICATIONS_TOKEN}`, ...(read ? {} : { "Content-Type": "application/json" }), ...(videoToken && request.headers.get("range") ? { Range: request.headers.get("range")! } : {}) },
      });
      if (response.status >= 300 && response.status < 400) throw new Error("Unexpected redirect");
    } catch {
      throw new ControlError("BACKEND_UNAVAILABLE", "Notification backend unavailable. Queued messages and saved feedback are retained; reconnect to check their status.", 503);
    }
    if (response.status === 401) throw new ControlError("NOT_CONFIGURED", "The notification backend token does not match the web configuration.", 503);
    const headers = new Headers({ "Content-Type": "application/json", "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer" });
    if (videoToken) for (const name of ["content-type", "content-length", "content-range", "accept-ranges", "content-disposition"])
      if (response.headers.has(name)) headers.set(name, response.headers.get(name)!);
    return new Response(response.body, { status: response.status, headers });
  } catch (error) {
    if (request.body && !request.bodyUsed) await request.body.cancel().catch(() => undefined);
    return failure(error, ctx.requestId);
  }
}
