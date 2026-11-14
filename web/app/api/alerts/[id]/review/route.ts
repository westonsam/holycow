import { monitoring, context, success, failure } from "@/server/control/http";
import { ControlError } from "@/server/control/monitoring-service";
export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const ctx = context();
  try {
    const origin = request.headers.get("origin");
    if (origin && new URL(origin).origin !== new URL(request.url).origin)
      throw new ControlError(
        "ORIGIN_REJECTED",
        "This review must originate from this application.",
        403,
      );
    if (!request.headers.get("content-type")?.includes("application/json"))
      throw new ControlError(
        "INVALID_CONTENT_TYPE",
        "Send a JSON review command.",
        415,
      );
    const raw = await request.text();
    if (raw.length > 6000)
      throw new ControlError(
        "BODY_TOO_LARGE",
        "The review request is too large.",
        413,
      );
    let input: unknown;
    try {
      input = JSON.parse(raw);
    } catch {
      throw new ControlError(
        "INVALID_JSON",
        "The review request is not valid JSON.",
      );
    }
    const { id } = await params;
    return success(await monitoring.review(id, input, ctx), ctx.requestId);
  } catch (error) {
    // Release rejected request streams before returning an early error.
    // This also keeps persistent proxy connections usable for subsequent requests.
    if (request.body && !request.bodyUsed) {
      await request.body.cancel().catch(() => undefined);
    }
    return failure(error, ctx.requestId);
  }
}
