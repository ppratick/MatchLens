import React, { useCallback, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  ArrowDownToLine,
  ArrowLeft,
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock3,
  Download,
  Eye,
  FileText,
  Film,
  Flag,
  FolderOpen,
  Goal,
  Grid2X2,
  Layers,
  Loader2,
  Map,
  MoreHorizontal,
  Pause,
  Play,
  Plus,
  Radio,
  ScanLine,
  Search,
  Settings2,
  ShieldCheck,
  SlidersHorizontal,
  Target,
  Trash2,
  Undo2,
  Redo2,
  Upload,
  Users,
  Video,
  X,
  AlertTriangle,
  Link2,
  Monitor,
  Smartphone,
  Camera,
  Scissors,
} from "lucide-react";
import { api, bytes, clock, establishSession, uploadVideo } from "./api";
import type {
  Artifact,
  Detail,
  Event as MatchEvent,
  Frame,
  Job,
  Match,
  Source,
  System,
  Team,
  Track,
} from "./types";
import "./style.css";

type Modal =
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
const teamColor: Record<Team, string> = {
  home: "#ed815a",
  away: "#7aabfa",
  unknown: "#bec9bf",
};
const labels: Record<string, string> = {
  goal: "Goal",
  shot: "Shot",
  pass: "Pass",
  turnover: "Turnover",
  save: "Save",
  possession: "Possession",
  note: "Note",
  period: "Period",
};

function Pitch({
  points = [],
  paths = [],
  heat = false,
  selected,
  onSelect,
}: {
  points?: { id: string; x: number; y: number; team: Team }[];
  paths?: { id: string; points: number[][]; team: Team }[];
  heat?: boolean;
  selected?: string;
  onSelect?: (id: string) => void;
}) {
  return (
    <svg
      className="pitch"
      viewBox="0 0 680 450"
      role="img"
      aria-label={heat ? "Player position heatmap" : "Top-down soccer field"}
    >
      <defs>
        <pattern
          id="stripes"
          width="120"
          height="450"
          patternUnits="userSpaceOnUse"
        >
          <rect width="60" height="450" fill="#ffffff" opacity=".018" />
        </pattern>
        <radialGradient id="heat">
          <stop offset="0" stopColor="#d9f58c" stopOpacity=".6" />
          <stop offset="1" stopColor="#d9f58c" stopOpacity="0" />
        </radialGradient>
      </defs>
      <rect width="680" height="450" rx="12" fill="#173c31" />
      <rect x="25" y="25" width="630" height="400" fill="url(#stripes)" />
      <g fill="none" stroke="#8bab95" strokeWidth="1.3" opacity=".6">
        <rect x="25" y="25" width="630" height="400" />
        <path d="M340 25V425M25 112H125V338H25M655 112H555V338H655M25 170H62V280H25M655 170H618V280H655" />
        <circle cx="340" cy="225" r="55" />
        <path d="M125 179Q166 225 125 271M555 179Q514 225 555 271" />
        <rect x="14" y="199" width="11" height="52" />
        <rect x="655" y="199" width="11" height="52" />
      </g>
      <g fill="#8bab95">
        <circle cx="340" cy="225" r="2" />
        <circle cx="94" cy="225" r="2" />
        <circle cx="586" cy="225" r="2" />
      </g>
      {paths.map((path) =>
        heat ? (
          <g key={path.id}>
            {path.points.map(([x, y], i) => (
              <circle
                key={i}
                cx={25 + x * 630}
                cy={25 + y * 400}
                r="16"
                fill="url(#heat)"
              />
            ))}
          </g>
        ) : (
          <path
            key={path.id}
            d={path.points
              .map(
                ([x, y, t], i) =>
                  `${i === 0 || t - path.points[i - 1][2] > 3 ? "M" : "L"}${25 + x * 630},${25 + y * 400}`,
              )
              .join(" ")}
            fill="none"
            stroke={teamColor[path.team]}
            strokeWidth="1.5"
            opacity=".55"
          />
        ),
      )}
      {points.map((p) => (
        <g
          key={p.id}
          onClick={() => onSelect?.(p.id)}
          style={{ cursor: onSelect ? "pointer" : "default" }}
        >
          <circle
            cx={25 + p.x * 630}
            cy={25 + p.y * 400}
            r={selected === p.id ? 9 : 6}
            fill={teamColor[p.team]}
            stroke="#fff"
            strokeWidth="1.5"
          />
          {selected === p.id && (
            <circle
              cx={25 + p.x * 630}
              cy={25 + p.y * 400}
              r="15"
              fill="none"
              stroke="#fff"
            />
          )}
        </g>
      ))}
    </svg>
  );
}

function ModalShell({
  title,
  subtitle,
  children,
  onClose,
  wide = false,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  onClose: () => void;
  wide?: boolean;
}) {
  const root = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement;
    root.current?.querySelector<HTMLElement>("input,button,select")?.focus();
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "Tab") {
        const items = Array.from(
          root.current?.querySelectorAll<HTMLElement>(
            'input,button,select,textarea,[tabindex="0"]',
          ) || [],
        ).filter((x) => !x.hasAttribute("disabled"));
        if (e.shiftKey && document.activeElement === items[0]) {
          e.preventDefault();
          items.at(-1)?.focus();
        } else if (!e.shiftKey && document.activeElement === items.at(-1)) {
          e.preventDefault();
          items[0]?.focus();
        }
      }
    };
    document.addEventListener("keydown", handler);
    return () => {
      document.removeEventListener("keydown", handler);
      previous?.focus();
    };
  }, [onClose]);
  return (
    <div
      className="modal-backdrop"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={root}
        className={"modal " + (wide ? "wide" : "")}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <button
          className="icon-button close"
          onClick={onClose}
          aria-label="Close dialog"
        >
          <X size={20} />
        </button>
        <h2>{title}</h2>
        {subtitle && <p className="muted">{subtitle}</p>}
        {children}
      </div>
    </div>
  );
}

