// Only local user-selected media. No upload, database credentials or signed URLs.
export interface LocalRecording {
  animalId: string;
  file: Blob;
  poster: Blob;
  fileName: string;
  capturedAt: string | null;
  attachedAt: string;
  duration: number;
}
const DATABASE = "holycow-recordings-v1";
async function open(): Promise<IDBDatabase> {
  if (!("indexedDB" in window))
    throw new Error("This browser does not support local clip storage.");
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DATABASE, 1);
    request.onupgradeneeded = () =>
      request.result.createObjectStore("recordings", { keyPath: "animalId" });
    request.onsuccess = () => resolve(request.result);
    request.onerror = () =>
      reject(new Error("Local clip storage is unavailable."));
    request.onblocked = () =>
      reject(new Error("Close other HolyCow tabs and try again."));
  });
}
export async function getLocalRecording(
  animalId: string,
): Promise<LocalRecording | undefined> {
  const db = await open();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction("recordings", "readonly");
    const request = transaction.objectStore("recordings").get(animalId);
    request.onsuccess = () =>
      resolve(request.result as LocalRecording | undefined);
    request.onerror = () =>
      reject(new Error("The saved clip could not be read."));
    transaction.oncomplete = () => db.close();
    transaction.onabort = () => db.close();
  });
}
export async function saveLocalRecording(
  recording: LocalRecording,
): Promise<void> {
  const db = await open();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction("recordings", "readwrite");
    transaction.objectStore("recordings").put(recording);
    transaction.oncomplete = () => {
      db.close();
      resolve();
    };
    transaction.onabort = transaction.onerror = () => {
      db.close();
      reject(
        new Error(
          "This browser could not save the clip. Check available storage and try a smaller file.",
        ),
      );
    };
  });
}
export async function deleteLocalRecording(animalId: string): Promise<void> {
  const db = await open();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction("recordings", "readwrite");
    transaction.objectStore("recordings").delete(animalId);
    transaction.oncomplete = () => {
      db.close();
      resolve();
    };
    transaction.onabort = transaction.onerror = () => {
      db.close();
      reject(new Error("The local clip could not be removed."));
    };
  });
}
export async function inspectVideo(
  file: File,
): Promise<{ poster: Blob; duration: number }> {
  if (!file.size || file.size > 100 * 1024 * 1024)
    throw new Error("Choose a video smaller than 100 MB.");
  if (!["video/mp4", "video/webm", "video/quicktime"].includes(file.type))
    throw new Error("Choose an MP4, WebM or MOV video.");
  const url = URL.createObjectURL(file);
  const video = document.createElement("video");
  video.preload = "auto";
  video.muted = true;
  video.playsInline = true;
  try {
    return await new Promise((resolve, reject) => {
      const timer = setTimeout(
        () =>
          reject(
            new Error(
              "This video could not be decoded. Try an H.264 MP4 or WebM clip.",
            ),
          ),
        15000,
      );
      video.onerror = () => {
        clearTimeout(timer);
        reject(new Error("This browser cannot play that video format."));
      };
      video.onloadedmetadata = () => {
        if (!Number.isFinite(video.duration) || video.duration <= 0) {
          clearTimeout(timer);
          reject(
            new Error("Choose a finite recorded video, not a live stream."),
          );
          return;
        }
        video.currentTime = Math.min(0.12, video.duration / 2);
      };
      video.onseeked = () => {
        const canvas = document.createElement("canvas");
        canvas.width = Math.min(900, video.videoWidth);
        canvas.height = Math.round(
          (canvas.width * video.videoHeight) / video.videoWidth,
        );
        const ctx = canvas.getContext("2d");
        if (!ctx || !canvas.height) {
          clearTimeout(timer);
          reject(new Error("A preview image could not be created."));
          return;
        }
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        canvas.toBlob(
          (poster) => {
            clearTimeout(timer);
            if (poster) resolve({ poster, duration: video.duration });
            else reject(new Error("A preview image could not be created."));
          },
          "image/jpeg",
          0.86,
        );
      };
      video.src = url;
      video.load();
    });
  } finally {
    video.removeAttribute("src");
    video.load();
    URL.revokeObjectURL(url);
  }
}
export function clipTime(value: string | null) {
  return value
    ? new Date(value).toLocaleString("en-US", {
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
        timeZone: "America/Los_Angeles",
      })
    : "Capture time not supplied";
}
export function durationLabel(seconds: number) {
  return `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`;
}
