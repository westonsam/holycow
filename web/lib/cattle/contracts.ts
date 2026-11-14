export type Assessment =
  | "priority"
  | "review"
  | "clear"
  | "unable"
  | "unobserved";
export type Section = "overview" | "map" | "cattle" | "flights" | "spotlight";
export type AlertLifecycle =
  | "open"
  | "acknowledged"
  | "resolved"
  | "invalidated";
export interface Animal {
  id: string;
  tag: string;
  herdId: string;
  assessment: Assessment;
  observedAt: string | null;
  mapPosition: { x: number; y: number } | null;
  metric: string;
  metricValue: string;
  modelVersion: string;
}
export interface Herd {
  id: string;
  name: string;
  pasture: string;
  pastureId: string;
}
export interface NonCowDetection {
  id: string;
  pastureId: string;
  observedAt: string;
  mapPosition: { x: number; y: number };
  label: "Non-cow detected";
}
export interface LatestRecording {
  animalId: string;
  availability: "ready" | "unavailable";
  capturedAt: string | null;
  playbackUrl: string | null;
  thumbnailUrl: string | null;
  message: string;
}
export interface HerdAlert {
  id: string;
  animalId: string;
  severity: "priority" | "review" | "unable";
  title: string;
  description: string;
  observedAt: string;
  lifecycle: AlertLifecycle;
  model: string;
  confidence: number | null;
  revision: number;
}
export interface Flight {
  id: string;
  name: string;
  drone: string;
  startedAt: string;
  durationMinutes: number;
  coveragePercent: number | null;
  observedAnimals: number;
  batteryPercent: number;
  status: "complete" | "processing" | "planned";
  clips: number;
}
export interface Overview {
  mode: "demo";
  ranch: string;
  snapshotAt: string;
  referenceNow: string;
  herds: Herd[];
  animals: Animal[];
  nonCowDetections: NonCowDetection[];
  alerts: HerdAlert[];
  flights: Flight[];
  capabilities: {
    liveConnected: false;
    persistence: "browser";
    reviewEnabled: true;
  };
}
export interface ReviewCommand {
  action: "acknowledge" | "accept" | "reject";
  reason: string;
  expectedRevision: number;
  requestId: string;
}
export interface ReviewReceipt {
  alertId: string;
  lifecycle: AlertLifecycle;
  revision: number;
  action: ReviewCommand["action"];
  reason: string;
  actor: string;
  recordedAt: string;
  persisted: false;
}
export interface ApiEnvelope<T> {
  data: T;
  meta: { mode: "demo"; requestId: string };
}
export interface ApiFailure {
  error: { code: string; message: string; requestId: string };
}
