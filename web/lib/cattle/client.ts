import type {
  ApiEnvelope,
  ApiFailure,
  Overview,
  ReviewCommand,
  ReviewReceipt,
  LatestRecording,
} from "./contracts";

async function api<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { ...init, cache: "no-store" });
  const body = (await response.json().catch(() => null)) as
    | (ApiEnvelope<T> & Partial<ApiFailure>)
    | null;
  if (!response.ok)
    throw new Error(
      body?.error?.message ??
        "The control layer is unavailable. Please try again.",
    );
  if (!body || !("data" in body))
    throw new Error("The control layer returned an unexpected response.");
  return body.data;
}
// This is the only data transport imported by client components.
export const monitoringApi = {
  latestRecording: (id: string) =>
    api<LatestRecording>(`/api/cattle/${encodeURIComponent(id)}/recording`),
  overview: () => api<Overview>("/api/overview"),
  review: (id: string, command: ReviewCommand) =>
    api<ReviewReceipt>(`/api/alerts/${encodeURIComponent(id)}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(command),
    }),
};
