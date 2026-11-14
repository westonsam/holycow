"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Star,
  Plus,
  Search,
  Play,
  Film,
  Clock3,
  Bell,
  ArrowUpRight,
  X,
  Upload,
  Loader2,
  Check,
  Trash2,
  Video,
  RefreshCw,
} from "lucide-react";
import type {
  Animal,
  Herd,
  HerdAlert,
  LatestRecording,
} from "@/lib/cattle/contracts";
import { monitoringApi } from "@/lib/cattle/client";
import {
  getLocalRecording,
  saveLocalRecording,
  deleteLocalRecording,
  inspectVideo,
  clipTime,
  durationLabel,
  type LocalRecording,
} from "@/lib/cattle/local-recordings";
import { Dialog } from "./dialog";
import { StatusBadge, time } from "./status";

interface Props {
  animals: Animal[];
  herds: Herd[];
  alerts: HerdAlert[];
  favoriteIds: string[];
  toggleFavorite(id: string): void;
  openAnimal(animal: Animal): void;
}
export function Spotlight({
  animals,
  herds,
  alerts,
  favoriteIds,
  toggleFavorite,
  openAnimal,
}: Props) {
  const [picker, setPicker] = useState(false),
    [search, setSearch] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [clips, setClips] = useState<Record<string, LocalRecording>>({});
  const [urls, setUrls] = useState<
    Record<string, { poster: string; video: string }>
  >({});
  const [storageError, setStorageError] = useState("");
  const favorites = useMemo(
    () =>
      favoriteIds
        .map((id) => animals.find((a) => a.id === id))
        .filter((a): a is Animal => !!a),
    [animals, favoriteIds],
  );
  const favoriteKey = favorites.map((a) => a.id).join("|");
  useEffect(() => {
    let active = true;
    Promise.all(
      favoriteKey
        .split("|")
        .filter(Boolean)
        .map((id) => getLocalRecording(id)),
    )
      .then((items) => {
        if (active) {
          setClips(
            Object.fromEntries(
              items
                .filter((c): c is LocalRecording => !!c)
                .map((c) => [c.animalId, c]),
            ),
          );
          setStorageError("");
        }
      })
      .catch((e) => {
        if (active)
          setStorageError(
            e instanceof Error
              ? e.message
              : "Local recordings could not be loaded.",
          );
      });
    return () => {
      active = false;
    };
  }, [favoriteKey]);
  useEffect(() => {
    const next = Object.fromEntries(
      Object.values(clips).map((clip) => [
        clip.animalId,
        {
          poster: URL.createObjectURL(clip.poster),
          video: URL.createObjectURL(clip.file),
        },
      ]),
    );
    setUrls(next);
    return () =>
      Object.values(next).forEach((value) => {
        URL.revokeObjectURL(value.poster);
        URL.revokeObjectURL(value.video);
      });
  }, [clips]);
  const closePicker = useCallback(() => setPicker(false), []);
  const closeViewer = useCallback(() => setSelected(null), []);
  const selectedAnimal = animals.find((a) => a.id === selected);
  const choices = animals
    .filter((a) => `cow ${a.tag}`.includes(search.trim().toLowerCase()))
    .sort(
      (a, b) =>
        Number(favoriteIds.includes(b.id)) -
          Number(favoriteIds.includes(a.id)) ||
        a.tag.localeCompare(b.tag, undefined, { numeric: true }),
    );
  return (
    <section className="spotlight-page">
      <div className="spotlight-intro">
        <div>
          <span className="spotlight-kicker">
            <Star size={13} fill="currentColor" />
            YOUR WATCHLIST
          </span>
          <h2>A closer eye on the cows that matter.</h2>
          <p>
            Keep important cattle in focus. Open a bubble to see their latest
            available recording.
          </p>
        </div>
        <button
          className="primary-button"
          onClick={() => {
            setSearch("");
            setPicker(true);
          }}
        >
          <Plus size={16} />
          Choose cows
        </button>
      </div>
      <div className="spotlight-meta">
        <span>
          {favorites.length} {favorites.length === 1 ? "cow" : "cows"} in
          Spotlight
        </span>
        <span>
          <Clock3 size={12} />
          Recorded clips, not a live feed
        </span>
      </div>
      {storageError && (
        <p className="form-error" role="alert">
          {storageError} Favorites are still available.
        </p>
      )}
      {favorites.length ? (
        <div className="spotlight-grid">
          {favorites.map((animal, index) => {
            const active = alerts.filter(
              (a) =>
                a.animalId === animal.id &&
                ["open", "acknowledged"].includes(a.lifecycle),
            );
            const clip = clips[animal.id];
            return (
              <article
                className="spotlight-card card"
                aria-label={`Spotlight Cow ${animal.tag}`}
                key={animal.id}
              >
                <div className={`spotlight-orbit orbit-${animal.assessment}`}>
                  <button
                    className="spotlight-photo"
                    aria-label={`Open recording for Cow ${animal.tag}`}
                    onClick={() => setSelected(animal.id)}
                  >
                    <img
                      src={
                        urls[animal.id]?.poster ??
                        "/assets/cow-illustration.png"
                      }
                      alt={
                        clip
                          ? `Frame from the clip attached to Cow ${animal.tag}`
                          : "Generic illustrative cow preview, not animal evidence"
                      }
                      style={{
                        objectPosition: clip
                          ? "center"
                          : index % 2
                            ? "57% center"
                            : "45% center",
                      }}
                    />
                    <span className="bubble-play">
                      {clip ? (
                        <Play size={23} fill="currentColor" />
                      ) : (
                        <Film size={23} />
                      )}
                    </span>
                    <span className="thumbnail-source">
                      {clip ? "Recorded frame" : "Illustrative preview"}
                    </span>
                    {clip && (
                      <span className="clip-duration">
                        {durationLabel(clip.duration)}
                      </span>
                    )}
                  </button>
                  <button
                    className="spotlight-unpin"
                    aria-label={`Remove Cow ${animal.tag} from Spotlight`}
                    title="Remove from Spotlight"
                    onClick={() => toggleFavorite(animal.id)}
                  >
                    <Star size={16} fill="currentColor" />
                  </button>
                  {!!active.length && (
                    <button
                      className={`spotlight-alert-dot alert-dot-${animal.assessment}`}
                      aria-label={`${active.length} open finding for Cow ${animal.tag}`}
                      onClick={() => openAnimal(animal)}
                    >
                      <Bell size={13} />
                      <span>{active.length}</span>
                    </button>
                  )}
                </div>
                <h3>Cow {animal.tag}</h3>
                <p className="spotlight-herd">
                  {herds.find((h) => h.id === animal.herdId)?.name}{" "}
                  <span>·</span>{" "}
                  {herds.find((h) => h.id === animal.herdId)?.pasture}
                </p>
                <StatusBadge status={animal.assessment} />
                <div className="spotlight-recorded">
                  <Clock3 size={12} />
                  <span>
                    {clip
                      ? clipTime(clip.capturedAt)
                      : animal.observedAt
                        ? `Observed ${time(animal.observedAt)} · no clip connected`
                        : "No recorded observation yet"}
                  </span>
                </div>
                <button
                  className="spotlight-watch"
                  onClick={() => setSelected(animal.id)}
                >
                  {clip ? (
                    <Play size={14} fill="currentColor" />
                  ) : (
                    <Video size={15} />
                  )}
                  View recording
                  <ArrowUpRight size={14} />
                </button>
                <button
                  className="text-button spotlight-details"
                  onClick={() => openAnimal(animal)}
                >
                  Cow details{!active.length && <span> · no open alerts</span>}
                </button>
              </article>
            );
          })}
          <button
            className="spotlight-add-bubble"
            onClick={() => {
              setSearch("");
              setPicker(true);
            }}
          >
            <span>
              <Plus size={27} />
            </span>
            <strong>Make room for another</strong>
            <small>Add a cow to your Spotlight</small>
          </button>
        </div>
      ) : (
        <div className="spotlight-empty card">
          <span className="empty-star">
            <Star size={35} />
          </span>
          <h3>Your Spotlight starts here</h3>
          <p>
            Choose a few important cows to keep their observations and
            recordings close.
          </p>
          <button className="primary-button" onClick={() => setPicker(true)}>
            <Plus size={15} />
            Choose your first cow
          </button>
        </div>
      )}
      <p className="spotlight-local-note">
        <Star size={12} />
        Favorites and attached clips stay in this browser. Illustrative previews
        are not source footage.
      </p>
      {picker && (
        <Dialog
          title="Choose your Spotlight"
          subtitle="FAVORITE CATTLE"
          onClose={closePicker}
          wide
        >
          <p className="dialog-copy">
            Star the cows you want to keep close. You can change your watchlist
            at any time.
          </p>
          <div className="input-with-icon">
            <Search size={17} />
            <input
              aria-label="Search cows to favorite"
              autoFocus
              placeholder="Search cow number…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <div className="favorite-picker-list">
            {choices.map((animal) => (
              <button
                key={animal.id}
                aria-pressed={favoriteIds.includes(animal.id)}
                aria-label={`${favoriteIds.includes(animal.id) ? "Unfavorite" : "Favorite"} Cow ${animal.tag}`}
                onClick={() => toggleFavorite(animal.id)}
              >
                <span
                  className={`picker-star ${favoriteIds.includes(animal.id) ? "is-starred" : ""}`}
                >
                  <Star
                    size={18}
                    fill={
                      favoriteIds.includes(animal.id) ? "currentColor" : "none"
                    }
                  />
                </span>
                <span>
                  <strong>Cow {animal.tag}</strong>
                  <small>
                    {herds.find((h) => h.id === animal.herdId)?.name}
                  </small>
                </span>
                <StatusBadge status={animal.assessment} />
                {favoriteIds.includes(animal.id) && <Check size={15} />}
              </button>
            ))}
            {!choices.length && (
              <div className="table-empty">
                <p>No cows match that number.</p>
              </div>
            )}
          </div>
          <button className="primary-button full-width" onClick={closePicker}>
            Done · {favoriteIds.length} selected
          </button>
        </Dialog>
      )}
      {selectedAnimal && (
        <RecordingViewer
          animal={selectedAnimal}
          clip={clips[selectedAnimal.id]}
          urls={urls[selectedAnimal.id]}
          onClose={closeViewer}
          onSaved={(clip) =>
            setClips((current) => ({ ...current, [clip.animalId]: clip }))
          }
          onRemoved={(id) =>
            setClips((current) => {
              const next = { ...current };
              delete next[id];
              return next;
            })
          }
        />
      )}
    </section>
  );
}

