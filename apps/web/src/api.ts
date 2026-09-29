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
