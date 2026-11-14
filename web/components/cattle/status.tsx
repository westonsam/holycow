import type { Assessment } from "@/lib/cattle/contracts";
export const assessmentLabels: Record<Assessment, string> = {
  priority: "Priority review",
  review: "Review",
  clear: "No clear deviation",
  unable: "Unable to assess",
  unobserved: "Unobserved",
};
export function StatusBadge({ status }: { status: Assessment }) {
  return (
    <span className={`status-badge status-${status}`}>
      {assessmentLabels[status]}
    </span>
  );
}
export function Dot({ status }: { status: Assessment }) {
  return <span className={`status-dot dot-${status}`} aria-hidden="true" />;
}
export function time(value: string | null) {
  return value
    ? new Date(value).toLocaleTimeString("en-US", {
        hour: "numeric",
        minute: "2-digit",
        timeZone: "America/Los_Angeles",
      })
    : "Not observed";
}
