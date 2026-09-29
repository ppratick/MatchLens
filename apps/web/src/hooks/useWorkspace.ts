import { useCallback, useEffect, useRef, useState } from "react";
import { useScreenCapture } from "./useScreenCapture";
import { api, establishSession, uploadVideo } from "../api";
import type {
  Artifact,
  Detail,
  Event as MatchEvent,
  Frame,
  Match,
  System,
} from "../types";
type Modal =
  | "television"
  | "annotate"
  | "new"
  | "event"
  | "analyze"
  | "clip"
  | "calibration"
  | "track"
  | "capture"
  | "pair"
  | "clock"
  | "exclude"
  | null;
type Section = "library" | "review" | "compare" | "settings";
export function useWorkspace() {
  const [section, setSection] = useState<Section>("library"),
    [matches, setMatches] = useState<Match[]>([]),
    [selected, setSelected] = useState<string | null>(null),
    [detail, setDetail] = useState<Detail | null>(null),
    [system, setSystem] = useState<System | null>(null);
  const [tab, setTab] = useState("overview"),
    [modal, setModal] = useState<Modal>(null),
    [toast, setToast] = useState(""),
    [busy, setBusy] = useState(false),
    [booted, setBooted] = useState(false),
    [query, setQuery] = useState("");
  const [sourceId, setSourceId] = useState(""),
    [segmentId, setSegmentId] = useState(""),
    [time, setTime] = useState(0),
    [frame, setFrame] = useState<Frame | null>(null),
    [playing, setPlaying] = useState(false),
    [overlay, setOverlay] = useState(true),
    [viewHeat, setViewHeat] = useState(false),
    [trackId, setTrackId] = useState(""),
    [pointEdit, setPointEdit] = useState(false);
  const [liveMode, setLiveMode] = useState<"feed" | "analysis" | "review">(
      "feed",
    ),
    [videoRatio, setVideoRatio] = useState(16 / 9);
  const [eventEdit, setEventEdit] = useState<MatchEvent | null>(null),
    [progress, setProgress] = useState<number | null>(null),
    [pairing, setPairing] = useState<{
      fragment: string;
      instructions: string;
    } | null>(null),
    [calibrationImage, setCalibrationImage] = useState(""),
    [calibrationPoints, setCalibrationPoints] = useState<number[][]>([]);
  const video = useRef<HTMLVideoElement>(null),
    importInput = useRef<HTMLInputElement>(null),
    pendingSeek = useRef<number | null>(null),
    resumePlayback = useRef(false),
    lastFrameFetch = useRef(0);
  const notify = useCallback((message: string) => {
    setToast(message);
  }, []);
  const close = useCallback(() => setModal(null), []);
  const refresh = useCallback(async () => {
    setMatches(await api<Match[]>("/matches"));
    if (selected) {
      const d = await api<Detail>("/matches/" + selected);
      setDetail(d);
    }
  }, [selected]);
  const screenCapture = useScreenCapture(selected, notify, refresh);
  useEffect(() => {
    establishSession()
      .then(async () => {
        const [m, s] = await Promise.all([
          api<Match[]>("/matches"),
          api<System>("/system"),
        ]);
        setMatches(m);
        setSystem(s);
        setBooted(true);
      })
      .catch((e) => notify(e.message));
  }, [notify]);
  useEffect(() => {
    if (!booted) return;
    refresh().catch((e) => notify(e.message));
    const id = window.setInterval(() => {
      refresh().catch(() => {});
      api<System>("/system")
        .then(setSystem)
        .catch(() => {});
    }, 2500);
    return () => clearInterval(id);
  }, [booted, refresh, notify]);
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(""), 8000);
    return () => clearTimeout(t);
  }, [toast]);
  useEffect(() => {
    if (
      detail &&
      detail.match.id === selected &&
      !detail.sources.some((s) => s.id === sourceId)
    ) {
      setSourceId(detail.sources[0]?.id || "");
      setSegmentId("");
    }
  }, [detail, selected, sourceId]);
  const source = detail?.sources.find((s) => s.id === sourceId);
  const segment =
    source?.segments?.find((s) => s.id === segmentId) || source?.segments?.[0];
  const mediaOffset = segment?.start ?? source?.offset ?? 0;
  const mediaUrl =
    selected && source
      ? `/media/${selected}/${source.id}${segment ? "?segment=" + segment.id : ""}`
      : "";
  const activeJobs =
    detail?.jobs.filter((j) => ["queued", "running"].includes(j.status)) || [];
  const recording = activeJobs.some((j) => j.kind === "capture");
  const runningAnalysis = activeJobs.find((j) => j.kind === "analysis");
  const latestAnalysis = detail?.jobs.find(
    (j) => j.kind === "analysis" && j.config.source_id === sourceId,
  );
  useEffect(() => {
    if (!recording || liveMode === "review" || !source?.segments?.length)
      return;
    const t =
      liveMode === "analysis" ? latestAnalysis?.checkpoint?.time : undefined;
    const next =
      t === undefined
        ? source.segments.at(-1)
        : source.segments.find((s) => s.start <= t && t < s.end);
    if (!next) return;
    if (next.id !== segment?.id) {
      pendingSeek.current = t === undefined ? 0 : Math.max(0, t - next.start);
      setSegmentId(next.id);
    } else if (t !== undefined && video.current) {
      video.current.pause();
      video.current.currentTime = Math.max(0, t - next.start);
    }
  }, [
    recording,
    liveMode,
    source?.segments?.length,
    latestAnalysis?.checkpoint?.time,
    sourceId,
  ]);
  useEffect(() => {
    if (!selected || !sourceId || !video.current?.paused) return;
    api<Frame[]>(`/matches/${selected}/frames?at=${time}&source_id=${sourceId}`)
      .then((f) => setFrame(f[0] || null))
      .catch(() => {});
  }, [selected, sourceId, detail?.match.revision, latestAnalysis?.status]);
  const track = detail?.tracks.find((t) => t.id === trackId);
  const currentFrame =
    !(recording && liveMode === "feed") &&
    latestAnalysis?.metrics?.visualizations !== false &&
    frame &&
    frame.source_id === sourceId &&
    Math.abs(time - frame.time) <= Math.max(0.6, frame.sample_interval * 1.5)
      ? frame
      : null;
  const openMatch = (id: string) => {
    setSelected(id);
    setDetail(null);
    setSourceId("");
    setSegmentId("");
    setTime(0);
    setFrame(null);
    setSection("review");
    setTab("overview");
  };
  const act = async (
    fn: () => Promise<unknown>,
    message?: string,
    reload = true,
  ) => {
    setBusy(true);
    try {
      await fn();
      if (reload) await refresh();
      if (message) notify(message);
    } catch (e) {
      notify((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const correction = async (operation: string, payload: unknown) => {
    if (!detail) return;
    await api(`/matches/${detail.match.id}/corrections`, "POST", {
      revision: detail.match.revision,
      operation,
      payload,
    });
    await refresh();
  };
  const seek = (t: number) => {
    const target = source?.segments?.find((s) => s.start <= t && t < s.end);
    if (target && target.id !== segment?.id) {
      resumePlayback.current = !video.current?.paused;
      pendingSeek.current = t - target.start;
      setSegmentId(target.id);
    } else if (video.current) {
      video.current.currentTime = Math.max(0, t - mediaOffset);
    }
    setTime(t);
  };
  const updateTime = () => {
    if (!video.current) return;
    const t = video.current.currentTime + mediaOffset;
    setTime(t);
    if (Date.now() - lastFrameFetch.current > 180 && selected && sourceId) {
      lastFrameFetch.current = Date.now();
      api<Frame[]>(`/matches/${selected}/frames?at=${t}&source_id=${sourceId}`)
        .then((f) => setFrame(f[0] || null))
        .catch(() => {});
    }
  };
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (
        (e.target as HTMLElement).closest("input,textarea,select") ||
        modal ||
        section !== "review"
      )
        return;
      if (e.key === " ") {
        e.preventDefault();
        if (video.current?.paused) video.current.play();
        else video.current?.pause();
      }
      if (e.key === "ArrowRight") {
        e.preventDefault();
        seek(time + 5);
      }
      if (e.key === "ArrowLeft") {
        e.preventDefault();
        seek(Math.max(0, time - 5));
      }
      if (e.key.toLowerCase() === "e") {
        setEventEdit(null);
        setModal("event");
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [modal, section, time, sourceId, segmentId]);
  const importFile = async (file: File, id = selected) => {
    if (!id) return;
    setProgress(0);
    try {
      await uploadVideo(id, file, setProgress);
      notify("Original recording saved. Ready to analyze.");
      await refresh();
    } catch (e) {
      notify((e as Error).message);
    } finally {
      setProgress(null);
    }
  };
  const calibrate = () => {
    if (!video.current || !source) return;
    const canvas = document.createElement("canvas");
    canvas.width = video.current.videoWidth;
    canvas.height = video.current.videoHeight;
    if (!canvas.width) {
      notify("Load a video frame first");
      return;
    }
    canvas.getContext("2d")?.drawImage(video.current, 0, 0);
    setCalibrationImage(canvas.toDataURL());
    setCalibrationPoints([]);
    video.current.pause();
    setModal("calibration");
  };
  const eventAction = (e: MatchEvent, status: string) =>
    act(() =>
      correction("event", {
        ...Object.fromEntries(
          Object.entries(e).filter(
            ([k]) => !["excluded", "track_id"].includes(k),
          ),
        ),
        status,
      }),
    );
  const exportUrl = (a: Artifact, name: string) =>
    `/api/matches/${selected}/exports/${a.id}/${name}`;

  return {
    screenCapture,
    section,
    setSection,
    matches,
    setMatches,
    selected,
    setSelected,
    detail,
    setDetail,
    system,
    setSystem,
    tab,
    setTab,
    modal,
    setModal,
    toast,
    setToast,
    busy,
    setBusy,
    booted,
    setBooted,
    query,
    setQuery,
    sourceId,
    setSourceId,
    segmentId,
    setSegmentId,
    time,
    setTime,
    frame,
    setFrame,
    playing,
    setPlaying,
    overlay,
    setOverlay,
    viewHeat,
    setViewHeat,
    trackId,
    setTrackId,
    pointEdit,
    setPointEdit,
    liveMode,
    setLiveMode,
    videoRatio,
    setVideoRatio,
    eventEdit,
    setEventEdit,
    progress,
    setProgress,
    pairing,
    setPairing,
    calibrationImage,
    setCalibrationImage,
    calibrationPoints,
    setCalibrationPoints,
    video,
    importInput,
    pendingSeek,
    resumePlayback,
    lastFrameFetch,
    notify,
    close,
    refresh,
    source,
    segment,
    mediaOffset,
    mediaUrl,
    activeJobs,
    recording,
    runningAnalysis,
    latestAnalysis,
    track,
    currentFrame,
    openMatch,
    act,
    correction,
    seek,
    updateTime,
    importFile,
    calibrate,
    eventAction,
    exportUrl,
  };
}
export type Workspace = ReturnType<typeof useWorkspace>;
