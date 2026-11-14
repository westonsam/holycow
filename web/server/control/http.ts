import {
  ControlError,
  MonitoringService,
  type RequestContext,
} from "./monitoring-service";
import { DemoMonitoringRepository } from "../repositories/demo-repository";

export const monitoring = new MonitoringService(new DemoMonitoringRepository());
export function context(): RequestContext {
  // Explicit demo identity. Never substitute this for a verified production JWT.
  return {
    mode: "demo",
    actor: "Demo reviewer",
    role: "reviewer",
    requestId: crypto.randomUUID(),
  };
}
export function success(data: unknown, requestId: string) {
  return Response.json(
    { data, meta: { mode: "demo", requestId } },
    {
      headers: {
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
      },
    },
  );
}
export function failure(error: unknown, requestId: string) {
  const known = error instanceof ControlError;
  return Response.json(
    {
      error: {
        code: known ? error.code : "INTERNAL_ERROR",
        message: known
          ? error.message
          : "We could not complete that request. Please try again.",
        requestId,
      },
    },
    {
      status: known ? error.status : 500,
      headers: { "Cache-Control": "no-store" },
    },
  );
}
