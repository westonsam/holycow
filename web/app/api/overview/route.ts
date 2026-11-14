import { monitoring, context, success, failure } from "@/server/control/http";
export async function GET() {
  const ctx = context();
  try {
    return success(await monitoring.overview(), ctx.requestId);
  } catch (error) {
    return failure(error, ctx.requestId);
  }
}
