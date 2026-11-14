import type {
  Animal,
  Assessment,
  Overview,
  LatestRecording,
} from "@/lib/cattle/contracts";
import type { MonitoringRepository } from "./monitoring-repository";
import { demoPosition } from "@/lib/cattle/map-layout";

const at = (time: string) => `2026-11-14T${time}:00-08:00`;
const animals: Animal[] = Array.from({ length: 90 }, (_, i) => {
  const herd = i < 45 ? 1 : 2;
  const n = i % 45;
  const assessment: Assessment =
    n >= 41
      ? "unobserved"
      : n < (herd === 1 ? 2 : 1)
        ? "priority"
        : n < (herd === 1 ? 6 : 6)
          ? "review"
          : herd === 1 && n === 6
            ? "unable"
            : "clear";
  const tag =
    i === 0
      ? "718"
      : i === 45
        ? "826"
        : i === 46
          ? "904"
          : i === 6
            ? "652"
            : String(300 + i);
  // Illustrative map-space only. These are NOT georeferenced ground coordinates.
  return {
    id: `cow-${tag}`,
    tag,
    herdId: `herd-${herd}`,
    assessment,
    observedAt:
      assessment === "unobserved"
        ? null
        : at(tag === "904" ? "07:58" : tag === "652" ? "07:21" : "08:42"),
    mapPosition:
      assessment === "unobserved" ? null : demoPosition(n, `herd-${herd}`),
    metric:
      assessment === "unable"
        ? "Gait / locomotion"
        : tag === "904"
          ? "Estrus behavior"
          : "Gait / locomotion",
    metricValue:
      assessment === "unable" || assessment === "unobserved"
        ? "Not assessed"
        : assessment === "priority"
          ? "4 / 5"
          : tag === "904"
            ? "72 / 100"
            : assessment === "review"
              ? "3 / 5"
              : "1 / 5",
    modelVersion:
      tag === "904" ? "Estrus behavior · demo v1.0" : "Locomotion · demo v2.1",
  };
});

export const demoOverview: Overview = {
  mode: "demo",
  ranch: "North Creek Ranch",
  snapshotAt: at("08:42"),
  referenceNow: at("08:54"),
  capabilities: {
    liveConnected: false,
    persistence: "browser",
    reviewEnabled: true,
  },
  herds: [
    {
      id: "herd-1",
      name: "Herd 1",
      pasture: "North pasture",
      pastureId: "pasture-north",
    },
    {
      id: "herd-2",
      name: "Herd 2",
      pasture: "South pasture",
      pastureId: "pasture-south",
    },
  ],
  animals,
  nonCowDetections: [
    {
      id: "other-1",
      pastureId: "pasture-north",
      observedAt: at("08:42"),
      mapPosition: { x: 43, y: 32 },
      label: "Non-cow detected",
    },
    {
      id: "other-2",
      pastureId: "pasture-south",
      observedAt: at("08:42"),
      mapPosition: { x: 62, y: 68 },
      label: "Non-cow detected",
    },
  ],
  alerts: [
    {
      id: "alert-718",
      animalId: "cow-718",
      severity: "priority",
      title: "Locomotion needs a closer look",
      description:
        "The demo model flagged a change in gait. Review the observation before making a health decision. This is a suspected finding, not a diagnosis.",
      observedAt: at("08:42"),
      lifecycle: "open",
      model: "Locomotion · demo v2.1",
      confidence: 0.87,
      revision: 1,
    },
    {
      id: "alert-904",
      animalId: "cow-904",
      severity: "review",
      title: "Review estrus behavior",
      description:
        "An elevated demo behavior score is ready for review. Heat refers to estrus behavior, not body temperature or confirmed reproductive status.",
      observedAt: at("07:58"),
      lifecycle: "open",
      model: "Estrus behavior · demo v1.0",
      confidence: 0.74,
      revision: 1,
    },
    {
      id: "alert-652",
      animalId: "cow-652",
      severity: "unable",
      title: "Unable to assess locomotion",
      description:
        "Occlusion prevented a useful gait assessment. A missing score is not evidence of healthy movement. Review a later observation when available.",
      observedAt: at("07:21"),
      lifecycle: "open",
      model: "Locomotion · demo v2.1",
      confidence: null,
      revision: 1,
    },
  ],
  flights: [
    {
      id: "flight-104",
      name: "Morning pasture sweep",
      drone: "Drone 01",
      startedAt: at("08:24"),
      durationMinutes: 18,
      coveragePercent: 91,
      observedAnimals: 82,
      batteryPercent: 78,
      status: "complete",
      clips: 82,
    },
    {
      id: "flight-103",
      name: "Early check-in",
      drone: "Drone 01",
      startedAt: at("07:02"),
      durationMinutes: 19,
      coveragePercent: 86,
      observedAnimals: 77,
      batteryPercent: 94,
      status: "complete",
      clips: 77,
    },
  ],
};

export class DemoMonitoringRepository implements MonitoringRepository {
  async getOverview(): Promise<Overview> {
    return structuredClone(demoOverview);
  }
  async getLatestRecording(animalId: string): Promise<LatestRecording | null> {
    if (!animals.some((animal) => animal.id === animalId)) return null;
    return {
      animalId,
      availability: "unavailable",
      capturedAt: null,
      playbackUrl: null,
      thumbnailUrl: null,
      message:
        "Live recordings are not connected. Attach a recorded clip to preview it in this browser.",
    };
  }
}
