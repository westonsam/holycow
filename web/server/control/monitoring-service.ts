import type { ReviewCommand, ReviewReceipt } from "@/lib/cattle/contracts";
import type { MonitoringRepository } from "../repositories/monitoring-repository";

export class ControlError extends Error {
  constructor(
    public code: string,
    message: string,
    public status = 400,
  ) {
    super(message);
  }
}
export interface RequestContext {
  mode: "demo";
  actor: string;
  role: "reviewer";
  requestId: string;
}

export class MonitoringService {
  constructor(private readonly repository: MonitoringRepository) {}
  overview() {
    return this.repository.getOverview();
  }
  async latestRecording(animalId: string) {
    const recording = await this.repository.getLatestRecording(animalId);
    if (!recording)
      throw new ControlError("NOT_FOUND", "That cow was not found.", 404);
    return recording;
  }

  async review(
    alertId: string,
    input: unknown,
    context: RequestContext,
  ): Promise<ReviewReceipt> {
    if (context.mode !== "demo")
      throw new ControlError(
        "NOT_CONFIGURED",
        "Live authentication and data access have not been configured.",
        503,
      );
    const overview = await this.repository.getOverview();
    if (!overview.alerts.some((alert) => alert.id === alertId))
      throw new ControlError("NOT_FOUND", "That finding was not found.", 404);
    if (!input || typeof input !== "object")
      throw new ControlError(
        "INVALID_COMMAND",
        "A review command is required.",
      );
    const command = input as Partial<ReviewCommand>;
    if (!["acknowledge", "accept", "reject"].includes(command.action ?? ""))
      throw new ControlError("INVALID_ACTION", "Choose a valid review action.");
    if (
      typeof command.reason !== "string" ||
      !command.reason.trim() ||
      command.reason.length > 2000
    )
      throw new ControlError(
        "REASON_REQUIRED",
        "Add a review note (up to 2,000 characters).",
      );
    if (
      !Number.isInteger(command.expectedRevision) ||
      command.expectedRevision! < 1 ||
      command.expectedRevision! > 100000
    )
      throw new ControlError(
        "INVALID_REVISION",
        "The review revision is invalid.",
      );
    if (
      typeof command.requestId !== "string" ||
      command.requestId.length < 8 ||
      command.requestId.length > 100
    )
      throw new ControlError(
        "INVALID_REQUEST",
        "A request identifier is required.",
      );
    return {
      alertId,
      lifecycle:
        command.action === "acknowledge"
          ? "acknowledged"
          : command.action === "reject"
            ? "invalidated"
            : "resolved",
      action: command.action!,
      revision: command.expectedRevision! + 1,
      reason: command.reason.trim(),
      actor: context.actor,
      recordedAt: new Date().toISOString(),
      persisted: false,
    };
  }
}
