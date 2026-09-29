import { useEffect, useRef } from "react";
import type { Workspace } from "../../hooks/useWorkspace";

export function ScreenCapturePanel({
  screenCapture,
  recording,
}: Pick<Workspace, "screenCapture" | "recording">) {
  const preview = useRef<HTMLVideoElement>(null);
  useEffect(() => {
    if (preview.current) preview.current.srcObject = screenCapture.preview;
  }, [screenCapture.preview]);
  return (
    <div className="panel-description">
      <h3>Record a Mac display, window, or browser tab</h3>
      <p>
        The browser opens a visible source picker. Screen/audio permission is
        yours to grant. Keep this MatchLens tab open while recording. Audio is
        included only when the selected source and browser provide it.
      </p>
      {screenCapture.preview && (
        <>
          <video
            ref={preview}
            muted
            autoPlay
            playsInline
            style={{ width: "100%", maxHeight: 240 }}
            aria-label="Incoming screen preview"
          />
          <p>
            Incoming preview · no analysis overlay ·{" "}
            {screenCapture.audio
              ? "audio track available"
              : "no audio track supplied"}
          </p>
        </>
      )}
      <p role="status">
        {screenCapture.state}: {screenCapture.message}
      </p>
      <div className="button-group">
        <button
          className="button primary"
          disabled={
            recording ||
            ["recording", "paused", "retrying", "draining", "blocked"].includes(
              screenCapture.state,
            )
          }
          onClick={() => void screenCapture.start()}
        >
          Choose screen or window
        </button>
        <button
          className="button"
          disabled={!screenCapture.preview}
          onClick={screenCapture.finish}
        >
          Finish screen recording
        </button>
        {screenCapture.state === "blocked" && (
          <button className="button" onClick={screenCapture.downloadBuffer}>
            Preserve unsent recording bytes
          </button>
        )}
      </div>
    </div>
  );
}
