"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { Bell, Send, RefreshCw } from "lucide-react";
import { notificationApi } from "@/lib/cattle/notification-client";
import type { NotificationSnapshot } from "@/lib/cattle/notification-contracts";
import "./notifications.css";
const errorMessage = (e: unknown) => e instanceof Error ? e.message : "Notification request failed.";
const rancherText = (text: string) => text.replace(/\bHC-[A-F0-9]{8}\b[ :\t]*/gi, '').trim();

export function Notifications() {
  const [data, setData] = useState<NotificationSnapshot | null>(null);
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const [selected, setSelected] = useState("");
  const [busy, setBusy] = useState(false);
  const [receipt, setReceipt] = useState("");
  const pendingDemo = useRef<string | null>(null);
  const submitting = useRef(false);
  const refresh = useCallback(async () => {
    try { setData(await notificationApi.snapshot()); setError(""); }
    catch (e) { setError(errorMessage(e)); setData(s => s ? { ...s, health: { ...s.health, ready: false } } : s); }
  }, []);
  useEffect(() => { void refresh(); const timer = setInterval(() => void refresh(), 2500); return () => clearInterval(timer); }, [refresh]);
  const sendDemo = async () => {
    if (submitting.current) return;
    submitting.current = true;
    setBusy(true); setReceipt(""); setActionError("");
    // Retry uncertain HTTP responses with the same durable request ID.
    pendingDemo.current ??= crypto.randomUUID().replaceAll("-", "");
    try {
      const alert = await notificationApi.telegramDemo(pendingDemo.current);
      pendingDemo.current = null;
      setSelected(alert.id);
      setReceipt("Demo requested. Check delivery status below, then reply to the video in Telegram.");
      await refresh();
    } catch (e) { setActionError(errorMessage(e)); }
    finally { submitting.current = false; setBusy(false); }
  };
  const alerts = data?.alerts.filter(a => a.source === "live" || a.telegramDemo) ?? [];
  const alert = alerts.find(a => a.id === selected);
  const outgoing = data?.messages.filter(m => m.alert === selected && m.direction === "outgoing" && m.kind === "alert") ?? [];
  const connected = data?.health.ready && data.health.transport === "telegram" && data.health.telegramConfigured;
  return <div className="notifications-page">
    <section className="card notifications-intro"><div className="card-title"><h2><Bell size={18}/> Telegram alerts</h2><button className="secondary-button" onClick={() => void refresh()}><RefreshCw size={14}/> Reconnect</button></div>
      <p>Receive cow tag, reason, location and video on your phone. Reply in Telegram to tell the assistant whether the alert was valid.</p>
      <div className="notification-mode"><strong>{error ? "Demo backend offline" : data ? data.health.ready ? "Backend worker running" : "Backend worker needs attention" : "Connecting to backend…"}</strong><span>Transport: {data?.health.transport ?? "unknown"} · Feedback: {data?.health.agent ?? "unknown"}</span></div>
      <p className="notification-muted">{data?.health.transport === "telegram" ? data.health.telegramUpdates === "webhook" ? "Telegram webhook mode enabled." : `Telegram polling · ${data.health.telegramReceiverReady ? "receiving replies" : "waiting for connection"}.` : "Telegram is not connected. Run the local Telegram setup to link your bot and rancher chat."}</p>
      <p className="notification-muted">This sends a real Telegram video to your configured chat, labeled DEMO ONLY. Cow 718, the location and the observation are fictional; the video is illustrative demo footage. The scene model does not identify registered cows or diagnose health conditions.</p>
      {error && <p className="notification-error" role="alert">{error}</p>}
      {actionError && <p className="notification-error" role="alert">{actionError}</p>}
      <button className="primary-button" disabled={busy || !connected} onClick={() => void sendDemo()}><Send size={15}/> {busy ? "Requesting demo…" : "Send demo to Telegram"}</button>
      {receipt && <p role="status">{receipt}</p>}
    </section>
    <div className="notification-columns"><section className="card notification-alerts"><h2>Notification history</h2>{!alerts.length && <p>No Telegram alerts yet. Send a demo to test phone delivery and feedback.</p>}
      {alerts.map(a => <button className={`notification-alert ${selected === a.id ? "notification-selected" : ""}`} key={a.id} onClick={() => setSelected(a.id)}><strong>Cow {a.cowNumber}</strong><span>{a.location}</span><small>{a.telegramDemo ? "Telegram demo · fictional observation" : "Ingested observation"} · {a.state}</small><span>{a.summary}</span><small>{a.feedback.length ? `Latest feedback: ${a.feedback[a.feedback.length-1].verdict.replaceAll("_", " ")}` : "Awaiting rancher feedback"}</small></button>)}
    </section>
    <section className="card notification-details"><h2>Delivery and feedback</h2><p>All messaging happens in Telegram. Use Reply on the video and say, for example, “she’s fine, just resting.” Confirm the assistant’s interpretation when asked.</p>
      {alert ? <>
        <p><strong>Cow {alert.cowNumber}</strong> · {alert.location}</p>
        <p>Processing status: <strong>{alert.state}</strong>{alert.state === "sent" && " · Accepted by Telegram; device delivery and read status are unavailable."}</p>
        {outgoing.map(m => m.error && <p className="notification-error" key={m.id}>{m.error}</p>)}
        <div className="notification-feedback"><h3>Saved feedback</h3>{alert.feedback.map((f, i) => <article key={i}><strong>{f.verdict.replaceAll("_", " ")}</strong><p>{rancherText(f.note)}</p><small>{f.method} · {new Date(f.created*1000).toLocaleString()}</small></article>)}{!alert.feedback.length && <p>No confirmed feedback yet. Reply in Telegram to review this observation.</p>}</div>
      </> : <p className="notification-muted">Select an alert to inspect its delivery status and saved review.</p>}
      <p className="notification-muted">Original messages and decisions stay in the backend. Demo feedback is synthetic and is not eligible for model training.</p><a className="text-button" href="/api/notifications/training-candidates" target="_blank" rel="noreferrer">View feedback export for model review</a>
    </section></div>
  </div>;
}
