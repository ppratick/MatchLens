import { Scissors } from "lucide-react";
import { api } from "../../api";
import { ModalShell } from "../../shared/ModalShell";
import type { Workspace } from "../../hooks/useWorkspace";
export function ClipDialog(
  workspace: Pick<
    Workspace,
    | "modal"
    | "detail"
    | "close"
    | "act"
    | "selected"
    | "sourceId"
    | "setTab"
    | "time"
    | "busy"
  >,
) {
  const { modal, detail, close, act, selected, sourceId, setTab, time, busy } =
    workspace;
  if (!detail) return null;
  return (
    <>
      {modal === "clip" && detail && (
        <ModalShell
          title="Keep the moments that matter."
          subtitle="Export from your original recording, with this review revision attached."
          onClose={close}
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              act(async () => {
                await api(`/matches/${selected}/clips`, "POST", {
                  title: f.get("title"),
                  source_id: sourceId,
                  start: Number(f.get("start")),
                  end: Number(f.get("end")),
                  mode: f.get("mode"),
                  team: f.get("team"),
                  player: f.get("player"),
                  pre: 10,
                  post: 5,
                });
                close();
                setTab("exports");
              }, "Export queued");
            }}
          >
            <label>
              Clip title
              <input
                name="title"
                defaultValue="Match highlights"
                required
                maxLength={100}
              />
            </label>
            <label>
              Export type
              <select name="mode">
                <option value="exact">Custom clip · exact boundaries</option>
                <option value="reel">Highlight reel · confirmed events</option>
                <option value="annotated">
                  Custom clip · tracking overlay
                </option>
                <option value="copy">Fast clip · keyframe-aligned</option>
              </select>
            </label>
            <div className="form-row">
              <label>
                Start (seconds)
                <input
                  name="start"
                  type="number"
                  step=".01"
                  min="0"
                  defaultValue={Math.max(0, time - 10).toFixed(2)}
                  required
                />
              </label>
              <label>
                End (seconds)
                <input
                  name="end"
                  type="number"
                  step=".01"
                  min=".01"
                  max={detail.match.duration}
                  defaultValue={Math.min(
                    detail.match.duration,
                    time + 5,
                  ).toFixed(2)}
                  required
                />
              </label>
            </div>
            <div className="form-row">
              <label>
                Reel team
                <select name="team">
                  <option value="all">Both teams</option>
                  <option value="home">{detail.match.home}</option>
                  <option value="away">{detail.match.away}</option>
                </select>
              </label>
              <label>
                Reel player
                <input
                  name="player"
                  placeholder="Optional, exact reviewed name"
                />
              </label>
            </div>
            <p className="muted">
              Reels use 10s before and 5s after confirmed events. Clips spanning
              missing footage are rejected rather than hiding gaps.
            </p>
            <div className="modal-actions">
              <button className="button" type="button" onClick={close}>
                Cancel
              </button>
              <button className="button primary" disabled={busy}>
                <Scissors size={17} />
                Create export
              </button>
            </div>
          </form>
        </ModalShell>
      )}
    </>
  );
}
