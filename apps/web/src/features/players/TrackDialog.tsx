import { Target, Link2 } from "lucide-react";
import { clock } from "../../api";
import { ModalShell } from "../../shared/ModalShell";
import type { Workspace } from "../../hooks/useWorkspace";
export function TrackDialog(
  workspace: Pick<
    Workspace,
    | "modal"
    | "track"
    | "detail"
    | "close"
    | "act"
    | "correction"
    | "time"
    | "busy"
    | "setPointEdit"
    | "setTab"
    | "notify"
  >,
) {
  const {
    modal,
    track,
    detail,
    close,
    act,
    correction,
    time,
    busy,
    setPointEdit,
    setTab,
    notify,
  } = workspace;
  if (!detail) return null;
  return (
    <>
      {modal === "track" && track && detail && (
        <ModalShell
          title={track.player || `Review track ${track.id.split("-").at(-1)}`}
          subtitle="Link this observed fragment to a team and player. Track IDs alone do not establish identity."
          onClose={close}
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              act(async () => {
                await correction("label", {
                  track_id: track.id,
                  start: Number(f.get("start")),
                  end: Number(f.get("end")),
                  team: f.get("team"),
                  player: f.get("player"),
                  role: f.get("role"),
                  alias: "",
                });
                close();
              }, "Identity assignment updated");
            }}
          >
            <label>
              Player name / jersey
              <input
                name="player"
                defaultValue={track.player}
                placeholder="e.g. Alex · #7"
                maxLength={100}
              />
            </label>
            <div className="form-row">
              <label>
                Team
                <select name="team" defaultValue={track.team}>
                  <option value="unknown">Unknown</option>
                  <option value="home">{detail.match.home}</option>
                  <option value="away">{detail.match.away}</option>
                </select>
              </label>
              <label>
                Role
                <select name="role" defaultValue={track.role}>
                  {["player", "goalkeeper", "official", "ball", "unknown"].map(
                    (v) => (
                      <option key={v}>{v}</option>
                    ),
                  )}
                </select>
              </label>
            </div>
            <div className="form-row">
              <label>
                From (seconds)
                <input
                  name="start"
                  type="number"
                  min="0"
                  step=".01"
                  defaultValue={track.start}
                />
              </label>
              <label>
                Until (seconds)
                <input
                  name="end"
                  type="number"
                  min="0"
                  step=".01"
                  defaultValue={track.end + 1}
                />
              </label>
            </div>
            <div className="modal-actions">
              <button
                className="button"
                type="button"
                onClick={() =>
                  act(async () => {
                    await correction("split", { track_id: track.id, time });
                    close();
                  }, "Track split after the current video time")
                }
              >
                Split at {clock(time)}
              </button>
              <button className="button primary" disabled={busy}>
                Save identity
              </button>
            </div>
          </form>
          <div className="divider" />
          <button
            className="text-button"
            onClick={() => {
              setPointEdit(true);
              setTab("overview");
              close();
              notify(
                "Click the corrected ground-contact position in the video at this analyzed frame.",
              );
            }}
          >
            <Target size={15} />
            Correct position in current frame
          </button>
          <form
            className="merge-form"
            onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              act(async () => {
                await correction("merge", {
                  track_ids: [track.id, f.get("other")],
                  player: f.get("identity"),
                  team: track.team,
                });
                close();
              }, "Non-overlapping fragments linked");
            }}
          >
            <label>
              Link another fragment
              <select name="other" required>
                <option value="">Choose fragment</option>
                {detail.tracks
                  .filter((t) => t.id !== track.id)
                  .map((t) => (
                    <option value={t.id} key={t.id}>
                      {t.player || t.id}
                    </option>
                  ))}
              </select>
            </label>
            <label>
              Shared player identity
              <input name="identity" required defaultValue={track.player} />
            </label>
            <button className="button small">
              <Link2 size={14} />
              Link fragments
            </button>
          </form>
        </ModalShell>
      )}
    </>
  );
}