function App() {
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
    const id = window.setInterval(() => refresh().catch(() => {}), 2500);
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

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            setSection("library");
          }}
        >
          <span className="brand-symbol">
            <ScanLine size={23} />
          </span>
          matchlens<span className="brand-dot">.</span>
        </a>
        <div className="workspace-label">YOUR WORKSPACE</div>
        <nav>
          <button
            className={section === "library" ? "active" : ""}
            onClick={() => setSection("library")}
          >
            <Grid2X2 size={18} />
            Match library<span className="nav-count">{matches.length}</span>
          </button>
          <button
            className={section === "review" ? "active" : ""}
            onClick={() =>
              selected
                ? setSection("review")
                : notify("Choose a match from your library first")
            }
          >
            <ScanLine size={18} />
            Analysis studio
          </button>
          <button
            className={section === "compare" ? "active" : ""}
            onClick={() => setSection("compare")}
          >
            <Layers size={18} />
            Compare matches
          </button>
          <button
            className={section === "settings" ? "active" : ""}
            onClick={() => setSection("settings")}
          >
            <Settings2 size={18} />
            Local setup
          </button>
        </nav>
        <div className="sidebar-bottom">
          <div className="privacy-card">
            <ShieldCheck size={22} />
            <strong>Your footage. Your machine.</strong>
            <p>
              No cloud uploads.
              <br />
              No account required.
            </p>
            <span>
              <i className="dot" />
              LOCAL WORKSPACE
            </span>
          </div>
          <div className="user">
            <div className="avatar">ML</div>
            <div>
              Personal workspace
              <small>
                {system
                  ? `${bytes(system.disk_free)} available`
                  : "Connecting locally…"}
              </small>
            </div>
            <ChevronDown size={15} />
          </div>
        </div>
      </aside>
      <main className="main">
        <header className="topbar">
          <div className="breadcrumb">
            Workspace <ChevronRight size={14} />
            <span>
              {section === "library"
                ? "Match library"
                : section === "review"
                  ? detail?.match.title || "Analysis studio"
                  : section === "compare"
                    ? "Compare matches"
                    : "Local setup"}
            </span>
          </div>
          <div className="topbar-right">
            <span className="local-status">
              <i className="dot" />
              Local processing
            </span>
            <span className="version">BETA 0.1</span>
          </div>
        </header>
        {section === "library" && (
          <div className="page">
            <div className="page-heading">
              <div>
                <div className="eyebrow">THE GAME, IN FOCUS</div>
                <h1>
                  Your match library<span>.</span>
                </h1>
                <p>Every moment. A clearer picture of the game.</p>
              </div>
              <button
                className="button primary"
                onClick={() => setModal("new")}
              >
                <Plus size={18} />
                New match
              </button>
            </div>
            <div className="library-stats">
              <div>
                <span className="stat-icon">
                  <Film size={19} />
                </span>
                <div>
                  <strong>{matches.length.toString().padStart(2, "0")}</strong>
                  <span>Matches in your library</span>
                </div>
              </div>
              <div>
                <span className="stat-icon">
                  <Clock3 size={19} />
                </span>
                <div>
                  <strong>
                    {Math.round(
                      matches.reduce((s, m) => s + m.duration, 0) / 60,
                    )}
                    <small> min</small>
                  </strong>
                  <span>Recorded match time</span>
                </div>
              </div>
              <div>
                <span className="stat-icon">
                  <ShieldCheck size={19} />
                </span>
                <div>
                  <strong>
                    100%<small> local</small>
                  </strong>
                  <span>Your data stays with you</span>
                </div>
              </div>
            </div>
            <div className="section-toolbar">
              <h2>
                All matches <span className="count">{matches.length}</span>
              </h2>
              <div className="search">
                <Search size={17} />
                <input
                  aria-label="Search matches"
                  placeholder="Search your matches"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
              </div>
            </div>
            {matches.length === 0 ? (
              <div className="welcome-grid">
                <div className="welcome">
                  <span className="round-icon">
                    <Video size={26} />
                  </span>
                  <h2>It starts with a recording.</h2>
                  <p>
                    Bring in a game, follow your players, and turn the moments
                    that matter into a reviewable match story.
                  </p>
                  <button
                    className="button primary"
                    onClick={() => setModal("new")}
                  >
                    <Upload size={17} />
                    Import your first match
                  </button>
                  <button
                    className="text-button"
                    disabled={busy}
                    onClick={() =>
                      act(async () => {
                        const m = await api<Match>("/demo", "POST");
                        openMatch(m.id);
                      }, "Generating a clearly labeled synthetic demo…")
                    }
                  >
                    Explore a synthetic demo <ArrowRight size={16} />
                  </button>
                  <div className="supported">
                    MP4 · MOV · MKV · WEBM · SCREEN RECORDINGS
                  </div>
                </div>
                <div className="welcome-field">
                  <div className="field-card-heading">
                    <span>
                      <i className="dot" />A DIFFERENT PERSPECTIVE
                    </span>
                    <ScanLine size={18} />
                  </div>
                  <Pitch />
                  <div className="field-caption">
                    <strong>See the shape of your game.</strong>
                    <p>Track players. Review decisions. Keep the evidence.</p>
                  </div>
                </div>
              </div>
            ) : (
              <div className="match-grid">
                {matches
                  .filter((m) =>
                    `${m.title} ${m.home} ${m.away}`
                      .toLowerCase()
                      .includes(query.toLowerCase()),
                  )
                  .map((m) => (
                    <MatchCard
                      key={m.id}
                      match={m}
                      onClick={() => openMatch(m.id)}
                    />
                  ))}
                <button
                  className="new-match-card"
                  onClick={() => setModal("new")}
                >
                  <Plus size={26} />
                  <strong>Add another match</strong>
                  <span>Import a recording or set up capture</span>
                </button>
              </div>
            )}
            <div className="footnote">
              <ShieldCheck size={15} />
              <span>
                Original recordings are preserved. Analysis can always be
                reviewed and corrected.
              </span>
            </div>
          </div>
        )}

        {section === "review" &&
          (!detail ? (
            <div className="loading">
              <Loader2 className="spin" />
              Opening your match…
            </div>
          ) : (
            <div className="page studio">
              <div className="page-heading compact">
                <div>
                  <button
                    className="back-link"
                    onClick={() => setSection("library")}
                  >
                    <ArrowLeft size={14} />
                    All matches
                  </button>
                  <h1>{detail.match.title}</h1>
                  <p>
                    {detail.match.date ||
                      new Date(detail.match.created * 1000).toLocaleDateString(
                        undefined,
                        { month: "long", day: "numeric", year: "numeric" },
                      )}
                    <span className="separator">/</span>Soccer
                    <span className="separator">/</span>
                    {clock(detail.match.duration)} recorded{" "}
                    <span className="tag">
                      {detail.match.profile === "synthetic"
                        ? "SYNTHETIC DEMO"
                        : "LOCAL FILES"}
                    </span>
                  </p>
                </div>
                <div className="button-group">
                  <button
                    className="button"
                    onClick={() => setModal("capture")}
                  >
                    <Radio size={16} />
                    Capture
                  </button>
                  <button
                    className="button primary"
                    onClick={() => setModal("analyze")}
                    disabled={!detail.sources.length || !!runningAnalysis}
                  >
                    <ScanLine size={17} />
                    {runningAnalysis ? "Analyzing…" : "Analyze match"}
                  </button>
                </div>
              </div>
              {detail.match.profile === "synthetic" && (
                <div className="notice">
                  <Flag size={16} />
                  Synthetic engineering fixture. Video, events, and identities
                  are demonstrations—not real match results or accuracy
                  measurements.
                </div>
              )}
              {progress !== null && (
                <div className="notice">
                  <Loader2 className="spin" size={16} />
                  Saving your original recording… {Math.round(progress * 100)}%
                  <progress value={progress} max={1} />
                </div>
              )}
              <div className="tabs">
                {[
                  ["overview", "Overview"],
                  ["timeline", "Timeline"],
                  ["players", "Players"],
                  ["field", "Field analysis"],
                  ["exports", "Highlights & reports"],
                ].map(([id, name]) => (
                  <button
                    className={tab === id ? "active" : ""}
                    onClick={() => setTab(id)}
                    key={id}
                  >
                    {name}
                    {id === "timeline" && <span>{detail.events.length}</span>}
                  </button>
                ))}
                <div className="tabs-actions">
                  <button
                    className="icon-button"
                    title="Undo review edit"
                    onClick={() =>
                      act(() =>
                        api(`/matches/${selected}/history/undo`, "POST", {
                          revision: detail.match.revision,
                        }),
                      )
                    }
                  >
                    <Undo2 size={17} />
                  </button>
                  <button
                    className="icon-button"
                    title="Redo review edit"
                    onClick={() =>
                      act(() =>
                        api(`/matches/${selected}/history/redo`, "POST", {
                          revision: detail.match.revision,
                        }),
                      )
                    }
                  >
                    <Redo2 size={17} />
                  </button>
                  <small>Revision {detail.match.revision}</small>
                </div>
              </div>
              {activeJobs.length > 0 && (
                <div className="jobs-strip">
                  {activeJobs.map((j) => (
                    <div className="job-inline" key={j.id}>
                      <span
                        className={
                          "dot " + (j.kind === "capture" ? "record-dot" : "")
                        }
                      />
                      <strong>
                        {j.kind === "capture"
                          ? "Recording"
                          : j.kind === "analysis"
                            ? "Analyzing"
                            : `Creating ${j.kind}`}
                      </strong>
                      <span>
                        {j.kind === "analysis"
                          ? `${Math.round(j.progress * 100)}% · ${j.metrics?.processed_fps?.toFixed(1) || "—"} frames/s`
                          : j.status}
                      </span>
                      {j.kind === "analysis" && (
                        <progress value={j.progress} max={1} />
                      )}
                      {(j.kind === "analysis" || j.kind === "capture") && (
                        <button
                          className="text-button"
                          onClick={() =>
                            act(() =>
                              api(
                                `/matches/${selected}/jobs/${j.id}/pause`,
                                "POST",
                              ),
                            )
                          }
                        >
                          {j.kind === "capture" ? "Stop recording" : "Pause"}
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}
              {detail.jobs
                .filter((j) => ["failed", "paused"].includes(j.status))
                .slice(0, 2)
                .map((j) => (
                  <div className="notice warning" key={j.id}>
                    <AlertTriangle size={16} />
                    <span>
                      {j.kind} {j.status}:{" "}
                      {j.error || "Paused at the last saved checkpoint."}
                    </span>
                    {j.kind === "analysis" && (
                      <button
                        className="text-button"
                        onClick={() =>
                          act(() =>
                            api(
                              `/matches/${selected}/jobs/${j.id}/resume`,
                              "POST",
                            ),
                          )
                        }
                      >
                        Resume
                      </button>
                    )}
                  </div>
                ))}
              {["overview", "timeline"].includes(tab) && (
                <div className="studio-grid">
                  <div className="video-column">
                    <div className="panel video-panel">
                      <div className="panel-header">
                        <h3>
                          <Video size={16} />
                          Match recording
                        </h3>
                        <div className="button-group">
                          {detail.sources.length > 0 && (
                            <select
                              aria-label="Video source"
                              value={sourceId}
                              onChange={(e) => {
                                setSourceId(e.target.value);
                                setSegmentId("");
                                setFrame(null);
                              }}
                            >
                              {detail.sources.map((s) => (
                                <option value={s.id} key={s.id}>
                                  {s.name}
                                </option>
                              ))}
                            </select>
                          )}
                          <button
                            className="icon-button"
                            title="Import recording"
                            onClick={() => importInput.current?.click()}
                          >
                            <Upload size={17} />
                          </button>
                        </div>
                      </div>
                      {source && (
                        <details className="source-tools">
                          <summary>
                            Source alignment & analysis versions
                          </summary>
                          <div className="source-tools-body">
                            <label>
                              Active analysis
                              <select
                                value={detail.active_runs[sourceId] || ""}
                                onChange={(e) =>
                                  act(
                                    () =>
                                      api(
                                        `/matches/${selected}/runs/${e.target.value}/activate`,
                                        "POST",
                                      ),
                                    "Analysis version selected",
                                  )
                                }
                              >
                                <option value="" disabled>
                                  No analysis selected
                                </option>
                                {detail.jobs
                                  .filter(
                                    (j) =>
                                      j.kind === "analysis" &&
                                      j.config.source_id === sourceId &&
                                      ["complete", "paused"].includes(j.status),
                                  )
                                  .map((j) => (
                                    <option value={j.id} key={j.id}>
                                      {j.id.slice(0, 8)} · {j.status} ·{" "}
                                      {String(j.config.detector)}
                                    </option>
                                  ))}
                              </select>
                            </label>
                            <button
                              className="button small"
                              disabled={
                                !!detail.active_runs[sourceId] ||
                                source.status === "recording"
                              }
                              onClick={() => {
                                const offset = prompt(
                                  "Match timeline offset in seconds. Align before analyzing this source.",
                                  String(source.offset),
                                );
                                if (offset !== null)
                                  act(
                                    () =>
                                      api(
                                        `/matches/${selected}/sources/${source.id}/offset`,
                                        "POST",
                                        { offset: Number(offset) },
                                      ),
                                    "Source aligned",
                                  );
                              }}
                            >
                              Set source offset ({source.offset}s)
                            </button>
                            <small>
                              Changing analysis versions can orphan corrections
                              tied to old track IDs. They remain stored with
                              their original IDs.
                            </small>
                          </div>
                        </details>
                      )}
                      {recording && (
                        <div className="live-controls">
                          <div className="segmented">
                            {(["feed", "analysis", "review"] as const).map(
                              (mode) => (
                                <button
                                  key={mode}
                                  className={liveMode === mode ? "active" : ""}
                                  onClick={() => setLiveMode(mode)}
                                >
                                  {mode === "feed"
                                    ? "Buffered feed"
                                    : mode === "analysis"
                                      ? "Delayed analysis"
                                      : "Review"}
                                </button>
                              ),
                            )}
                          </div>
                          <small>
                            {latestAnalysis?.metrics?.analysis_delay !==
                            undefined
                              ? `${latestAnalysis.metrics.analysis_delay?.toFixed(1)} s behind saved video`
                              : "Waiting for analysis"}{" "}
                            · recording continues
                          </small>
                        </div>
                      )}
                      <div
                        className={
                          "video-stage " + (pointEdit ? "point-edit" : "")
                        }
                        style={{ aspectRatio: videoRatio }}
                        onClick={(e) => {
                          if (pointEdit && trackId && currentFrame) {
                            const r = e.currentTarget.getBoundingClientRect();
                            act(
                              () =>
                                correction("point", {
                                  track_id: trackId,
                                  time: currentFrame.time,
                                  point: [
                                    (e.clientX - r.left) / r.width,
                                    (e.clientY - r.top) / r.height,
                                  ],
                                }),
                              "Position corrected",
                            );
                            setPointEdit(false);
                          }
                        }}
                      >
                        {mediaUrl ? (
                          <>
                            <video
                              key={mediaUrl}
                              ref={video}
                              src={mediaUrl}
                              muted={recording && liveMode === "feed"}
                              onTimeUpdate={updateTime}
                              onPlay={() => setPlaying(true)}
                              onPause={() => setPlaying(false)}
                              onEnded={() => {
                                if (!segment || !source?.segments) return;
                                const next = source.segments.find(
                                  (s) =>
                                    s.start >= segment.end - 0.1 &&
                                    s.id !== segment.id,
                                );
                                if (!next) return;
                                const contiguous =
                                  next.start - segment.end < 0.15;
                                resumePlayback.current = contiguous;
                                pendingSeek.current = 0;
                                setSegmentId(next.id);
                                if (!contiguous)
                                  notify(
                                    "Recording gap: playback paused at the next available segment.",
                                  );
                              }}
                              onLoadedMetadata={() => {
                                if (video.current) {
                                  setVideoRatio(
                                    video.current.videoWidth /
                                      video.current.videoHeight || 16 / 9,
                                  );
                                  if (pendingSeek.current !== null) {
                                    video.current.currentTime =
                                      pendingSeek.current;
                                    pendingSeek.current = null;
                                  }
                                  if (
                                    (recording && liveMode === "feed") ||
                                    resumePlayback.current
                                  )
                                    video.current.play().catch(() => {});
                                  resumePlayback.current = false;
                                }
                                updateTime();
                              }}
                              onError={() =>
                                notify(
                                  "This container may need a playback proxy, or the segment is not ready. Original media remains preserved.",
                                )
                              }
                              playsInline
                            />
                            {overlay &&
                              currentFrame &&
                              !currentFrame.excluded && (
                                <svg
                                  className="video-overlay"
                                  viewBox="0 0 1000 1000"
                                  preserveAspectRatio="none"
                                >
                                  {currentFrame.tracks.map((t) => (
                                    <g
                                      key={t.id}
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        setTrackId(t.id);
                                        setModal("track");
                                      }}
                                    >
                                      <rect
                                        x={t.box[0] * 1000}
                                        y={t.box[1] * 1000}
                                        width={(t.box[2] - t.box[0]) * 1000}
                                        height={(t.box[3] - t.box[1]) * 1000}
                                        fill="transparent"
                                        stroke={teamColor[t.team]}
                                        strokeWidth="2"
                                      />
                                      <text
                                        x={t.box[0] * 1000}
                                        y={t.box[1] * 1000 - 7}
                                        fill={teamColor[t.team]}
                                        fontSize="15"
                                      >
                                        {t.player ||
                                          t.display_id.split("-").at(-1)}
                                      </text>
                                    </g>
                                  ))}
                                </svg>
                              )}
                            <div className="video-badges">
                              <span>
                                <i
                                  className={
                                    "dot " + (recording ? "record-dot" : "")
                                  }
                                />
                                {recording ? "RECORDING" : "ORIGINAL PRESERVED"}
                              </span>
                              {overlay && (
                                <span>
                                  {currentFrame
                                    ? "TRACK OVERLAY"
                                    : "NO ANALYSIS AT THIS TIME"}
                                </span>
                              )}
                            </div>
                          </>
                        ) : (
                          <div className="video-empty">
                            <Film size={40} />
                            <h3>Your game goes here</h3>
                            <p>Import a recording to start your analysis.</p>
                            <button
                              className="button light"
                              onClick={() => importInput.current?.click()}
                            >
                              <Upload size={16} />
                              Choose a video
                            </button>
                          </div>
                        )}
                      </div>
                      <div className="video-controls">
                        <button
                          className="icon-button play"
                          aria-label={playing ? "Pause video" : "Play video"}
                          onClick={() =>
                            video.current?.paused
                              ? video.current.play()
                              : video.current?.pause()
                          }
                        >
                          {playing ? <Pause size={18} /> : <Play size={18} />}
                        </button>
                        <span className="timecode">
                          {clock(time)}{" "}
                          <span>/ {clock(detail.match.duration)}</span>
                        </span>
                        <div className="spacer" />
                        <button
                          className={
                            "toggle-button " + (overlay ? "selected" : "")
                          }
                          onClick={() => setOverlay(!overlay)}
                        >
                          <ScanLine size={15} />
                          Tracks
                        </button>
                        <button
                          className="icon-button"
                          title="Create custom clip"
                          onClick={() => setModal("clip")}
                        >
                          <Scissors size={17} />
                        </button>
                        <button
                          className="icon-button"
                          title="Calibrate field"
                          onClick={calibrate}
                        >
                          <Map size={17} />
                        </button>
                      </div>
                      <div className="timeline-scrub">
                        <input
                          type="range"
                          min={mediaOffset}
                          max={segment?.end || detail.match.duration || 1}
                          step=".05"
                          value={time}
                          aria-label="Seek recording"
                          onChange={(e) => seek(Number(e.target.value))}
                        />
                        <div className="event-ticks">
                          {detail.events
                            .filter(
                              (e) =>
                                e.status !== "rejected" &&
                                e.start >= mediaOffset &&
                                e.start <=
                                  (segment?.end || detail.match.duration),
                            )
                            .map((e) => (
                              <button
                                key={e.id}
                                title={`${labels[e.kind]} at ${clock(e.start)}`}
                                style={{
                                  left: `${(100 * (e.start - mediaOffset)) / ((segment?.end || detail.match.duration) - mediaOffset || 1)}%`,
                                  background: teamColor[e.team],
                                }}
                                onClick={() => seek(e.start)}
                              />
                            ))}
                        </div>
                      </div>
                      {source?.segments && (
                        <div className="segment-select">
                          <label>
                            Recording segment{" "}
                            <select
                              value={segment?.id || ""}
                              onChange={(e) => setSegmentId(e.target.value)}
                            >
                              {source.segments.map((s) => (
                                <option value={s.id} key={s.id}>
                                  {clock(s.start)} — {clock(s.end)}
                                </option>
                              ))}
                            </select>
                          </label>
                          <span>Only committed segments are shown.</span>
                        </div>
                      )}
                    </div>
                    <div className="video-footer">
                      <span>
                        <ShieldCheck size={14} />
                        Original footage stays unchanged
                      </span>
                      <span>SPACE play / pause · ← → seek · E add event</span>
                    </div>
                    <div className="panel field-preview">
                      <div className="panel-header">
                        <h3>
                          <Map size={16} />
                          The field, from above
                        </h3>
                        <button
                          className="text-button"
                          onClick={() => setTab("field")}
                        >
                          Explore field <ArrowRight size={14} />
                        </button>
                      </div>
                      <div className="field-preview-body">
                        <div>
                          <Pitch
                            points={(currentFrame?.tracks || [])
                              .filter((t) => t.field)
                              .map((t) => ({
                                id: t.id,
                                x: t.field![0],
                                y: t.field![1],
                                team: t.team,
                              }))}
                          />
                        </div>
                        <div>
                          <span className="eyebrow">SPATIAL CONTEXT</span>
                          <h3>
                            {currentFrame?.calibrated
                              ? "A new perspective."
                              : "Give your video a field."}
                          </h3>
                          <p>
                            {currentFrame?.calibrated
                              ? "Positions match the analyzed video timestamp. Unseen areas remain unknown."
                              : "Identify pitch landmarks to map observed player positions onto a top-down field."}
                          </p>
                          <button className="button small" onClick={calibrate}>
                            {currentFrame?.calibrated
                              ? "Update calibration"
                              : "Calibrate field"}
                            <ArrowRight size={14} />
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                  <aside className="insight-column">
                    <div className="panel scoreboard">
                      <div className="score-label">
                        <span className="eyebrow">REVIEWED SCORE</span>
                        <button
                          className="icon-button"
                          title="Set match clock"
                          onClick={() => setModal("clock")}
                        >
                          <Clock3 size={15} />
                        </button>
                      </div>
                      <div className="score-teams">
                        <div>
                          <span className="team-crest home">
                            {detail.match.home.slice(0, 2).toUpperCase()}
                          </span>
                          <strong>{detail.match.home}</strong>
                        </div>
                        <div className="score-number">
                          {detail.statistics.score.home}
                          <span>:</span>
                          {detail.statistics.score.away}
                        </div>
                        <div>
                          <span className="team-crest away">
                            {detail.match.away.slice(0, 2).toUpperCase()}
                          </span>
                          <strong>{detail.match.away}</strong>
                        </div>
                      </div>
                      <div className="match-clock">
                        Period {detail.review.clock.period} ·{" "}
                        {clock(
                          Math.max(
                            0,
                            time -
                              detail.review.clock.media_anchor +
                              detail.review.clock.match_anchor,
                          ),
                        )}
                        <span>From confirmed goals</span>
                      </div>
                    </div>
                    <div className="panel">
                      <div className="panel-header">
                        <h3>Match insights</h3>
                        <span className="pill">REVIEWABLE</span>
                      </div>
                      <div className="insights">
                        <div className="metric-big">
                          <span>Analysis coverage</span>
                          <strong>
                            {detail.statistics.coverage_percent}
                            <small>%</small>
                          </strong>
                        </div>
                        <div className="meter">
                          <i
                            style={{
                              width: detail.statistics.coverage_percent + "%",
                            }}
                          />
                        </div>
                        <small>Sampled time, not guaranteed visibility</small>
                        <div className="mini-stats">
                          <div>
                            <strong>{detail.statistics.unique_tracks}</strong>
                            <span>Player tracks</span>
                          </div>
                          <div>
                            <strong>
                              {detail.statistics.confirmed_events}
                            </strong>
                            <span>Confirmed events</span>
                          </div>
                        </div>
                        <div className="possession-title">
                          Reviewed possession{" "}
                          <span>
                            UNKNOWN{" "}
                            {detail.statistics.possession.percent.unknown ??
                              100}
                            %
                          </span>
                        </div>
                        <div className="possession-bar">
                          <i
                            style={{
                              width:
                                (detail.statistics.possession.percent.home ||
                                  0) + "%",
                              background: teamColor.home,
                            }}
                          />
                          <i
                            style={{
                              width:
                                (detail.statistics.possession.percent.away ||
                                  0) + "%",
                              background: teamColor.away,
                            }}
                          />
                        </div>
                        <div className="team-legend">
                          <span>
                            <i style={{ background: teamColor.home }} />
                            {detail.match.home}
                          </span>
                          <span>
                            <i style={{ background: teamColor.away }} />
                            {detail.match.away}
                          </span>
                        </div>
                      </div>
                    </div>
                    <div className="panel events-panel">
                      <div className="panel-header">
                        <h3>
                          Match moments{" "}
                          <span className="count">
                            {
                              detail.events.filter(
                                (e) =>
                                  tab === "timeline" || e.status !== "rejected",
                              ).length
                            }
                          </span>
                        </h3>
                        <button
                          className="icon-button"
                          title="Add event"
                          onClick={() => {
                            setEventEdit(null);
                            setModal("event");
                          }}
                        >
                          <Plus size={18} />
                        </button>
                      </div>
                      <div className="event-list">
                        {detail.events
                          .filter(
                            (e) =>
                              tab === "timeline" || e.status !== "rejected",
                          )
                          .map((e) => (
                            <div
                              className={
                                "event-row " + (e.excluded ? "excluded" : "")
                              }
                              key={e.id}
                            >
                              <button
                                className="event-time"
                                onClick={() => seek(e.start)}
                              >
                                {clock(e.start)}
                              </button>
                              <span
                                className="event-icon"
                                style={{ color: teamColor[e.team] }}
                              >
                                {e.kind === "goal" ? (
                                  <Goal size={17} />
                                ) : e.kind === "shot" ? (
                                  <Target size={17} />
                                ) : e.kind === "possession" ? (
                                  <Clock3 size={17} />
                                ) : (
                                  <Flag size={16} />
                                )}
                              </span>
                              <button
                                className="event-description"
                                onClick={() => {
                                  setEventEdit(e);
                                  setModal("event");
                                }}
                              >
                                <strong>
                                  {labels[e.kind]}
                                  {e.status === "rejected" ? " · rejected" : ""}
                                  {e.excluded ? " · excluded" : ""}
                                </strong>
                                <span>
                                  {e.player ||
                                    {
                                      home: detail.match.home,
                                      away: detail.match.away,
                                      unknown: "Unassigned",
                                    }[e.team]}
                                </span>
                              </button>
                              {e.status === "confirmed" ? (
                                <CheckCircle2 size={15} className="confirmed" />
                              ) : (
                                <button
                                  className="icon-button"
                                  title="Confirm event"
                                  onClick={() => eventAction(e, "confirmed")}
                                >
                                  <Check size={16} />
                                </button>
                              )}
                            </div>
                          ))}
                        {detail.events.length === 0 && (
                          <div className="small-empty">
                            <Flag size={25} />
                            <strong>Your timeline starts here</strong>
                            <p>
                              Tag a moment while you watch. Confirmed events
                              power your report.
                            </p>
                          </div>
                        )}
                      </div>
                      <button
                        className="panel-footer-button"
                        onClick={() => {
                          setEventEdit(null);
                          setModal("event");
                        }}
                      >
                        <Plus size={16} />
                        Add a match moment
                      </button>
                    </div>
                  </aside>
                </div>
              )}
              {tab === "timeline" && (
                <div className="panel timeline-tools">
                  <div>
                    <h3>Review the whole story</h3>
                    <p>
                      Exclude replays, set period clocks, or trim a custom
                      highlight. All review edits are reversible.
                    </p>
                  </div>
                  <button
                    className="button"
                    onClick={() => setModal("exclude")}
                  >
                    Exclude an interval
                  </button>
                  <button className="button" onClick={() => setModal("clip")}>
                    <Scissors size={16} />
                    Create clip
                  </button>
                </div>
              )}
              {tab === "players" && !!detail.statistics.players?.length && (
                <div className="panel" style={{ marginBottom: 20 }}>
                  <div className="panel-header">
                    <h3>Reviewed player summaries</h3>
                  </div>
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>Player</th>
                          <th>Team</th>
                          <th>Observed time</th>
                          <th>Confirmed events</th>
                        </tr>
                      </thead>
                      <tbody>
                        {detail.statistics.players.map((p, i) => (
                          <tr key={i}>
                            <td>{p.player}</td>
                            <td>
                              {p.team === "unknown"
                                ? "Unknown"
                                : detail.match[p.team]}
                            </td>
                            <td>{p.observed_seconds.toFixed(1)} s</td>
                            <td>
                              {Object.entries(p.counts)
                                .map(
                                  ([kind, n]) =>
                                    `${labels[kind] || kind}: ${n}`,
                                )
                                .join(" · ") || "None reviewed"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <p className="panel-description">
                    Observed time is not minutes played. Counts include reviewed
                    events only; linked fragments are not double-counted in
                    observed time.
                  </p>
                </div>
              )}
              {tab === "players" && (
                <div className="panel">
                  <div className="panel-header">
                    <div>
                      <h2>Follow the player, not just the box.</h2>
                      <p className="muted">
                        Anonymous tracks become player identities only when you
                        link them. Visibility gaps stay unknown.
                      </p>
                    </div>
                    <Users size={22} />
                  </div>
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Track / player</th>
                          <th>Team</th>
                          <th>Role</th>
                          <th>Observed</th>
                          <th>Video interval</th>
                          <th>Review</th>
                        </tr>
                      </thead>
                      <tbody>
                        {detail.tracks.map((t) => (
                          <tr key={t.id}>
                            <td>
                              <span
                                className="player-dot"
                                style={{ background: teamColor[t.team] }}
                              />
                              {t.player || `Track ${t.id.split("-").at(-1)}`}
                              <small>{t.id}</small>
                            </td>
                            <td>
                              {t.team === "unknown"
                                ? `Unassigned${t.team_hint && t.team_hint !== "unknown" ? " · " + t.team_hint : ""}`
                                : detail.match[t.team]}
                            </td>
                            <td>{t.role}</td>
                            <td>{t.observed_seconds.toFixed(1)} s</td>
                            <td>
                              <button
                                className="text-button"
                                onClick={() => {
                                  setTab("overview");
                                  setTimeout(() => seek(t.start), 100);
                                }}
                              >
                                {clock(t.start)}–{clock(t.end)}
                              </button>
                            </td>
                            <td>
                              <button
                                className="button small"
                                onClick={() => {
                                  setTrackId(t.id);
                                  setModal("track");
                                }}
                              >
                                <SlidersHorizontal size={14} />
                                Edit identity
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {!detail.tracks.length && (
                      <div className="small-empty">
                        <Users size={30} />
                        <h3>No player tracks yet</h3>
                        <p>
                          Run analysis on your recording to inspect its player
                          tracks.
                        </p>
                        <button
                          className="button"
                          onClick={() => setModal("analyze")}
                        >
                          Set up analysis
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              )}
              {tab === "field" && (
                <div className="field-page">
                  <div className="panel">
                    <div className="panel-header">
                      <h3>Movement, with context</h3>
                      <div className="segmented">
                        <button
                          className={!viewHeat ? "active" : ""}
                          onClick={() => setViewHeat(false)}
                        >
                          Paths
                        </button>
                        <button
                          className={viewHeat ? "active" : ""}
                          onClick={() => setViewHeat(true)}
                        >
                          Heatmap
                        </button>
                      </div>
                    </div>
                    <div className="large-pitch">
                      <Pitch
                        heat={viewHeat}
                        paths={detail.tracks
                          .filter((t) => !trackId || t.id === trackId)
                          .map((t) => ({
                            id: t.id,
                            points: t.path,
                            team: t.team,
                          }))}
                      />
                    </div>
                    <div className="panel-description">
                      Only observed, calibrated positions are shown. Heat is
                      sampled occupancy; it is not exact distance, speed, or
                      full-field coverage.
                    </div>
                  </div>
                  <div className="panel field-settings">
                    <h3>Field settings</h3>
                    <label>
                      Player track
                      <select
                        value={trackId}
                        onChange={(e) => setTrackId(e.target.value)}
                      >
                        <option value="">All observed tracks</option>
                        {detail.tracks.map((t) => (
                          <option value={t.id} key={t.id}>
                            {t.player || t.id}
                          </option>
                        ))}
                      </select>
                    </label>
                    <div className="divider" />
                    <h4>Calibration</h4>
                    <p>
                      {detail.review.calibrations.length
                        ? `${detail.review.calibrations.length} calibration interval(s). Fit has not been independently validated.`
                        : "No calibration yet. Open a frame in Overview and identify visible pitch landmarks."}
                    </p>
                    <button
                      className="button"
                      onClick={() => setTab("overview")}
                    >
                      Open video calibration <ArrowRight size={15} />
                    </button>
                    <div className="notice warning">
                      <AlertTriangle size={17} />
                      Recalibrate after camera movement. A ground-plane
                      transform cannot locate an airborne ball.
                    </div>
                  </div>
                </div>
              )}
              {tab === "exports" && (
                <>
                  <div className="export-actions">
                    <div className="panel export-action">
                      <span className="round-icon">
                        <Scissors size={23} />
                      </span>
                      <h3>The moments worth keeping.</h3>
                      <p>
                        Build highlights from confirmed events, or trim your own
                        clip. Filter reels by team or reviewed player identity.
                      </p>
                      <button
                        className="button primary"
                        onClick={() => setModal("clip")}
                      >
                        Create highlights <ArrowRight size={16} />
                      </button>
                    </div>
                    <div className="panel export-action">
                      <span className="round-icon">
                        <FileText size={23} />
                      </span>
                      <h3>A report you can stand behind.</h3>
                      <p>
                        Statistics, coverage, field visualization, and the
                        timeline—with JSON and CSV for your own analysis.
                      </p>
                      <button
                        className="button"
                        disabled={busy}
                        onClick={() =>
                          act(
                            () => api(`/matches/${selected}/report`, "POST"),
                            "Report queued",
                          )
                        }
                      >
                        Generate report <ArrowRight size={16} />
                      </button>
                    </div>
                  </div>
                  <div className="panel">
                    <div className="panel-header">
                      <h3>Your exports</h3>
                      <span className="muted">
                        Local files · versioned results
                      </span>
                    </div>
                    {detail.exports.map((a) => (
                      <div className="export-row" key={a.id}>
                        <span className="file-icon">
                          {a.kind === "report" ? (
                            <FileText size={22} />
                          ) : (
                            <Film size={22} />
                          )}
                        </span>
                        <div>
                          <strong>{a.title}</strong>
                          <small>
                            Revision {a.revision}{" "}
                            {a.revision !== detail.match.revision
                              ? "· older than current review"
                              : ""}
                            {a.duration ? ` · ${clock(a.duration)}` : ""}
                          </small>
                        </div>
                        <div className="export-links">
                          {Object.keys(a.files).map((name) => (
                            <a
                              className="button small"
                              key={name}
                              href={exportUrl(a, name)}
                              target="_blank"
                              rel="noreferrer"
                            >
                              <Download size={13} />
                              {name.split(".").at(-1)?.toUpperCase()}
                            </a>
                          ))}
                        </div>
                      </div>
                    ))}
                    {!detail.exports.length && (
                      <div className="small-empty">
                        <ArrowDownToLine size={28} />
                        <p>Your clips and reports will appear here.</p>
                      </div>
                    )}
                  </div>
                </>
              )}
              {detail.warnings.length > 0 && (
                <details className="quality-warnings">
                  <summary>
                    <AlertTriangle size={15} />
                    Quality observations ({detail.warnings.length})
                  </summary>
                  {detail.warnings.map((w) => (
                    <p key={w}>{w}</p>
                  ))}
                </details>
              )}
              <div className="studio-bottom">
                <span>
                  <ShieldCheck size={14} />
                  Statistics describe confirmed events and observed footage.
                </span>
                <button
                  className="text-button danger"
                  onClick={() => {
                    if (
                      confirm(
                        "Permanently delete this match and all its managed footage, analysis, and exports? External originals and downloaded copies remain.",
                      )
                    )
                      act(
                        async () => {
                          await api(`/matches/${selected}`, "DELETE");
                          setSelected(null);
                          setDetail(null);
                          setSection("library");
                          setMatches(await api<Match[]>("/matches"));
                        },
                        "Managed match data deleted",
                        false,
                      );
                  }}
                >
                  <Trash2 size={14} />
                  Delete match
                </button>
              </div>
            </div>
          ))}
        {section === "settings" && (
          <div className="page">
            <div className="page-heading">
              <div>
                <div className="eyebrow">BUILT AROUND YOUR MACHINE</div>
                <h1>
                  Local, by design<span>.</span>
                </h1>
                <p>Your setup, privacy, and analysis capabilities.</p>
              </div>
              <ShieldCheck size={38} />
            </div>
            {system && (
              <div className="settings-grid">
                <div className="panel settings-panel">
                  <h3>Storage & privacy</h3>
                  <dl>
                    <dt>Match data</dt>
                    <dd className="path">{system.data_dir}</dd>
                    <dt>Available storage</dt>
                    <dd>{bytes(system.disk_free)}</dd>
                    <dt>Account</dt>
                    <dd>Not required</dd>
                    <dt>External services</dt>
                    <dd>No required cloud services or paid APIs</dd>
                  </dl>
                  <p>
                    Match data defaults outside iCloud Drive. Exported copies
                    and operating-system backups are managed separately.
                  </p>
                </div>
                <div className="panel settings-panel">
                  <h3>Analysis engine</h3>
                  <dl>
                    <dt>Player detector</dt>
                    <dd>
                      <span
                        className={
                          "status-pill " + (system.model_ready ? "ready" : "")
                        }
                      >
                        {system.model_ready
                          ? "YOLOX installed locally"
                          : "Model not installed"}
                      </span>
                    </dd>
                    <dt>Runtime providers</dt>
                    <dd>{system.providers.join(", ")}</dd>
                    <dt>Install / validate model</dt>
                    <dd>
                      <code>.venv/bin/python run.py model install</code>
                    </dd>
                  </dl>
                  <p>
                    No downloads happen during ordinary analysis. Offline model
                    import is also supported.
                  </p>
                </div>
                <div className="panel settings-panel">
                  <h3>Capability boundaries</h3>
                  {Object.entries(system.capabilities).map(([k, v]) => (
                    <div className="capability" key={k}>
                      <strong>{k.replaceAll("_", " ")}</strong>
                      <span>{v}</span>
                    </div>
                  ))}
                </div>
                <div className="panel settings-panel">
                  <h3>Phone capture</h3>
                  <p>
                    Pair from a match, then start the separate HTTPS receiver.
                    Your phone streams to this computer over the local network.
                  </p>
                  <code>
                    .venv/bin/python run.py receiver --cert cert.pem --key
                    key.pem
                  </code>
                  <p>
                    The certificate must be trusted by your phone. Keep it awake
                    and connected to power; background capture is not
                    guaranteed.
                  </p>
                  <button
                    className="text-button"
                    onClick={() => setSection("library")}
                  >
                    Choose a match <ArrowRight size={15} />
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
        {section === "compare" && (
          <Comparison matches={matches} notify={notify} />
        )}
        {!booted && section === "library" && (
          <div className="connection-note">
            <Loader2 className="spin" size={16} />
            Connecting to your local workspace…
          </div>
        )}
      </main>
      <input
        hidden
        ref={importInput}
        type="file"
        accept="video/*,.mkv,.ts"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) importFile(file);
          e.target.value = "";
        }}
      />
      {toast && (
        <div className="toast" role="status">
          <span>{toast}</span>
          <button
            className="icon-button"
            onClick={() => setToast("")}
            aria-label="Dismiss notification"
          >
            <X size={17} />
          </button>
        </div>
      )}

      {modal === "new" && (
        <ModalShell
          title="A new game. A new perspective."
          subtitle="Give your match a home. Your original recording will be preserved locally."
          onClose={close}
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              act(async () => {
                const m = await api<Match>("/matches", "POST", {
                  title: f.get("title"),
                  home: f.get("home"),
                  away: f.get("away"),
                  date: f.get("date"),
                  profile: f.get("profile"),
                });
                close();
                openMatch(m.id);
                const file = f.get("file") as File;
                if (file?.size) await importFile(file, m.id);
              });
            }}
          >
            <label>
              Match title
              <input
                name="title"
                required
                placeholder="Saturday friendly"
                maxLength={150}
              />
            </label>
            <div className="form-row">
              <label>
                Home team
                <input
                  name="home"
                  defaultValue="Home"
                  required
                  maxLength={60}
                />
              </label>
              <label>
                Away team
                <input
                  name="away"
                  defaultValue="Away"
                  required
                  maxLength={60}
                />
              </label>
            </div>
            <div className="form-row">
              <label>
                Match date
                <input
                  name="date"
                  type="date"
                  defaultValue={new Date().toISOString().slice(0, 10)}
                />
              </label>
              <label>
                Recording profile
                <select name="profile">
                  <option value="wide">Wide-view soccer</option>
                  <option value="phone">Stationary phone</option>
                  <option value="broadcast">
                    Broadcast / screen recording
                  </option>
                  <option value="game">Video game (unvalidated)</option>
                </select>
              </label>
            </div>
            <label className="file-drop">
              <Upload size={25} />
              <strong>Choose a recording</strong>
              <span>Optional—you can import or capture later.</span>
              <input name="file" type="file" accept="video/*,.mkv,.ts" />
            </label>
            <div className="modal-actions">
              <button className="button" type="button" onClick={close}>
                Cancel
              </button>
              <button className="button primary" disabled={busy}>
                Create match <ArrowRight size={16} />
              </button>
            </div>
          </form>
        </ModalShell>
      )}

      {modal === "analyze" && detail && (
        <ModalShell
          title="Look closer at your game."
          subtitle="Analysis runs locally. Your original recording is never modified."
          onClose={close}
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              act(async () => {
                await api(`/matches/${selected}/analyze`, "POST", {
                  source_id: sourceId,
                  sample_fps: Number(f.get("fps")),
                  detector: f.get("detector"),
                  experimental_events: f.get("events") === "on",
                  live: recording,
                });
                close();
              }, "Analysis queued");
            }}
          >
            <label>
              Detection engine
              <select
                name="detector"
                defaultValue={
                  detail.match.profile === "synthetic"
                    ? "synthetic"
                    : system?.model_ready
                      ? "yolox"
                      : "hog"
                }
              >
                <option value="yolox" disabled={!system?.model_ready}>
                  YOLOX tiny · pretrained local model
                </option>
                <option value="hog">
                  HOG · limited baseline, no model download
                </option>
                {detail.match.profile === "synthetic" && (
                  <option value="synthetic">
                    Synthetic fixture detector (demo only)
                  </option>
                )}
              </select>
            </label>
            <label>
              Analysis sampling
              <select name="fps" defaultValue="5">
                <option value="2">2 frames / second · lighter</option>
                <option value="5">5 frames / second · balanced</option>
                <option value="10">10 frames / second · more detail</option>
              </select>
            </label>
            <label className="checkbox">
              <input type="checkbox" name="events" />
              Experimental ball-control suggestions
            </label>
            <div className="notice warning">
              <AlertTriangle size={18} />
              <span>
                Player tracking and ball control are unvalidated on your
                footage. Suggestions need review. Automatic goals, shots,
                passes, and saves are not claimed.
              </span>
            </div>
            <div className="modal-actions">
              <button className="button" type="button" onClick={close}>
                Cancel
              </button>
              <button className="button primary" disabled={busy || !sourceId}>
                <ScanLine size={17} />
                Start analysis
              </button>
            </div>
          </form>
        </ModalShell>
      )}

      {modal === "event" && detail && (
        <ModalShell
          title={eventEdit ? "Review this moment." : "Mark a match moment."}
          subtitle="Confirmed events update your statistics. You can always edit or undo."
          onClose={close}
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              act(async () => {
                await correction("event", {
                  id: eventEdit?.id || crypto.randomUUID().replaceAll("-", ""),
                  kind: f.get("kind"),
                  start: Number(f.get("start")),
                  end: f.get("end") ? Number(f.get("end")) : null,
                  team: f.get("team"),
                  player: f.get("player"),
                  status: f.get("status"),
                  note: f.get("note"),
                  origin: eventEdit?.origin || "manual",
                  evidence: eventEdit?.evidence || "",
                  score: eventEdit?.score ?? null,
                  source_id: sourceId || null,
                });
                close();
              }, "Timeline updated");
            }}
          >
            <div className="form-row">
              <label>
                Event
                <select name="kind" defaultValue={eventEdit?.kind || "goal"}>
                  {Object.entries(labels).map(([k, v]) => (
                    <option key={k} value={k}>
                      {v}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Review status
                <select
                  name="status"
                  defaultValue={eventEdit?.status || "confirmed"}
                >
                  <option value="confirmed">Confirmed by me</option>
                  <option value="proposed">Needs review</option>
                  <option value="rejected">Rejected</option>
                </select>
              </label>
            </div>
            <div className="form-row">
              <label>
                Start (video seconds)
                <input
                  name="start"
                  type="number"
                  min="0"
                  max={detail.match.duration}
                  step=".01"
                  required
                  defaultValue={(eventEdit?.start ?? time).toFixed(2)}
                />
              </label>
              <label>
                End (intervals only)
                <input
                  name="end"
                  type="number"
                  min="0"
                  max={detail.match.duration}
                  step=".01"
                  defaultValue={eventEdit?.end ?? ""}
                />
              </label>
            </div>
            <div className="form-row">
              <label>
                Team
                <select name="team" defaultValue={eventEdit?.team || "home"}>
                  <option value="home">{detail.match.home}</option>
                  <option value="away">{detail.match.away}</option>
                  <option value="unknown">Unknown</option>
                </select>
              </label>
              <label>
                Player identity
                <input
                  name="player"
                  maxLength={100}
                  defaultValue={eventEdit?.player || ""}
                  placeholder="Optional, reviewed identity"
                />
              </label>
            </div>
            <label>
              Notes
              <textarea
                name="note"
                rows={3}
                maxLength={2000}
                defaultValue={eventEdit?.note || ""}
              />
            </label>
            {eventEdit?.evidence && (
              <p className="muted">Evidence: {eventEdit.evidence}</p>
            )}
            <div className="modal-actions">
              <button className="button" type="button" onClick={close}>
                Cancel
              </button>
              <button className="button primary" disabled={busy}>
                <Check size={17} />
                Save moment
              </button>
            </div>
          </form>
        </ModalShell>
      )}

      {modal === "clip" && detail && (
        <ModalShell
          title="Keep the moments that matter."
          subtitle="Export from your original recording, with this review revision attached."
          onClose={close}
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              act(async () => {
                await api(`/matches/${selected}/clips`, "POST", {
                  title: f.get("title"),
                  source_id: sourceId,
                  start: Number(f.get("start")),
                  end: Number(f.get("end")),
                  mode: f.get("mode"),
                  team: f.get("team"),
                  player: f.get("player"),
                  pre: 10,
                  post: 5,
                });
                close();
                setTab("exports");
              }, "Export queued");
            }}
          >
            <label>
              Clip title
              <input
                name="title"
                defaultValue="Match highlights"
                required
                maxLength={100}
              />
            </label>
            <label>
              Export type
              <select name="mode">
                <option value="exact">Custom clip · exact boundaries</option>
                <option value="reel">Highlight reel · confirmed events</option>
                <option value="annotated">
                  Custom clip · tracking overlay
                </option>
                <option value="copy">Fast clip · keyframe-aligned</option>
              </select>
            </label>
            <div className="form-row">
              <label>
                Start (seconds)
                <input
                  name="start"
                  type="number"
                  step=".01"
                  min="0"
                  defaultValue={Math.max(0, time - 10).toFixed(2)}
                  required
                />
              </label>
              <label>
                End (seconds)
                <input
                  name="end"
                  type="number"
                  step=".01"
                  min=".01"
                  max={detail.match.duration}
                  defaultValue={Math.min(
                    detail.match.duration,
                    time + 5,
                  ).toFixed(2)}
                  required
                />
              </label>
            </div>
            <div className="form-row">
              <label>
                Reel team
                <select name="team">
                  <option value="all">Both teams</option>
                  <option value="home">{detail.match.home}</option>
                  <option value="away">{detail.match.away}</option>
                </select>
              </label>
              <label>
                Reel player
                <input
                  name="player"
                  placeholder="Optional, exact reviewed name"
                />
              </label>
            </div>
            <p className="muted">
              Reels use 10s before and 5s after confirmed events. Clips spanning
              missing footage are rejected rather than hiding gaps.
            </p>
            <div className="modal-actions">
              <button className="button" type="button" onClick={close}>
                Cancel
              </button>
              <button className="button primary" disabled={busy}>
                <Scissors size={17} />
                Create export
              </button>
            </div>
          </form>
        </ModalShell>
      )}

      {modal === "track" && track && detail && (
        <ModalShell
          title={track.player || `Review track ${track.id.split("-").at(-1)}`}
          subtitle="Link this observed fragment to a team and player. Track IDs alone do not establish identity."
          onClose={close}
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              act(async () => {
                await correction("label", {
                  track_id: track.id,
                  start: Number(f.get("start")),
                  end: Number(f.get("end")),
                  team: f.get("team"),
                  player: f.get("player"),
                  role: f.get("role"),
                  alias: "",
                });
                close();
              }, "Identity assignment updated");
            }}
          >
            <label>
              Player name / jersey
              <input
                name="player"
                defaultValue={track.player}
                placeholder="e.g. Alex · #7"
                maxLength={100}
              />
            </label>
            <div className="form-row">
              <label>
                Team
                <select name="team" defaultValue={track.team}>
                  <option value="unknown">Unknown</option>
                  <option value="home">{detail.match.home}</option>
                  <option value="away">{detail.match.away}</option>
                </select>
              </label>
              <label>
                Role
                <select name="role" defaultValue={track.role}>
                  {["player", "goalkeeper", "official", "ball", "unknown"].map(
                    (v) => (
                      <option key={v}>{v}</option>
                    ),
                  )}
                </select>
              </label>
            </div>
            <div className="form-row">
              <label>
                From (seconds)
                <input
                  name="start"
                  type="number"
                  min="0"
                  step=".01"
                  defaultValue={track.start}
                />
              </label>
              <label>
                Until (seconds)
                <input
                  name="end"
                  type="number"
                  min="0"
                  step=".01"
                  defaultValue={track.end + 1}
                />
              </label>
            </div>
            <div className="modal-actions">
              <button
                className="button"
                type="button"
                onClick={() =>
                  act(async () => {
                    await correction("split", { track_id: track.id, time });
                    close();
                  }, "Track split after the current video time")
                }
              >
                Split at {clock(time)}
              </button>
              <button className="button primary" disabled={busy}>
                Save identity
              </button>
            </div>
          </form>
          <div className="divider" />
          <button
            className="text-button"
            onClick={() => {
              setPointEdit(true);
              setTab("overview");
              close();
              notify(
                "Click the corrected ground-contact position in the video at this analyzed frame.",
              );
            }}
          >
            <Target size={15} />
            Correct position in current frame
          </button>
          <form
            className="merge-form"
            onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              act(async () => {
                await correction("merge", {
                  track_ids: [track.id, f.get("other")],
                  player: f.get("identity"),
                  team: track.team,
                });
                close();
              }, "Non-overlapping fragments linked");
            }}
          >
            <label>
              Link another fragment
              <select name="other" required>
                <option value="">Choose fragment</option>
                {detail.tracks
                  .filter((t) => t.id !== track.id)
                  .map((t) => (
                    <option value={t.id} key={t.id}>
                      {t.player || t.id}
                    </option>
                  ))}
              </select>
            </label>
            <label>
              Shared player identity
              <input name="identity" required defaultValue={track.player} />
            </label>
            <button className="button small">
              <Link2 size={14} />
              Link fragments
            </button>
          </form>
        </ModalShell>
      )}

      {modal === "calibration" && source && (
        <ModalShell
          title="Put the pitch in perspective."
          subtitle="Click the four pitch corners: top-left, top-right, bottom-right, bottom-left. Use only a view with all four known corners visible."
          wide
          onClose={close}
        >
          <div
            className="calibration-image"
            onClick={(e) => {
              if (calibrationPoints.length >= 4) return;
              const r = e.currentTarget.getBoundingClientRect();
              setCalibrationPoints([
                ...calibrationPoints,
                [
                  (e.clientX - r.left) / r.width,
                  (e.clientY - r.top) / r.height,
                ],
              ]);
            }}
          >
            <img src={calibrationImage} alt="Select four known field corners" />
            {calibrationPoints.map(([x, y], i) => (
              <span key={i} style={{ left: x * 100 + "%", top: y * 100 + "%" }}>
                {i + 1}
              </span>
            ))}
          </div>
          <p className="muted">
            {calibrationPoints.length}/4 points selected. Mapping is limited to
            this visible polygon. Assumed field dimensions: 105 × 68 m. Distance
            and speed remain withheld.
          </p>
          <div className="modal-actions">
            <button className="button" onClick={() => setCalibrationPoints([])}>
              Reset points
            </button>
            <button
              className="button primary"
              disabled={calibrationPoints.length !== 4 || busy}
              onClick={() =>
                act(async () => {
                  await correction("calibration", {
                    source_id: source.id,
                    start: time,
                    image: calibrationPoints,
                    field: [
                      [0, 0],
                      [1, 0],
                      [1, 1],
                      [0, 1],
                    ],
                    length: 105,
                    width: 68,
                    dimensions_measured: false,
                  });
                  close();
                }, "Calibration saved for this time onward")
              }
            >
              Save calibration <Check size={16} />
            </button>
          </div>
        </ModalShell>
      )}

      {modal === "capture" && (
        <ModalShell
          title="Bring the game in."
          subtitle="Recording runs independently from analysis. Only committed media is analyzed."
          onClose={close}
        >
          <div className="capture-options">
            <button
              onClick={() =>
                act(async () => {
                  const p = await api<{
                    fragment: string;
                    instructions: string;
                  }>(`/matches/${selected}/pair`, "POST");
                  setPairing(p);
                  setModal("pair");
                })
              }
            >
              <Smartphone size={25} />
              <strong>Phone on your network</strong>
              <span>Pair with the separate HTTPS receiver</span>
              <ArrowRight size={17} />
            </button>
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              act(async () => {
                await api(`/matches/${selected}/capture`, "POST", {
                  kind: f.get("kind"),
                  address: f.get("address"),
                  device: f.get("device"),
                  fps: 30,
                  analyze: f.get("analyze") === "on",
                  detector: system?.model_ready ? "yolox" : "hog",
                });
                close();
              }, "Capture queued. Verify the recording indicator before relying on it.");
            }}
          >
            <label>
              Other capture source
              <select name="kind">
                <option value="stream">Stream URL (RTSP / RTMP / HTTP)</option>
                <option value="screen">macOS screen device</option>
                <option value="camera">macOS camera device</option>
                <option value="test">Synthetic test source</option>
              </select>
            </label>
            <label>
              Stream URL
              <input
                name="address"
                placeholder="rtsp://192.168.1.20:8554/live"
              />
            </label>
            <label>
              AVFoundation device index
              <input name="device" defaultValue="0:none" />
              <small>
                Run “python run.py devices” to find the correct screen/camera
                index.
              </small>
            </label>
            <label className="checkbox">
              <input name="analyze" type="checkbox" />
              Analyze behind the recording
            </label>
            <div className="notice warning">
              <AlertTriangle size={17} />
              Device access requires macOS permission. A disconnected source
              creates a recording gap; the app cannot recover frames it never
              received.
            </div>
            <div className="modal-actions">
              <button className="button" type="button" onClick={close}>
                Cancel
              </button>
              <button className="button primary" disabled={busy || recording}>
                <Radio size={16} />
                Start recording
              </button>
            </div>
          </form>
        </ModalShell>
      )}

      {modal === "pair" && pairing && (
        <ModalShell
          title="Connect your phone."
          subtitle="Use the same local network. The receiver needs HTTPS trusted by your phone."
          onClose={close}
        >
          <p className="muted">Start the phone receiver on this computer:</p>
          <code className="code-block">
            .venv/bin/python run.py receiver --cert cert.pem --key key.pem
          </code>
          <label>
            Pairing URL
            <span className="muted">
              Replace COMPUTER-IP with this computer's LAN address.
            </span>
            <textarea
              readOnly
              rows={4}
              value={`https://COMPUTER-IP:8766/${pairing.fragment}`}
            />
          </label>
          <p>
            Open that address on your phone, grant camera access, and keep the
            page open. Pairing expires in four hours. The main application stays
            on localhost.
          </p>
          <button className="button primary" onClick={close}>
            Done
          </button>
        </ModalShell>
      )}

      {modal === "clock" && detail && (
        <ModalShell
          title="Set the match clock."
          subtitle="Match time is separate from recording time."
          onClose={close}
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              act(async () => {
                await correction("clock", {
                  period: Number(f.get("period")),
                  media_anchor: Number(f.get("media")),
                  match_anchor: Number(f.get("match")),
                });
                close();
              }, "Match clock updated");
            }}
          >
            <label>
              Period
              <input
                name="period"
                type="number"
                min="1"
                max="6"
                defaultValue={detail.review.clock.period}
              />
            </label>
            <div className="form-row">
              <label>
                Video anchor (seconds)
                <input
                  name="media"
                  type="number"
                  min="0"
                  step=".01"
                  defaultValue={time.toFixed(2)}
                />
              </label>
              <label>
                Match time at anchor (seconds)
                <input
                  name="match"
                  type="number"
                  min="0"
                  defaultValue={detail.review.clock.match_anchor}
                />
              </label>
            </div>
            <button className="button primary">Save clock</button>
          </form>
        </ModalShell>
      )}
      {modal === "exclude" && detail && (
        <ModalShell
          title="Exclude an interval."
          subtitle="Replays and non-play footage should not inflate your match statistics."
          onClose={close}
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              act(async () => {
                await correction("exclude", {
                  start: Number(f.get("start")),
                  end: Number(f.get("end")),
                  reason: f.get("reason"),
                });
                close();
              }, "Interval excluded");
            }}
          >
            <div className="form-row">
              <label>
                From (seconds)
                <input
                  name="start"
                  type="number"
                  min="0"
                  step=".01"
                  defaultValue={time.toFixed(2)}
                />
              </label>
              <label>
                Until (seconds)
                <input
                  name="end"
                  type="number"
                  min="0"
                  step=".01"
                  defaultValue={Math.min(
                    detail.match.duration,
                    time + 5,
                  ).toFixed(2)}
                />
              </label>
            </div>
            <label>
              Reason
              <input name="reason" defaultValue="Replay / non-play footage" />
            </label>
            <button className="button primary">Exclude interval</button>
          </form>
        </ModalShell>
      )}
    </div>
  );
}

