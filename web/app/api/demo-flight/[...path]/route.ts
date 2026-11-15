import { demoFlight } from "@/server/control/demo-flight";
type RouteContext = { params: Promise<{ path: string[] }> };
export async function GET(request: Request, { params }: RouteContext) {
  return demoFlight(request, (await params).path);
}
export async function POST(request: Request, { params }: RouteContext) {
  return demoFlight(request, (await params).path);
}
