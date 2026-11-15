export type DemoDetection = { id: string; track: number; box: [number, number, number, number] };
export type DemoFrame = { frame: number; time: number; detections: DemoDetection[] };
export type DemoResult = { width: number; height: number; fps: number; duration: number; trackCount: number; frames: DemoFrame[] };
export type DemoReview = { seq: number; detection: string; action: "flag" | "resolve" | "reject"; note: string; created: string };
export type DemoJob = {
  id: string; mode: "inference" | "precomputed";
  state: "queued" | "running" | "completed" | "failed";
  progress: number | null; error: string | null; created: string;
  result: DemoResult | null; summary?: { duration: number; trackCount: number } | null;
  reviews: DemoReview[];
};