function MatchCard({ match, onClick }: { match: Match; onClick: () => void }) {
  const [source, setSource] = useState<Source | null>(null);
  useEffect(() => {
    api<Detail>("/matches/" + match.id)
      .then((d) => setSource(d.sources[0] || null))
      .catch(() => {});
  }, [match.id, match.updated]);
  return (
    <button className="match-card" onClick={onClick}>
      <div className="match-poster">
        {source?.poster ? (
          <img
            src={`/api/matches/${match.id}/poster/${source.id}`}
            alt="Recording preview"
          />
        ) : (
          <Pitch />
        )}
        <span className="poster-tag">
          {match.profile === "synthetic" ? "SYNTHETIC DEMO" : "SOCCER"}
        </span>
        <span className="poster-duration">{clock(match.duration)}</span>
        <span className="poster-play">
          <Play size={20} />
        </span>
      </div>
      <div className="match-card-body">
        <div className="card-date">
          {match.date || new Date(match.created * 1000).toLocaleDateString()}
        </div>
        <h3>{match.title}</h3>
        <p>
          {match.home} <span>vs</span> {match.away}
        </p>
        <div className="card-bottom">
          <span>
            <i className="dot" />
            {source ? "Ready to review" : "Awaiting recording"}
          </span>
          <ArrowRight size={17} />
        </div>
      </div>
    </button>
  );
}

