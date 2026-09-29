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
              : "Click the four pitch corners: top-left, top-right, bottom-right, bottom-left. Use only a view with all four known corners visible."
          }
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
            <img
              src={calibrationImage}
              alt={
                modal === "television"
                  ? "Select television picture corners"
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
            {calibrationPoints.length}/4 points selected. Mapping is limited to
            {modal === "television"
              ? " the rectified screen. A 16:9 output is assumed. Original footage stays unchanged; start a new analysis run after saving. Reflections, flicker, moire, exposure changes and people blocking the screen can still hide evidence."
              : " this visible polygon. Assumed field dimensions: 105 × 68 m. Distance and speed remain withheld."}
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
    </>
  );
}
