import { api } from "./client";
import type { DemoJob, DemoReview } from "./demo-contracts";
const root = "/api/demo-flight";
const post = (body: unknown): RequestInit => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
export const demoApi = {
  list: () => api<DemoJob[]>(`${root}/jobs`),
  get: (id: string) => api<DemoJob>(`${root}/jobs/${encodeURIComponent(id)}`),
  start: (mode: DemoJob["mode"], requestId: string) => api<DemoJob>(`${root}/jobs`, post({ assetId: "scene-flight", mode, requestId })),
  review: (id: string, detectionId: string, action: DemoReview["action"], note: string, expectedSeq: number) => api<DemoJob>(`${root}/jobs/${encodeURIComponent(id)}/reviews`, post({ detectionId, action, note, expectedSeq })),
  reset: () => api(`${root}/reset`, post({})),
  video: `${root}/assets/scene-video`,
  referenceVideo: `${root}/assets/reference-video`,
};
