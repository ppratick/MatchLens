import {
  Film,
  Map,
  Pause,
  Play,
  ScanLine,
  Upload,
  Video,
  Scissors,
} from "lucide-react";
import { api, clock } from "../../api";
import { teamColor } from "../../shared/constants";
import { labels } from "../../shared/constants";
import type { Workspace } from "../../hooks/useWorkspace";
export function VideoPlayer(
  workspace: Pick<
    Workspace,
    | "detail"
    | "sourceId"
    | "setSourceId"
    | "setSegmentId"
    | "setFrame"
    | "importInput"
    | "source"
    | "act"
    | "selected"
    | "recording"
    | "liveMode"
    | "setLiveMode"
    | "latestAnalysis"
    | "pointEdit"
    | "videoRatio"
    | "trackId"
    | "currentFrame"
    | "correction"
    | "time"
    | "setPointEdit"
    | "mediaUrl"
    | "video"
    | "updateTime"
    | "setPlaying"
    | "segment"
    | "resumePlayback"
    | "pendingSeek"
    | "notify"
    | "setVideoRatio"
    | "overlay"
    | "setTrackId"
    | "setModal"
    | "playing"
    | "setOverlay"
    | "calibrate"
    | "mediaOffset"
    | "seek"
  >,
) {
  const {
    detail,
    sourceId,
    setSourceId,
    setSegmentId,
    setFrame,
    importInput,
    source,
    act,
    selected,
    recording,
    liveMode,
    setLiveMode,
    latestAnalysis,
    pointEdit,
    videoRatio,
    trackId,
    currentFrame,
    correction,
    time,
    setPointEdit,
    mediaUrl,
    video,
    updateTime,
    setPlaying,
    segment,
    resumePlayback,
    pendingSeek,
    notify,
    setVideoRatio,
    overlay,
    setTrackId,
    setModal,
    playing,
    setOverlay,
    calibrate,
    mediaOffset,
    seek,
  } = workspace;
  if (!detail) return null;
  return (
    <>
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
            <summary>Source alignment & analysis versions</summary>
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
                        {j.id.slice(0, 8)} ·{" "}
                        {j.config.live ? "live" : "offline"} · {j.status} ·{" "}
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
              <button
                className="button small"
                onClick={() => {
                  if (calibrate()) setModal("television");
                }}
              >
                Set television corners
              </button>
              <small>
                Changing analysis versions can orphan corrections tied to old
                track IDs. They remain stored with their original IDs.
              </small>
            </div>
          </details>
        )}
        {recording && (
          <div className="live-controls">
            <div className="segmented">
              {(["feed", "analysis", "review"] as const).map((mode) => (
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
              ))}
            </div>
            <small>
              {latestAnalysis?.metrics?.analysis_delay !== undefined
                ? `${latestAnalysis.metrics.analysis_delay?.toFixed(1)} s behind saved video`
                : "Waiting for analysis"}{" "}
              · recording continues
            </small>
          </div>
        )}
        <div
          className={"video-stage " + (pointEdit ? "point-edit" : "")}
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
                    (s) => s.start >= segment.end - 0.1 && s.id !== segment.id,
                  );
                  if (!next) return;
                  const contiguous = next.start - segment.end < 0.15;
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
                      video.current.videoWidth / video.current.videoHeight ||
                        16 / 9,
                    );
                    if (pendingSeek.current !== null) {
                      video.current.currentTime = pendingSeek.current;
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
              {overlay && currentFrame && !currentFrame.excluded && (
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
                        {t.player || t.display_id.split("-").at(-1)}
                      </text>
                    </g>
                  ))}
                </svg>
              )}
              <div className="video-badges">
                <span>
                  <i className={"dot " + (recording ? "record-dot" : "")} />
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
        {recording && (
          <div className="panel-description">
            Buffered recording timestamp: {time.toFixed(2)} s · delayed analysis
            timestamp:{" "}
            {latestAnalysis?.checkpoint?.time?.toFixed(2) ??
              "not yet available"}{" "}
            s · analysis {latestAnalysis?.status ?? "off"} · sampling{" "}
            {latestAnalysis?.metrics?.sample_fps ?? "—"} fps · committed{" "}
            {(source?.bytes ?? 0) / 1000000} MB ·{" "}
            {source?.has_audio ? "audio recorded" : "audio not confirmed"}.
            Incoming preview and buffered feed have no analysis overlay.
          </div>
        )}
        <div className="video-controls">
          <button
            className="button small"
            disabled={!source || source.status === "recording"}
            onClick={() => {
              video.current?.pause();
              setModal("annotate");
            }}
          >
            Label frame
          </button>
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
            {clock(time)} <span>/ {clock(detail.match.duration)}</span>
          </span>
          <div className="spacer" />
          <button
            className={"toggle-button " + (overlay ? "selected" : "")}
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
                  e.start <= (segment?.end || detail.match.duration),
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
    </>
  );
}
