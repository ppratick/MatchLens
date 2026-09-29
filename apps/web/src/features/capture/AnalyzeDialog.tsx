import { ScanLine, AlertTriangle } from "lucide-react";
import { api } from "../../api";
import { ModalShell } from "../../shared/ModalShell";
import type { Workspace } from "../../hooks/useWorkspace";
export function AnalyzeDialog(
  workspace: Pick<
    Workspace,
    | "modal"
    | "detail"
    | "close"
    | "act"
    | "selected"
    | "sourceId"
    | "recording"
    | "system"
    | "busy"
  >,
) {
  const {
    modal,
    detail,
    close,
    act,
    selected,
    sourceId,
    recording,
    system,
    busy,
  } = workspace;
  if (!detail) return null;
  return (
    <>
      {modal === "analyze" && detail && (
        <ModalShell
          title="Look closer at your game."
          subtitle="Analysis runs locally. Your original recording is never modified. Select a completed new version explicitly in Source alignment & analysis versions."
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
                  provider: f.get("provider"),
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
                <option value="yolox_s" disabled={!system?.small_model_ready}>
                  YOLOX Small · local, unvalidated
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
              Execution provider
              <select name="provider" defaultValue="cpu">
                <option value="cpu">CPU · default</option>
                <option
                  value="coreml"
                  disabled={
                    !system?.providers.includes("CoreMLExecutionProvider")
                  }
                >
                  CoreML · experimental, ONNX only
                </option>
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
    </>
  );
}
