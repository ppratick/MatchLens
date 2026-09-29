import { useEffect, useRef, useState } from "react";
import { api, CaptureError, sendCapture } from "../api";

type Pair = { pair_id: string; secret: string; job_id: string };
export function useScreenCapture(
  matchId: string | null,
  notify: (s: string) => void,
  refresh: () => Promise<void>,
) {
  const [state, setState] = useState("idle"),
    [message, setMessage] = useState(""),
    [preview, setPreview] = useState<MediaStream | null>(null),
    [audio, setAudio] = useState(false);
  const owner = useRef<{
    recorder: MediaRecorder;
    stream: MediaStream;
    pair: Pair;
    queue: Blob[];
    sequence: number;
    sending: boolean;
    finishing: boolean;
    epoch: string;
    started: number;
  } | null>(null);
  const health = async (state: string) => {
    const c = owner.current;
    if (c)
      await sendCapture(`/health/${c.pair.pair_id}`, c.pair.secret, {
        state,
        elapsed_ms: performance.now() - c.started,
      }).catch(() => {});
  };
  const finish = () => {
    const c = owner.current;
    if (!c || c.recorder.state === "inactive") return;
    setState("draining");
    c.recorder.stop();
  };
  useEffect(() => {
    const leaving = (e: BeforeUnloadEvent) => {
      if (owner.current) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    const suspended = () => {
      if (owner.current?.recorder.state === "recording") {
        void health("suspended");
        finish();
        setMessage(
          "Capture page unloading: recording stopped and interruption marked. Finalizing received video.",
        );
      }
    };
    window.addEventListener("beforeunload", leaving);
    window.addEventListener("pagehide", suspended);
    return () => {
      window.removeEventListener("beforeunload", leaving);
      window.removeEventListener("pagehide", suspended);
    };
  }, []);
  const drain = async () => {
    const c = owner.current;
    if (!c || c.sending) return;
    c.sending = true;
    try {
      while (c.queue.length || c.finishing) {
        try {
          if (!c.queue.length && c.finishing) {
            await sendCapture(`/finish/${c.pair.pair_id}`, c.pair.secret, {});
            c.stream.getTracks().forEach((t) => t.stop());
            setPreview(null);
            setState("saved");
            setMessage(
              "Received bytes finalized. Verify playable committed segments on the Mac; run an offline pass next.",
            );
            owner.current = null;
            await refresh();
            break;
          }
          const result = await sendCapture(
            `/ingest/${c.pair.pair_id}/${c.sequence}`,
            c.pair.secret,
            c.queue[0],
            c.epoch,
          );
          c.queue.shift();
          c.sequence = result.next_sequence;
          setMessage(
            `${c.sequence} chunks durably received. Waiting for committed video segments.`,
          );
          if (c.recorder.state === "paused" && c.queue.length < 3) {
            await health("resumed");
            c.recorder.resume();
            setState("recording");
          }
        } catch (e) {
          if (
            e instanceof CaptureError &&
            [400, 403, 404, 409, 413].includes(e.status)
          ) {
            finish();
            setState("blocked");
            setMessage(
              `Receiver rejected this recording: ${e.message}. Buffered bytes remain in this tab; do not start a new timeline here.`,
            );
            break;
          }
          setMessage(
            `Connection interrupted; buffered chunks retained. ${(e as Error).message}`,
          );
          setState("retrying");
          await new Promise((r) => setTimeout(r, 1500));
        }
      }
    } finally {
      c.sending = false;
    }
  };
  const start = async () => {
    if (!matchId || owner.current) return;
    let stream: MediaStream | undefined;
    try {
      if (!navigator.mediaDevices?.getDisplayMedia)
        throw Error(
          "This browser does not provide screen selection. Use desktop Chrome or import a macOS recording.",
        );
      // Must be called directly from the user's click, before API awaits.
      stream = await navigator.mediaDevices.getDisplayMedia({
        video: { frameRate: { ideal: 30, max: 30 } },
        audio: true,
      });
      setAudio(stream.getAudioTracks().length > 0);
      setPreview(stream);
      const pair = await api<Pair>(`/matches/${matchId}/screen-pair`, "POST");
      const mime = [
        "video/webm;codecs=vp8,opus",
        "video/webm;codecs=vp8",
        "video/mp4",
      ].find((m) => MediaRecorder.isTypeSupported(m));
      const recorder = new MediaRecorder(stream, {
        ...(mime ? { mimeType: mime } : {}),
        videoBitsPerSecond: 6000000,
      });
      owner.current = {
        recorder,
        stream,
        pair,
        queue: [],
        sequence: 0,
        sending: false,
        finishing: false,
        epoch: crypto.randomUUID(),
        started: performance.now(),
      };
      recorder.ondataavailable = (e) => {
        const c = owner.current!;
        if (e.data.size) {
          for (let a = 0; a < e.data.size; a += 8 * 1024 * 1024)
            c.queue.push(e.data.slice(a, a + 8 * 1024 * 1024));
          if (
            c.queue.reduce((s, b) => s + b.size, 0) > 24 * 1024 * 1024 &&
            recorder.state === "recording"
          ) {
            recorder.pause();
            health("paused");
            setState("paused");
            setMessage(
              "Upload buffer full: capture paused, recording gap marked. Recording bytes already received are preserved.",
            );
          }
          void drain();
        }
      };
      recorder.onstop = () => {
        owner.current!.finishing = true;
        void drain();
      };
      stream.getVideoTracks()[0].onended = () => {
        void health("track_ended");
        finish();
      };
      recorder.start(2000);
      setState("recording");
      setMessage(
        `Recording ${stream.getVideoTracks()[0].label || "selected source"}. Keep this browser tab open.`,
      );
      await refresh();
    } catch (e) {
      stream?.getTracks().forEach((t) => t.stop());
      setPreview(null);
      setState("error");
      const name = (e as Error).name;
      const reason =
        name === "NotAllowedError"
          ? "Screen sharing was denied or cancelled. In macOS System Settings → Privacy & Security → Screen & System Audio Recording, allow your browser manually if needed; relaunch it and choose the source again."
          : (e as Error).message;
      setMessage(reason);
      notify(reason);
    }
  };
  const downloadBuffer = () => {
    const c = owner.current;
    if (!c?.queue.length) return;
    const url = URL.createObjectURL(new Blob(c.queue));
    const a = document.createElement("a");
    a.href = url;
    a.download = `unsent-${c.pair.pair_id}-from-chunk-${c.sequence}.bin`;
    a.click();
    URL.revokeObjectURL(url);
    notify(
      "Unsent bytes downloaded. This is a raw recording tail, not a complete playable video; retain it with the Mac's received original.",
    );
  };
  return { state, message, preview, audio, start, finish, downloadBuffer };
}
