import { useEffect, useState } from "react";
import { api } from "../../api";
import { Check } from "lucide-react";
import { ModalShell } from "../../shared/ModalShell";
import type { Workspace } from "../../hooks/useWorkspace";
export function CalibrationDialog(
  workspace: Pick<
    Workspace,
    | "modal"
    | "source"
    | "close"
    | "calibrationPoints"
    | "setCalibrationPoints"
    | "calibrationImage"
    | "busy"
    | "act"
    | "correction"
    | "time"
    | "detail"
    | "selected"
  >,
) {
  const {
    modal,
    source,
    close,
    calibrationPoints,
    setCalibrationPoints,
    calibrationImage,
    busy,
    act,
    correction,
    time,
    detail,
    selected,
  } = workspace;

  const [landmarks, setLandmarks] = useState(false);
  const [targets, setTargets] = useState<number[][]>([]);
  const [targetX, setTargetX] = useState(0),
    [targetY, setTargetY] = useState(0);
  const [end, setEnd] = useState(0);
  useEffect(() => {
    if (modal !== "calibration" && modal !== "television") return;
    setLandmarks(false);
    setTargets([]);
    setEnd(
      Math.min(
        time + 1,
        (source?.offset || 0) + (source?.duration || time + 1),
      ),
    );
  }, [modal]);
  return (
    <>
      {(modal === "calibration" || modal === "television") && source && (
        <ModalShell
          title={
            modal === "television"
              ? "Align the television screen."
              : "Put the pitch in perspective."
          }
          subtitle={
            modal === "television"
              ? "Mark the picture area: top-left, top-right, bottom-right, bottom-left. Exclude the bezel. Use landscape, center the mount, reduce glare, and keep static surroundings visible for movement checks."
              : landmarks
                ? "Pair at least four visible landmarks with their known field coordinates; spread points across the visible area."
                : "Click the four pitch corners: top-left, top-right, bottom-right, bottom-left. Use only a view with all four known corners visible."
          }
          wide
          onClose={close}
        >
          {modal === "calibration" && (
            <>
              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={landmarks}
                  onChange={(e) => {
                    setLandmarks(e.target.checked);
                    setTargets([]);
                    setCalibrationPoints([]);
                  }}
                />{" "}
                Use paired landmarks for a partial field
              </label>
              {landmarks && (
                <div className="form-row">
                  <label>
                    Next landmark field X · 0–1
                    <input
                      type="number"
                      min="0"
                      max="1"
                      step=".001"
                      value={targetX}
                      onChange={(e) => setTargetX(Number(e.target.value))}
                    />
                  </label>
                  <label>
                    Next landmark field Y · 0–1
                    <input
                      type="number"
                      min="0"
                      max="1"
                      step=".001"
                      value={targetY}
                      onChange={(e) => setTargetY(Number(e.target.value))}
                    />
                  </label>
                </div>
              )}
              {landmarks && (
                <p className="muted">
                  Choose the known normalized field coordinate, then click its
                  visible image point. Field X spans goal line to goal line; Y
                  spans touchline to touchline. Use at least four spread-out
                  noncollinear points. Center is (0.5, 0.5); touchline/halfway
                  intersections are (0.5, 0) and (0.5, 1). Never invent unseen
                  landmarks.
                </p>
              )}
              <label>
                Calibration valid until · video seconds
                <input
                  type="number"
                  min={time + 0.001}
                  max={(source.offset || 0) + source.duration}
                  step=".001"
                  value={end}
                  onChange={(e) => setEnd(Number(e.target.value))}
                />
              </label>
              <p className="muted">
                Starts at {time.toFixed(3)} s. Default is a one-second interval;
                extend only through a verified stationary shot. Recalibrate
                after pan, zoom, cut, or movement. Fit error is not measured
                spatial accuracy.
              </p>
            </>
          )}
          <div
            className="calibration-image"
            onClick={(e) => {
              if (
                calibrationPoints.length >=
                (landmarks && modal === "calibration" ? 30 : 4)
              )
                return;
              if (landmarks && modal === "calibration")
                setTargets([...targets, [targetX, targetY]]);
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
            <img
              src={calibrationImage}
              alt={
                modal === "television"
                  ? "Select television picture corners"
                  : landmarks
                    ? "Select visible field landmarks"
                    : "Select four known field corners"
              }
            />
            {calibrationPoints.map(([x, y], i) => (
              <span key={i} style={{ left: x * 100 + "%", top: y * 100 + "%" }}>
                {i + 1}
              </span>
            ))}
          </div>
          <p className="muted">
            {calibrationPoints.length}/
            {landmarks && modal === "calibration" ? "30 maximum" : "4"} points
            selected. Mapping is limited to
            {modal === "television"
              ? " the rectified screen. A 16:9 output is assumed. Original footage stays unchanged; start a new analysis run after saving. Reflections, flicker, moire, exposure changes and people blocking the screen can still hide evidence."
              : " this visible polygon. Assumed field dimensions: 105 × 68 m. Distance and speed remain withheld."}
          </p>
          <div className="modal-actions">
            {landmarks && modal === "calibration" && (
              <p className="muted">
                Paired field points:{" "}
                {targets
                  .map(([x, y], i) => `${i + 1}: (${x}, ${y})`)
                  .join(" · ")}
              </p>
            )}
            <button
              className="button"
              onClick={() => {
                setCalibrationPoints([]);
                setTargets([]);
              }}
            >
              Reset points
            </button>
            <button
              className="button primary"
              disabled={
                (landmarks && modal === "calibration"
                  ? calibrationPoints.length < 4
                  : calibrationPoints.length !== 4) ||
                busy ||
                (modal === "calibration" && end <= time)
              }
              onClick={() =>
                act(async () => {
                  if (modal === "television") {
                    await api(
                      `/matches/${selected}/sources/${source.id}/television`,
                      "POST",
                      {
                        revision: detail?.match.revision,
                        reference_image: calibrationImage,
                        calibration: {
                          corners: calibrationPoints,
                          start: time,
                          width: 1280,
                          height: 720,
                        },
                      },
                    );
                    close();
                    return;
                  }
                  await correction("calibration", {
                    source_id: source.id,
                    start: time,
                    end,
                    image: calibrationPoints,
                    field: landmarks
                      ? targets
                      : [
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
                }, "Calibration saved with its reviewed validity interval")
              }
            >
              Save calibration <Check size={16} />
            </button>
          </div>
        </ModalShell>
      )}
    </>
  );
}
