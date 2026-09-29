import { ModalShell } from "../../shared/ModalShell";
import type { Workspace } from "../../hooks/useWorkspace";
export function ExcludeDialog(
  workspace: Pick<
    Workspace,
    "modal" | "detail" | "close" | "act" | "correction" | "time"
  >,
) {
  const { modal, detail, close, act, correction, time } = workspace;
  if (!detail) return null;
  return (
    <>
      {modal === "exclude" && detail && (
        <ModalShell
          title="Exclude an interval."
          subtitle="Replays and non-play footage should not inflate your match statistics."
          onClose={close}
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              act(async () => {
                await correction("exclude", {
                  start: Number(f.get("start")),
                  end: Number(f.get("end")),
                  reason: f.get("reason"),
                });
                close();
              }, "Interval excluded");
            }}
          >
            <div className="form-row">
              <label>
                From (seconds)
                <input
                  name="start"
                  type="number"
                  min="0"
                  step=".01"
                  defaultValue={time.toFixed(2)}
                />
              </label>
              <label>
                Until (seconds)
                <input
                  name="end"
                  type="number"
                  min="0"
                  step=".01"
                  defaultValue={Math.min(
                    detail.match.duration,
                    time + 5,
                  ).toFixed(2)}
                />
              </label>
            </div>
            <label>
              Reason
              <input name="reason" defaultValue="Replay / non-play footage" />
            </label>
            <button className="button primary">Exclude interval</button>
          </form>
        </ModalShell>
      )}
    </>
  );
}
