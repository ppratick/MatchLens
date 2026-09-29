import { clock } from "../../api";
import { ModalShell } from "../../shared/ModalShell";
import type { Workspace } from "../../hooks/useWorkspace";
export function ClockDialog(
  workspace: Pick<
    Workspace,
    "modal" | "detail" | "close" | "act" | "correction" | "time"
  >,
) {
  const { modal, detail, close, act, correction, time } = workspace;
  if (!detail) return null;
  return (
    <>
      {modal === "clock" && detail && (
        <ModalShell
          title="Set the match clock."
          subtitle="Match time is separate from recording time."
          onClose={close}
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              act(async () => {
                await correction("clock", {
                  period: Number(f.get("period")),
                  media_anchor: Number(f.get("media")),
                  match_anchor: Number(f.get("match")),
                });
                close();
              }, "Match clock updated");
            }}
          >
            <label>
              Period
              <input
                name="period"
                type="number"
                min="1"
                max="6"
                defaultValue={detail.review.clock.period}
              />
            </label>
            <div className="form-row">
              <label>
                Video anchor (seconds)
                <input
                  name="media"
                  type="number"
                  min="0"
                  step=".01"
                  defaultValue={time.toFixed(2)}
                />
              </label>
              <label>
                Match time at anchor (seconds)
                <input
                  name="match"
                  type="number"
                  min="0"
                  defaultValue={detail.review.clock.match_anchor}
                />
              </label>
            </div>
            <button className="button primary">Save clock</button>
          </form>
        </ModalShell>
      )}
    </>
  );
}
