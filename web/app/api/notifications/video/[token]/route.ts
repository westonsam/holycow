import { notifications } from "@/server/control/notifications";
export async function GET(request: Request, { params }: { params: Promise<{ token: string }> }) {
  return notifications(request, `video/${(await params).token}`);
}
