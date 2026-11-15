"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { Play, RefreshCw, Flag, Maximize } from "lucide-react";
import { demoApi } from "@/lib/cattle/demo-client";
import type { DemoDetection, DemoJob, DemoReview } from "@/lib/cattle/demo-contracts";
import { Dialog } from "./dialog";
import "./demo-flight.css";

const active = (j: DemoJob) => j.state === "queued" || j.state === "running";
const label = (j: DemoJob) => j.mode === "precomputed" ? "Precomputed results · no inference run" : "Local pipeline inference";
const message = (e: unknown) => e instanceof Error ? e.message : "Demo request failed. Retry to reconnect.";
function latestReviews(job: DemoJob) {
  return new Map(job.reviews.map(r => [r.detection, r]));
}

export function DemoFlight() {
  const [jobs, setJobs] = useState<DemoJob[]>([]);
  const [selected, setSelected] = useState<DemoJob | null>(null);
  const [setup, setSetup] = useState(false);
  const [mode, setMode] = useState<DemoJob["mode"]>("precomputed");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [loaded, setLoaded] = useState(false);
  const requestId = useRef<string | null>(null);
  const refresh = useCallback(async () => {
    try { setJobs(await demoApi.list()); setLoaded(true); setError(""); }
    catch (e) { setError(message(e)); }
  }, []);
  useEffect(() => { void refresh(); }, [refresh]);
  useEffect(() => {
    // Keep reconnecting even after an outage; do not fabricate progress.
    const timer = setInterval(() => { void refresh(); }, 2500);
    return () => clearInterval(timer);
  }, [refresh]);
  const open = async (id: string) => {
    setBusy(true);
    try { setSelected(await demoApi.get(id)); setError(""); }
    catch (e) { setError(message(e)); }
    finally { setBusy(false); }
  };
  const start = async () => {
    if (busy || jobs.some(active)) return;
    setBusy(true); setError("");
    // Retain this key on an ambiguous network failure so retry cannot start twice.
    requestId.current ??= crypto.randomUUID().replaceAll("-", "");
    try {
      const job = await demoApi.start(mode, requestId.current);
      requestId.current = null;
      setSetup(false);
      setJobs(await demoApi.list());
      if (job.state === "completed") setSelected(await demoApi.get(job.id));
    } catch (e) { setError(message(e)); }
    finally { setBusy(false); }
  };
  const reset = async () => {
    setBusy(true);
    try { await demoApi.reset(); setJobs([]); setSelected(null); requestId.current = null; setError(""); }
    catch (e) { setError(message(e)); }
    finally { setBusy(false); }
  };
  return <section className="card demo-flight-card">
    <div className="card-title"><h2>Demo flight evidence</h2><button className="primary-button" onClick={() => setSetup(true)} disabled={busy || jobs.some(active)}><Play size={15}/>Process demo flight</button></div>
    <p className="demo-muted">Scene-specific stock drone footage · model observations for human review. Separate from fictional dashboard alerts.</p>
    {error && <div role="alert" className="demo-error">{error} <button className="text-button" onClick={() => void refresh()}>Reconnect</button></div>}
    {!loaded && !error && <p role="status">Connecting to local demo service…</p>}
    {jobs.map(job => {
      const summary = job.summary;
      const flags = [...latestReviews(job).values()].filter(r => r.action === "flag").length;
      return <div className="demo-job" key={job.id}>
        <div><strong>Prepared scene flight</strong><small>{label(job)} · {job.created} UTC</small><code title={job.id}>Job {job.id.slice(0, 8)}</code></div>
        <div><strong className="demo-state">{job.state}</strong><small>{summary ? `${summary.duration.toFixed(2)}s · ${summary.trackCount} detected tracks` : "32.72s clip · track count pending"}</small><small>{flags} flagged observations open · {job.reviews.filter(r => r.action === "flag").length} flags in history</small></div>
        {active(job) && <div className="demo-progress" role="status"><progress max={1} value={job.progress ?? undefined}/><small>{job.mode === "precomputed" ? "Loading prepared results…" : job.progress === null ? "Waiting for pipeline progress…" : `${Math.floor(job.progress * 100)}% of frames processed`}</small></div>}
        {job.state === "completed" && <button className="secondary-button" disabled={busy} onClick={() => void open(job.id)}>Inspect detections</button>}
        {job.state === "failed" && <p className="demo-error" role="alert">{job.error} Start another demo flight to retry.</p>}
      </div>;
    })}
    <div className="demo-footer"><small>Tracks can split or merge. Counts are not a verified cattle census; no health diagnosis is inferred.</small><button className="text-button" disabled={busy || jobs.some(active) || !jobs.length} onClick={() => void reset()}><RefreshCw size={13}/> Reset demo jobs and reviews</button></div>
    {setup && <Dialog title="Process demo flight" subtitle="Local hackathon demo" onClose={() => setSetup(false)}>
      <div className="demo-form"><label>Prepared clip<select aria-label="Prepared clip" defaultValue="scene-flight"><option value="scene-flight">Scene flight · 32.72 seconds · Pexels drone clip</option></select></label>
        <p>The bundled model was trained on this exact scene. Arbitrary footage is not supported and needs new annotations and retraining.</p>
        <label>Processing mode<select aria-label="Processing mode" value={mode} disabled={busy} onChange={e => { setMode(e.target.value as DemoJob["mode"]); requestId.current = null; }}><option value="precomputed">Precomputed results (no inference)</option><option value="inference">Run local Python inference</option></select></label>
        <p>{mode === "precomputed" ? "Loads actual saved pipeline detections. This does not rerun inference or simulate live processing." : "Runs the existing scene segmentation pipeline on CPU in the local HTTP service. This may take several minutes."}</p>
        {error && <p role="alert" className="demo-error">{error}</p>}
        <button className="primary-button" disabled={busy || jobs.some(active)} onClick={() => void start()}>{busy ? "Starting…" : mode === "precomputed" ? "Load precomputed results" : "Start inference job"}</button>
      </div>
    </Dialog>}
    {selected && <Evidence job={selected} onClose={() => { setSelected(null); void refresh(); }} onSaved={setSelected}/>}
  </section>;
}

