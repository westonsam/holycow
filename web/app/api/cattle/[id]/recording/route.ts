import { monitoring, context, success, failure } from "@/server/control/http";
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const ctx = context();
  try {
    const { id } = await params;
    return success(await monitoring.latestRecording(id), ctx.requestId);
  } catch (error) {
    return failure(error, ctx.requestId);
  }
}
