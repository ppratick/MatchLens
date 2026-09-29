import { ArrowRight, AlertTriangle } from "lucide-react";
import { Pitch } from "../../features/field/Pitch";
import type { Workspace } from "../../hooks/useWorkspace";
export function FieldAnalysis(
  workspace: Pick<
    Workspace,
    | "tab"
    | "viewHeat"
    | "setViewHeat"
    | "detail"
    | "trackId"
    | "setTrackId"
    | "setTab"
  >,
) {
  const { tab, viewHeat, setViewHeat, detail, trackId, setTrackId, setTab } =
    workspace;
  if (!detail) return null;
  return (
    <>
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
              Only observed, calibrated positions are shown. Heat is sampled
              occupancy; it is not exact distance, speed, or full-field
              coverage.
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
            <button className="button" onClick={() => setTab("overview")}>
              Open video calibration <ArrowRight size={15} />
            </button>
            <div className="notice warning">
              <AlertTriangle size={17} />
              Recalibrate after camera movement. A ground-plane transform cannot
              locate an airborne ball.
            </div>
          </div>
        </div>
      )}
    </>
  );
}
