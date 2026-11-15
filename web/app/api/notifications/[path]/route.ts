import { notifications } from "@/server/control/notifications";
type Context = { params: Promise<{ path: string }> };
export async function GET(request: Request, { params }: Context) { return notifications(request, (await params).path); }
export async function POST(request: Request, { params }: Context) { return notifications(request, (await params).path); }
