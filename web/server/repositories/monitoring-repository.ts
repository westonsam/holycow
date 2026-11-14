import type { Overview, LatestRecording } from "@/lib/cattle/contracts";

// Implement this interface in the application backend to connect PostgreSQL later.
// The browser never receives a database connection or privileged Supabase credential.
export interface MonitoringRepository {
  getOverview(): Promise<Overview>;
  getLatestRecording(animalId: string): Promise<LatestRecording | null>;
}
