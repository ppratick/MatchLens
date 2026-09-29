import {
  ArrowLeft,
  ChevronDown,
  ChevronRight,
  Flag,
  Grid2X2,
  Layers,
  Loader2,
  Radio,
  ScanLine,
  Settings2,
  ShieldCheck,
  Trash2,
  Undo2,
  Redo2,
  X,
  AlertTriangle,
  Scissors,
} from "lucide-react";
import { api, bytes, clock } from "./api";
import type { Match } from "./types";
import { Comparison } from "./features/library/Comparison";
import { VideoPlayer } from "./features/video/VideoPlayer";
import { FieldPreview } from "./features/field/FieldPreview";
import { Statistics } from "./features/statistics/Statistics";
import { Library } from "./features/library/Library";
import { Setup } from "./features/setup/Setup";
import { Players } from "./features/players/Players";
import { PlayerSummaries } from "./features/players/PlayerSummaries";
import { FieldAnalysis } from "./features/field/FieldAnalysis";
import { Exports } from "./features/exports/Exports";
import { NewDialog } from "./features/library/NewDialog";
import { AnalyzeDialog } from "./features/capture/AnalyzeDialog";
import { EventDialog } from "./features/timeline/EventDialog";
import { ClipDialog } from "./features/exports/ClipDialog";
import { TrackDialog } from "./features/players/TrackDialog";
import { CalibrationDialog } from "./features/field/CalibrationDialog";
import { CaptureDialog } from "./features/capture/CaptureDialog";
import { PairDialog } from "./features/capture/PairDialog";
import { ClockDialog } from "./features/timeline/ClockDialog";
import { ExcludeDialog } from "./features/timeline/ExcludeDialog";
import { useWorkspace } from "./hooks/useWorkspace";
import { AnnotationDialog } from "./features/players/AnnotationDialog";

export function App() {
  const workspace = useWorkspace();
  const {
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
  } = workspace;
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
        <Library {...workspace} />

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
                    <VideoPlayer {...workspace} />
                    <div className="video-footer">
                      <span>
                        <ShieldCheck size={14} />
                        Original footage stays unchanged
                      </span>
                      <span>SPACE play / pause · ← → seek · E add event</span>
                    </div>
                    <FieldPreview {...workspace} />
                  </div>
                  <Statistics {...workspace} />
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
              <PlayerSummaries {...workspace} />
              <Players {...workspace} />
              <FieldAnalysis {...workspace} />
              <Exports {...workspace} />
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
        <Setup {...workspace} />
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

      {workspace.screenCapture.preview && modal !== "capture" && (
        <div className="toast" role="status">
          <span>
            Screen recording {workspace.screenCapture.state} · keep this tab
            open
          </span>
          <button
            className="button small"
            onClick={workspace.screenCapture.finish}
          >
            Finish screen recording
          </button>
        </div>
      )}
      <AnnotationDialog {...workspace} />
      <NewDialog {...workspace} />

      <AnalyzeDialog {...workspace} />

      <EventDialog {...workspace} />

      <ClipDialog {...workspace} />

      <TrackDialog {...workspace} />

      <CalibrationDialog {...workspace} />

      <CaptureDialog {...workspace} />

      <PairDialog {...workspace} />

      <ClockDialog {...workspace} />
      <ExcludeDialog {...workspace} />
    </div>
  );
}
