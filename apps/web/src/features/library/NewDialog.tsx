import { ArrowRight, Upload } from "lucide-react";
import { api } from "../../api";
import type { Match } from "../../types";
import { ModalShell } from "../../shared/ModalShell";
import type { Workspace } from "../../hooks/useWorkspace";
export function NewDialog(
  workspace: Pick<
    Workspace,
    "modal" | "close" | "act" | "openMatch" | "importFile" | "busy"
  >,
) {
  const { modal, close, act, openMatch, importFile, busy } = workspace;

  return (
    <>
      {modal === "new" && (
        <ModalShell
          title="A new game. A new perspective."
          subtitle="Give your match a home. Your original recording will be preserved locally."
          onClose={close}
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              act(async () => {
                const m = await api<Match>("/matches", "POST", {
                  title: f.get("title"),
                  home: f.get("home"),
                  away: f.get("away"),
                  date: f.get("date"),
                  profile: f.get("profile"),
                });
                close();
                openMatch(m.id);
                const file = f.get("file") as File;
                if (file?.size) await importFile(file, m.id);
              });
            }}
          >
            <label>
              Match title
              <input
                name="title"
                required
                placeholder="Saturday friendly"
                maxLength={150}
              />
            </label>
            <div className="form-row">
              <label>
                Home team
                <input
                  name="home"
                  defaultValue="Home"
                  required
                  maxLength={60}
                />
              </label>
              <label>
                Away team
                <input
                  name="away"
                  defaultValue="Away"
                  required
                  maxLength={60}
                />
              </label>
            </div>
            <div className="form-row">
              <label>
                Match date
                <input
                  name="date"
                  type="date"
                  defaultValue={new Date().toISOString().slice(0, 10)}
                />
              </label>
              <label>
                Recording profile
                <select name="profile">
                  <option value="broadcast">
                    Imported broadcast recording
                  </option>
                  <option value="screen">Direct Mac screen capture</option>
                  <option value="phone_tv">Phone recording a television</option>
                  <option value="sideline" disabled>
                    Physical sideline recording · Coming later
                  </option>
                </select>
              </label>
            </div>
            <label className="file-drop">
              <Upload size={25} />
              <strong>Choose a recording</strong>
              <span>Optional—you can import or capture later.</span>
              <input name="file" type="file" accept="video/*,.mkv,.ts" />
            </label>
            <div className="modal-actions">
              <button className="button" type="button" onClick={close}>
                Cancel
              </button>
              <button className="button primary" disabled={busy}>
                Create match <ArrowRight size={16} />
              </button>
            </div>
          </form>
        </ModalShell>
      )}
    </>
  );
}