function Evidence({ job, onClose, onSaved }: { job: DemoJob; onClose(): void; onSaved(job: DemoJob): void }) {
  const video = useRef<HTMLVideoElement>(null);
  const stage = useRef<HTMLDivElement>(null);
  const [seconds, setSeconds] = useState(0);
  const [detection, setDetection] = useState<{ d: DemoDetection; time: number } | null>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");
  const result = job.result!;
  useEffect(() => {
    const element = video.current;
    if (!element) return;
    let token: number;
    let cancelled = false;
    const tick: VideoFrameRequestCallback = (_, metadata) => {
      if (cancelled) return;
      setSeconds(metadata.mediaTime);
      token = element.requestVideoFrameCallback(tick);
    };
    if (element.requestVideoFrameCallback) token = element.requestVideoFrameCallback(tick);
    return () => { cancelled = true; if (token !== undefined) element.cancelVideoFrameCallback(token); };
  }, []);
  const frame = result.frames[Math.min(result.frames.length-1, Math.max(0, Math.floor(seconds * result.fps + .001)))];
  const select = (d: DemoDetection, time: number) => {
    setDetection({ d, time }); setNote(""); setSaved(""); setError("");
    if (video.current) { video.current.pause(); video.current.currentTime = time; }
    setSeconds(time);
  };
  const latest = latestReviews(job);
  const sightings = new Map<number, { d: DemoDetection; time: number }>();
  for (const f of result.frames) for (const d of f.detections)
    if (!sightings.has(d.track)) sightings.set(d.track, { d, time: f.time });
  const head = detection ? latest.get(detection.d.id) : undefined;
  const review = async (action: DemoReview["action"]) => {
    if (!detection || busy) return;
    setBusy(true); setError(""); setSaved("");
    try {
      onSaved(await demoApi.review(job.id, detection.d.id, action, note, head?.seq ?? 0));
      setNote(""); setSaved("Decision saved to local SQLite history.");
    } catch (e) {
      setError(message(e));
      try { onSaved(await demoApi.get(job.id)); } catch { /* keep evidence and unsaved note */ }
    } finally { setBusy(false); }
  };
  return <Dialog title="Flight evidence" subtitle={label(job)} wide onClose={onClose}>
    <div className="demo-evidence">
      <p className="demo-muted">Location: Farm in the Netherlands</p>
      <p>{result.duration.toFixed(2)} seconds · Completed · {result.trackCount} detected tracks · {[...latest.values()].filter(r => r.action === "flag").length} open flags</p>
      <p className="demo-muted">Video track IDs are temporary geometric associations, not registered cattle identities. Boxes are approximate model predictions.</p>
      <div className="demo-stage" ref={stage} style={{ aspectRatio: `${result.width}/${result.height}` }}>
        <video ref={video} src={demoApi.video} controls controlsList="nofullscreen" playsInline preload="auto" onTimeUpdate={e => setSeconds(e.currentTarget.currentTime)} onSeeked={e => setSeconds(e.currentTarget.currentTime)} onError={() => setError("Video unavailable. Prepare the local playback asset, then reopen this viewer.")}/>
        <svg className="demo-overlay" viewBox={`0 0 ${result.width} ${result.height}`} aria-label="Detection boxes aligned to source video pixels">
          {frame?.detections.map(d => <rect key={d.id} x={d.box[0]} y={d.box[1]} width={d.box[2]-d.box[0]} height={d.box[3]-d.box[1]} className={d.id === detection?.d.id ? "selected" : ""} onClick={() => select(d, frame.time)}><title>Video track {d.track}, {frame.time.toFixed(2)}s</title></rect>)}
        </svg>
      </div>
      <div className="demo-footer"><span>Playback {seconds.toFixed(2)}s · frame {frame?.frame}</span><button className="text-button" onClick={() => void stage.current?.requestFullscreen().catch(e => setError(message(e)))}><Maximize size={14}/> Fullscreen evidence</button></div>
      <div className="demo-evidence-columns">
        <div><div className="demo-form"><label>Jump to first track sighting<select aria-label="Jump to first track sighting" value="" onChange={e => { const sighting = sightings.get(Number(e.target.value)); if (sighting) select(sighting.d, sighting.time); }}><option value="">Select a timestamped detection…</option>{[...sightings.values()].map(({ d, time }) => <option key={d.track} value={d.track}>Video track {d.track} · {time.toFixed(2)}s</option>)}</select></label></div>
          <h3 className="demo-detection-heading">Detections at playback time</h3><div className="demo-detections">{frame?.detections.map(d => <button key={d.id} className={`secondary-button ${d.id === detection?.d.id ? "demo-selected" : ""}`} onClick={() => select(d, frame.time)}>Track {d.track} · {frame.time.toFixed(2)}s</button>)}</div>
          <h3>Flagged observations</h3><div className="demo-flags">{[...latest.values()].map(r => {
            const f = result.frames.find(f => f.detections.some(d => d.id === r.detection));
            const d = f?.detections.find(d => d.id === r.detection);
            return d && f && <button className="secondary-button" key={r.detection} onClick={() => select(d, f.time)}>Track {d.track} · {f.time.toFixed(2)}s · {r.action === "flag" ? "Open flag" : r.action === "resolve" ? "Resolved" : "Rejected"}</button>;
          })}{latest.size === 0 && <p className="demo-muted">No flags yet. Select a box or detection.</p>}</div>
        </div>
        <div className="demo-form"><h3>Observation review</h3>{detection ? <>
          <p><strong>Video track {detection.d.track} at {detection.time.toFixed(2)}s</strong><br/>Observation {detection.d.id} · {head ? head.action === "flag" ? "Open flag" : head.action === "resolve" ? "Resolved" : "Rejected" : "Not flagged"}</p>
          <label>Review note<textarea maxLength={2000} value={note} onChange={e => setNote(e.target.value)} placeholder="Describe the observation or reason for your decision"/></label>
          <div className="demo-review-actions">{head?.action === "flag" ? <><button className="primary-button" disabled={busy || !note.trim()} onClick={() => void review("resolve")}>Resolve flag</button><button className="secondary-button" disabled={busy || !note.trim()} onClick={() => void review("reject")}>Reject flag</button></> : <button className="primary-button" disabled={busy || !note.trim()} onClick={() => void review("flag")}><Flag size={14}/> Flag for review</button>}</div>
          <h3>Saved review history</h3>{job.reviews.filter(r => r.detection === detection.d.id).map(r => <div className="demo-history" key={r.seq}><strong>{r.action} · Demo reviewer</strong><small>{r.created} UTC</small><p>{r.note}</p></div>)}
        </> : <p>Select a detection to seek to its timestamp, add a note, and flag it for review.</p>}
          {busy && <p role="status">Saving…</p>}{saved && <p role="status">{saved}</p>}{error && <p className="demo-error" role="alert">{error}</p>}
        </div>
      </div>
    </div>
  </Dialog>;
}