function RecordingViewer({
  animal,
  clip,
  urls,
  onClose,
  onSaved,
  onRemoved,
}: {
  animal: Animal;
  clip?: LocalRecording;
  urls?: { video: string; poster: string };
  onClose(): void;
  onSaved(clip: LocalRecording): void;
  onRemoved(id: string): void;
}) {
  const [remote, setRemote] = useState<LatestRecording | null>(null),
    [loading, setLoading] = useState(true),
    [loadError, setLoadError] = useState("");
  const [attaching, setAttaching] = useState(!clip),
    [file, setFile] = useState<File | null>(null),
    [recordedAt, setRecordedAt] = useState("");
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const load = useCallback(async () => {
    if (clip || animal.id.startsWith("local-")) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setLoadError("");
    try {
      setRemote(await monitoringApi.latestRecording(animal.id));
    } catch (e) {
      setLoadError(
        e instanceof Error
          ? e.message
          : "The recording could not be retrieved.",
      );
    } finally {
      setLoading(false);
    }
  }, [animal.id, clip]);
  useEffect(() => {
    void load();
  }, [load]);
  const src = urls?.video ?? remote?.playbackUrl;
  async function attach(event: React.FormEvent) {
    event.preventDefault();
    if (!file) {
      setError("Choose a recorded video first.");
      return;
    }
    if (recordedAt && !Number.isFinite(Date.parse(recordedAt))) {
      setError('Choose a valid capture date and time, or leave it blank.');
      return;
    }
    const capturedAt = recordedAt ? new Date(recordedAt).toISOString() : null;
    if (
      clip?.capturedAt &&
      capturedAt &&
      Date.parse(capturedAt) < Date.parse(clip.capturedAt)
    ) {
      setError(
        "An attached clip has a later capture time. Keep the newer recording or remove it first.",
      );
      return;
    }
    setBusy(true);
    setError("");
    try {
      const info = await inspectVideo(file);
      const next: LocalRecording = {
        animalId: animal.id,
        file,
        poster: info.poster,
        fileName: file.name,
        duration: info.duration,
        capturedAt,
        attachedAt: new Date().toISOString(),
      };
      await saveLocalRecording(next);
      onSaved(next);
      setAttaching(false);
      setFile(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "The clip could not be saved.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog
      title={`Cow ${animal.tag} · recording`}
      subtitle="LAST AVAILABLE INSTANCE"
      onClose={onClose}
      wide
    >
      {loading ? (
        <div className="recording-unavailable">
          <Loader2 className="spin" size={27} />
          <p>Looking for the latest recording…</p>
        </div>
      ) : src ? (
        <>
          <video
            className="cow-video-player"
            controls
            playsInline
            preload="metadata"
            poster={urls?.poster ?? remote?.thumbnailUrl ?? undefined}
            src={src}
            onError={() =>
              setError(
                "This clip cannot be played by this browser. Try an H.264 MP4 or WebM recording.",
              )
            }
            aria-label={`Recorded video for Cow ${animal.tag}`}
          />
          <div className="recording-facts">
            <span>
              <span className="healthy-dot" />
              Recorded clip
            </span>
            <span>
              {clip ? durationLabel(clip.duration) : "Latest available"}
            </span>
          </div>
          <div className="detail-facts">
            <div>
              <span>Capture time · Pacific</span>
              <strong>
                {clipTime(clip?.capturedAt ?? remote?.capturedAt ?? null)}
              </strong>
            </div>
            <div>
              <span>Source</span>
              <strong>
                {clip
                  ? "Manually attached in this browser"
                  : "Authorized backend recording"}
              </strong>
            </div>
            {clip && (
              <div>
                <span>File</span>
                <strong>{clip.fileName}</strong>
              </div>
            )}
          </div>
        </>
      ) : (
        <div className="recording-unavailable">
          <span>
            <Video size={33} />
          </span>
          <h3>No recorded clip connected</h3>
          <p>
            {loadError ||
              remote?.message ||
              "Attach a recorded clip for this cow. No live footage is connected."}
          </p>
          {loadError && (
            <button className="text-button" onClick={() => void load()}>
              <RefreshCw size={14} />
              Retry recording lookup
            </button>
          )}
        </div>
      )}
      {clip && !attaching && (
        <div className="recording-actions">
          <button
            className="secondary-button"
            onClick={() => {
              setAttaching(true);
              setError("");
              setFile(null);
              setRecordedAt('');
            }}
          >
            <Upload size={14} />
            Replace local clip
          </button>
          <button
            className="text-button danger-text"
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              try {
                await deleteLocalRecording(animal.id);
                onRemoved(animal.id);
                setAttaching(true);
                setError('');
                setFile(null);
                setRecordedAt('');
              } catch (e) {
                setError(
                  e instanceof Error ? e.message : "Could not remove clip.",
                );
              } finally {
                setBusy(false);
              }
            }}
          >
            <Trash2 size={14} />
            Remove attached copy
          </button>
        </div>
      )}
      {attaching && (
        <form onSubmit={attach} className="attach-recording-form">
          <div>
            <h3>
              <Upload size={16} />
              Attach a recorded clip
            </h3>
            <p>
              MP4, WebM or MOV · up to 100 MB. Stored locally; never uploaded.
            </p>
          </div>
          <label htmlFor="cow-recording-file">Video for Cow {animal.tag}</label>
          <input
            id="cow-recording-file"
            type="file"
            accept="video/mp4,video/webm,video/quicktime"
            disabled={busy}
            onChange={(e) => {
              setFile(e.target.files?.[0] ?? null);
              setError("");
            }}
          />
          <label htmlFor="cow-recording-time">
            Capture time (your local time, optional)
          </label>
          <input
            id="cow-recording-time"
            type="datetime-local"
            value={recordedAt}
            onChange={(e) => setRecordedAt(e.target.value)}
            disabled={busy}
          />
          <p className="demo-write-note">
            Assign only a clip that belongs to this cow. Unknown capture time
            stays unknown. A preview frame is extracted from your video.
          </p>
          <div className="form-actions">
            {clip && (
              <button
                className="secondary-button"
                type="button"
                disabled={busy}
                onClick={() => {setAttaching(false);setError('');setFile(null);setRecordedAt('');}}
              >
                Cancel
              </button>
            )}
            <button
              className="primary-button"
              type="submit"
              disabled={busy || !file}
            >
              {busy ? (
                <Loader2 size={15} className="spin" />
              ) : (
                <Check size={15} />
              )}{" "}
              {busy ? "Preparing preview…" : "Save clip & view"}
            </button>
          </div>
        </form>
      )}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
    </Dialog>
  );
}
