import { Check } from "lucide-react";
import { labels } from "../../shared/constants";
import { ModalShell } from "../../shared/ModalShell";
import type { Workspace } from "../../hooks/useWorkspace";
export function EventDialog(
  workspace: Pick<
    Workspace,
    | "modal"
    | "detail"
    | "eventEdit"
    | "close"
    | "act"
    | "correction"
    | "sourceId"
    | "time"
    | "busy"
  >,
) {
  const {
    modal,
    detail,
    eventEdit,
    close,
    act,
    correction,
    sourceId,
    time,
    busy,
  } = workspace;
  if (!detail) return null;
  return (
    <>
      {modal === "event" && detail && (
        <ModalShell
          title={eventEdit ? "Review this moment." : "Mark a match moment."}
          subtitle="Confirmed events update your statistics. You can always edit or undo."
          onClose={close}
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              act(async () => {
                await correction("event", {
                  id: eventEdit?.id || crypto.randomUUID().replaceAll("-", ""),
                  kind: f.get("kind"),
                  start: Number(f.get("start")),
                  end: f.get("end") ? Number(f.get("end")) : null,
                  team: f.get("team"),
                  player: f.get("player"),
                  status: f.get("status"),
                  note: f.get("note"),
                  origin: eventEdit?.origin || "manual",
                  evidence: eventEdit?.evidence || "",
                  score: eventEdit?.score ?? null,
                  source_id: sourceId || null,
                });
                close();
              }, "Timeline updated");
            }}
          >
            <div className="form-row">
              <label>
                Event
                <select name="kind" defaultValue={eventEdit?.kind || "goal"}>
                  {Object.entries(labels).map(([k, v]) => (
                    <option key={k} value={k}>
                      {v}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Review status
                <select
                  name="status"
                  defaultValue={eventEdit?.status || "confirmed"}
                >
                  <option value="confirmed">Confirmed by me</option>
                  <option value="proposed">Needs review</option>
                  <option value="rejected">Rejected</option>
                </select>
              </label>
            </div>
            <div className="form-row">
              <label>
                Start (video seconds)
                <input
                  name="start"
                  type="number"
                  min="0"
                  max={detail.match.duration}
                  step=".01"
                  required
                  defaultValue={(eventEdit?.start ?? time).toFixed(2)}
                />
              </label>
              <label>
                End (intervals only)
                <input
                  name="end"
                  type="number"
                  min="0"
                  max={detail.match.duration}
                  step=".01"
                  defaultValue={eventEdit?.end ?? ""}
                />
              </label>
            </div>
            <div className="form-row">
              <label>
                Team
                <select name="team" defaultValue={eventEdit?.team || "home"}>
                  <option value="home">{detail.match.home}</option>
                  <option value="away">{detail.match.away}</option>
                  <option value="unknown">Unknown</option>
                </select>
              </label>
              <label>
                Player identity
                <input
                  name="player"
                  maxLength={100}
                  defaultValue={eventEdit?.player || ""}
                  placeholder="Optional, reviewed identity"
                />
              </label>
            </div>
            <label>
              Notes
              <textarea
                name="note"
                rows={3}
                maxLength={2000}
                defaultValue={eventEdit?.note || ""}
              />
            </label>
            {eventEdit?.evidence && (
              <p className="muted">Evidence: {eventEdit.evidence}</p>
            )}
            <div className="modal-actions">
              <button className="button" type="button" onClick={close}>
                Cancel
              </button>
              <button className="button primary" disabled={busy}>
                <Check size={17} />
                Save moment
              </button>
            </div>
          </form>
        </ModalShell>
      )}
    </>
  );
}
