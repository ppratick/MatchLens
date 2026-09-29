import { ArrowRight, Radio, AlertTriangle, Smartphone } from "lucide-react";
import { api } from "../../api";
import { ModalShell } from "../../shared/ModalShell";
import type { Workspace } from "../../hooks/useWorkspace";
export function CaptureDialog(
  workspace: Pick<
    Workspace,
    | "modal"
    | "close"
    | "act"
    | "selected"
    | "setPairing"
    | "setModal"
    | "system"
    | "busy"
    | "recording"
  >,
) {
  const {
    modal,
    close,
    act,
    selected,
    setPairing,
    setModal,
    system,
    busy,
    recording,
  } = workspace;

  return (
    <>
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
    </>
  );
}
