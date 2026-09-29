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
  } = workspace;

  return (
    <>
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
    </>
  );
}
