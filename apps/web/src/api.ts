let token = "";
export async function establishSession() {
  const response = await fetch("/api/session");
  if (!response.ok)
    throw Error("Cannot connect to the local MatchLens service.");
  const session = await response.json();
  token = session.token;
  return session;
}
export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const response = await fetch("/api" + path, {
    method,
    headers: { "Content-Type": "application/json", "X-MatchLens-Token": token },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: response.statusText }));
    throw Error(
      typeof error.detail === "string"
        ? error.detail
        : JSON.stringify(error.detail),
    );
  }
  return response.json();
}
export function uploadVideo(
  id: string,
  file: File,
  onProgress: (n: number) => void,
) {
  return new Promise<void>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open(
      "POST",
      `/api/matches/${id}/video?filename=${encodeURIComponent(file.name)}`,
    );
    xhr.setRequestHeader("X-MatchLens-Token", token);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(e.loaded / e.total);
    };
    xhr.onerror = () =>
      reject(Error("Upload interrupted. Your original file is unchanged."));
    xhr.onload = () => {
      if (xhr.status < 300) resolve();
      else {
        try {
          reject(Error(JSON.parse(xhr.responseText).detail));
        } catch {
          reject(Error("Import failed"));
        }
      }
    };
    xhr.send(file);
  });
}
export const clock = (seconds: number) =>
  `${Math.floor(Math.max(0, seconds) / 60)
    .toString()
    .padStart(2, "0")}:${Math.floor(Math.max(0, seconds) % 60)
    .toString()
    .padStart(2, "0")}`;
export const bytes = (n: number) =>
  n >= 1e9 ? `${(n / 1e9).toFixed(1)} GB` : `${(n / 1e6).toFixed(0)} MB`;

export class CaptureError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

export async function sendCapture(
  path: string,
  secret: string,
  body?: Blob | object,
  epoch?: string,
) {
  const response = await fetch("/screen-ingest" + path, {
    signal: AbortSignal.timeout(10000),
    method: body === undefined ? "GET" : "POST",
    headers: {
      "X-MatchLens-Token": token,
      "x-pair-secret": secret,
      ...(epoch ? { "x-sender-epoch": epoch } : {}),
      ...(body instanceof Blob ? {} : { "Content-Type": "application/json" }),
    },
    body:
      body === undefined
        ? undefined
        : body instanceof Blob
          ? body
          : JSON.stringify(body),
  });
  const result = await response.json();
  if (!response.ok)
    throw new CaptureError(
      result.detail || response.statusText,
      response.status,
    );
  return result;
}

export async function importModel(file: File, variant: "tiny" | "small") {
  const response = await fetch(`/api/models/import?variant=${variant}`, {
    method: "POST",
    body: file,
    headers: { "X-MatchLens-Token": token },
    signal: AbortSignal.timeout(120000),
  });
  const result = await response.json();
  if (!response.ok) throw Error(result.detail || "Model import failed");
  return result;
}
