import { api } from "./client";
import type { NotificationAlert, NotificationSnapshot } from "./notification-contracts";
const root = "/api/notifications";
const post = (body: unknown): RequestInit => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
export const notificationApi = {
  snapshot: () => api<NotificationSnapshot>(`${root}/status`),
  telegramDemo: (requestId: string) => api<NotificationAlert>(`${root}/telegram-demo`, post({ requestId })),
  sample: () => api<NotificationAlert>(`${root}/sample`, post({})),
  reply: (body: string, messageId: string, replyToMessageId?: string) => api(`${root}/simulate-reply`, post({ body, messageId, ...(replyToMessageId ? { replyToMessageId } : {}) })),
};
