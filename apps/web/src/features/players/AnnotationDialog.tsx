import { useEffect, useState, useRef } from "react";
import { api } from "../../api";
import type { Team } from "../../types";
import { ModalShell } from "../../shared/ModalShell";
import type { Workspace } from "../../hooks/useWorkspace";

type ObjectLabel = {
  id: string;
  kind: "person" | "ball";
  box: number[];
  team: Team;
  player: string;
  track_id?: string | null;
};
type FrameLabel = {
  time: number;
  sample_interval: number;
  observable: boolean;
  objects: ObjectLabel[];
};
type Bundle = {
  schema_version: string;
  source_sha256: string;
  source_profile: string;
  source_offset: number;
  revision: number;
  frames: FrameLabel[];
  intervals: { start: number; end: number; kind: string; note: string }[];
  events: unknown[];
};

export function AnnotationDialog({
  modal,
  close,
  detail,
  selected,
  source,
  time,
  video,
  currentFrame,
  mediaOffset,
  act,
  refresh,
  notify,
}: Pick<
  Workspace,
  | "modal"
  | "close"
  | "detail"
  | "selected"
  | "source"
  | "time"
  | "video"
  | "currentFrame"
  | "mediaOffset"
  | "act"
  | "refresh"
  | "notify"
>) {
  const [bundle, setBundle] = useState<Bundle | null>(null);
  const [image, setImage] = useState("");
  const [objects, setObjects] = useState<ObjectLabel[]>([]);
  const [observable, setObservable] = useState(true);
  const [kind, setKind] = useState<"person" | "ball">("person");
  const [selectedObject, setSelectedObject] = useState<number | null>(null);
  const [labelTime, setLabelTime] = useState(0);
  const drag = useRef<number[] | null>(null);
  useEffect(() => {
    if (
      modal !== "annotate" ||
      !selected ||
      !source ||
      !video.current?.videoWidth
    )
      return;
    const player = video.current;
    player.pause();
    const t = currentFrame?.time ?? time;
    setLabelTime(t);
    // Draw only after playback reaches the exact timestamp being labeled.
    const snapshot = () => {
      const canvas = document.createElement("canvas");
      canvas.width = player.videoWidth;
      canvas.height = player.videoHeight;
      canvas.getContext("2d")?.drawImage(player, 0, 0);
      setImage(canvas.toDataURL());
    };
    if (Math.abs(player.currentTime + mediaOffset - t) > 0.001) {
      player.addEventListener("seeked", snapshot, { once: true });
      player.currentTime = Math.max(0, t - mediaOffset);
    } else snapshot();
    api<Bundle>(`/matches/${selected}/sources/${source.id}/annotations`)
      .then((b) => {
        setBundle(b);
        const saved = b.frames.find((f) => Math.abs(f.time - t) < 0.001);
        setObjects(saved?.objects ?? []);
        setObservable(saved?.observable ?? true);
      })
      .catch((e) => notify(e.message));
    return () => player.removeEventListener("seeked", snapshot);
  }, [modal, source?.id]);
  if (modal !== "annotate" || !detail || !source) return null;
  const path = `/matches/${selected}/sources/${source.id}/annotations`;
  const withFrame = (): Bundle => ({
    ...bundle!,
    frames: [
      ...bundle!.frames.filter((f) => Math.abs(f.time - labelTime) >= 0.001),
      {
        time: labelTime,
        sample_interval: currentFrame?.sample_interval ?? 0.2,
        observable,
        objects: observable ? objects : [],
      },
    ].sort((a, b) => a.time - b.time),
  });
  const download = () => {
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(withFrame(), null, 2)], {
        type: "application/json",
      }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = `annotations-${source.id}-r${detail.match.revision}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };
  return (
    <ModalShell
      title="Label the evidence."
      subtitle={`Frame ${labelTime.toFixed(3)} s · original-image coordinates. Draw boxes, keep unknowns, and use the same identity across visible frames.`}
      wide
      onClose={close}
    >
      <p className="muted">
        Stop playback at the frame you want to label. Ball mode accepts a click
        for a small box. Full-frame labels replace detector observations at this
        sample; label every visible object. Change an object ID to link it
        across nearby labeled frames.
      </p>
      <div className="button-group">
        <label>
          Drawing tool
          <select
            value={kind}
            onChange={(e) => setKind(e.target.value as typeof kind)}
          >
            <option value="person">Player box · drag</option>
            <option value="ball">Ball position · click or drag</option>
          </select>
        </label>
        <label className="checkbox">
          <input
            type="checkbox"
            checked={observable}
            onChange={(e) => setObservable(e.target.checked)}
          />
          Observable frame
        </label>
      </div>
      <div
        className="calibration-image"
        onPointerDown={(e) => {
          e.currentTarget.setPointerCapture(e.pointerId);
          const r = e.currentTarget.getBoundingClientRect();
          drag.current = [
            (e.clientX - r.left) / r.width,
            (e.clientY - r.top) / r.height,
          ];
        }}
        onPointerUp={(e) => {
          const a = drag.current;
          if (!a || !observable) return;
          drag.current = null;
          const r = e.currentTarget.getBoundingClientRect();
          const b = [
            (e.clientX - r.left) / r.width,
            (e.clientY - r.top) / r.height,
          ];
          let box = [
            Math.min(a[0], b[0]),
            Math.min(a[1], b[1]),
            Math.max(a[0], b[0]),
            Math.max(a[1], b[1]),
          ];
          if (kind === "ball" && box[2] - box[0] < 0.005)
            box = [a[0] - 0.008, a[1] - 0.012, a[0] + 0.008, a[1] + 0.012];
          box = box.map((v) => Math.min(1, Math.max(0, v)));
          if (box[2] - box[0] < 0.001 || box[3] - box[1] < 0.001) return;
          setObjects([
            ...objects,
            {
              id: crypto.randomUUID().slice(0, 8),
              kind,
              box,
              team: "unknown",
              player: "",
            },
          ]);
          setSelectedObject(objects.length);
        }}
      >
        <img
          src={image}
          alt="Original frame for annotation"
          draggable={false}
        />
        <svg
          className="video-overlay"
          viewBox="0 0 1000 1000"
          preserveAspectRatio="none"
        >
          {objects.map((o, i) => (
            <g key={o.id}>
              <rect
                x={o.box[0] * 1000}
                y={o.box[1] * 1000}
                width={(o.box[2] - o.box[0]) * 1000}
                height={(o.box[3] - o.box[1]) * 1000}
                stroke={i === selectedObject ? "#d6f08c" : "#7aabfa"}
                strokeWidth="3"
                fill="transparent"
              />
              <text
                x={o.box[0] * 1000}
                y={o.box[1] * 1000 - 5}
                fontSize="20"
                fill="#d6f08c"
              >
                {o.id}
              </text>
            </g>
          ))}
        </svg>
      </div>
      <div className="button-group">
        <button
          className="button small"
          disabled={!currentFrame}
          onClick={() => {
            setObjects(
              (currentFrame?.tracks ?? []).map((t) => ({
                id: t.id,
                track_id: t.id,
                kind: t.kind as "person" | "ball",
                box: t.box,
                team: t.team,
                player: t.player,
              })),
            );
          }}
        >
          Use current boxes for manual review
        </button>
        <button className="button small" onClick={() => setObjects([])}>
          Clear frame labels
        </button>
      </div>
      {objects.map((o, i) => (
        <div className="form-row" key={i} onFocus={() => setSelectedObject(i)}>
          <label>
            Object identity
            <input
              value={o.id}
              onChange={(e) =>
                setObjects(
                  objects.map((v, j) =>
                    j === i ? { ...v, id: e.target.value } : v,
                  ),
                )
              }
            />
          </label>
          <label>
            Team
            <select
              value={o.team}
              onChange={(e) =>
                setObjects(
                  objects.map((v, j) =>
                    j === i ? { ...v, team: e.target.value as Team } : v,
                  ),
                )
              }
            >
              <option value="unknown">Unknown</option>
              <option value="home">{detail.match.home}</option>
              <option value="away">{detail.match.away}</option>
            </select>
          </label>
          <label>
            Reviewed name
            <input
              value={o.player}
              onChange={(e) =>
                setObjects(
                  objects.map((v, j) =>
                    j === i ? { ...v, player: e.target.value } : v,
                  ),
                )
              }
            />
          </label>
          <button
            className="text-button"
            onClick={() => setObjects(objects.filter((_, j) => i !== j))}
          >
            Remove
          </button>
        </div>
      ))}
      <details>
        <summary>Camera cuts, replay, non-play, and unknown intervals</summary>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!bundle) return;
            const f = new FormData(e.currentTarget);
            setBundle({
              ...bundle,
              intervals: [
                ...bundle.intervals,
                {
                  start: Number(f.get("start")),
                  end: Number(f.get("end")),
                  kind: String(f.get("kind")),
                  note: String(f.get("note")),
                },
              ],
            });
            e.currentTarget.reset();
          }}
        >
          <div className="form-row">
            <label>
              Start
              <input
                name="start"
                type="number"
                min="0"
                step=".001"
                required
                defaultValue={labelTime}
              />
            </label>
            <label>
              End
              <input
                name="end"
                type="number"
                min="0"
                step=".001"
                required
                defaultValue={labelTime + 1}
              />
            </label>
            <label>
              Interval
              <select name="kind">
                {[
                  "camera_cut",
                  "replay",
                  "closeup",
                  "non_play",
                  "unknown",
                  "contested",
                ].map((k) => (
                  <option key={k}>{k}</option>
                ))}
              </select>
            </label>
          </div>
          <label>
            Evidence note
            <input name="note" />
          </label>
          <button className="button small">Add interval to labels</button>
        </form>
        {bundle?.intervals.map((i, n) => (
          <p key={n}>
            {i.start}–{i.end} s · {i.kind}{" "}
            <button
              className="text-button"
              onClick={() =>
                setBundle({
                  ...bundle,
                  intervals: bundle.intervals.filter((_, j) => n !== j),
                })
              }
            >
              Remove
            </button>
          </p>
        ))}
      </details>
      <div className="modal-actions">
        <label>
          Import labels
          <input
            type="file"
            accept=".json"
            disabled={!bundle}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f)
                act(async () => {
                  await api(
                    path + `?revision=${detail.match.revision}`,
                    "POST",
                    JSON.parse(await f.text()),
                  );
                  await refresh();
                  close();
                }, "Annotations imported as a new reversible review revision");
            }}
          />
        </label>
        <button className="button" disabled={!bundle} onClick={download}>
          Export labels
        </button>
        <button
          className="button primary"
          disabled={!bundle}
          onClick={() =>
            act(async () => {
              await api(
                path + `?revision=${detail.match.revision}`,
                "POST",
                withFrame(),
              );
              await refresh();
              close();
            }, "Labels saved. Undo restores the previous revision.")
          }
        >
          Save frame labels
        </button>
      </div>
    </ModalShell>
  );
}