function Comparison({
  matches,
  notify,
}: {
  matches: Match[];
  notify: (s: string) => void;
}) {
  const [left, setLeft] = useState(""),
    [right, setRight] = useState(""),
    [data, setData] = useState<Detail[]>([]);
  useEffect(() => {
    if (!left || !right) {
      setData([]);
      return;
    }
    Promise.all([
      api<Detail>("/matches/" + left),
      api<Detail>("/matches/" + right),
    ])
      .then(setData)
      .catch((e) => notify(e.message));
  }, [left, right, notify]);
  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <div className="eyebrow">THE BIGGER PICTURE</div>
          <h1>
            A game is part of a story<span>.</span>
          </h1>
          <p>
            Compare reviewed results, with coverage and source differences kept
            in view.
          </p>
        </div>
      </div>
      <div className="compare-select">
        <label>
          First match
          <select value={left} onChange={(e) => setLeft(e.target.value)}>
            <option value="">Choose a match</option>
            {matches.map((m) => (
              <option value={m.id} key={m.id}>
                {m.title}
              </option>
            ))}
          </select>
        </label>
        <Layers size={24} />
        <label>
          Second match
          <select value={right} onChange={(e) => setRight(e.target.value)}>
            <option value="">Choose a match</option>
            {matches.map((m) => (
              <option value={m.id} key={m.id}>
                {m.title}
              </option>
            ))}
          </select>
        </label>
      </div>
      {data.length === 2 ? (
        <>
          <div className="notice">
            <AlertTriangle size={17} />
            {data[0].match.profile !== data[1].match.profile
              ? "Different capture profiles: statistics are not directly comparable."
              : "Counts cover confirmed events only; review completeness and footage coverage may differ."}
          </div>
          <div className="panel">
            <table>
              <thead>
                <tr>
                  <th>Reviewed measure</th>
                  {data.map((d) => (
                    <th key={d.match.id}>{d.match.title}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[
                  "Coverage",
                  "Confirmed events",
                  "Goals",
                  "Shots",
                  "Passes",
                  "Saves",
                ].map((metric) => (
                  <tr key={metric}>
                    <th>{metric}</th>
                    {data.map((d) => (
                      <td key={d.match.id}>
                        {metric === "Coverage"
                          ? d.statistics.coverage_percent + "%"
                          : metric === "Confirmed events"
                            ? d.statistics.confirmed_events
                            : ["home", "away"]
                                .map(
                                  (t) =>
                                    d.statistics.counts[t as Team][
                                      {
                                        Goals: "goal",
                                        Shots: "shot",
                                        Passes: "pass",
                                        Saves: "save",
                                      }[metric] || ""
                                    ] || 0,
                                )
                                .join(" — ")}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : (
        <div className="panel comparison-empty">
          <Layers size={35} />
          <h3>Two matches. More context.</h3>
          <p>
            Select two matches to inspect their confirmed events and analysis
            coverage side by side.
          </p>
        </div>
      )}
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
