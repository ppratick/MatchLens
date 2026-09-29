import {
  ArrowDownToLine,
  ArrowRight,
  Download,
  FileText,
  Film,
  Scissors,
} from "lucide-react";
import { api, clock } from "../../api";
import type { Workspace } from "../../hooks/useWorkspace";
export function Exports(
  workspace: Pick<
    Workspace,
    "tab" | "setModal" | "busy" | "act" | "selected" | "detail" | "exportUrl"
  >,
) {
  const { tab, setModal, busy, act, selected, detail, exportUrl } = workspace;
  if (!detail) return null;
  return (
    <>
      {tab === "exports" && (
        <>
          <div className="export-actions">
            <div className="panel export-action">
              <span className="round-icon">
                <Scissors size={23} />
              </span>
              <h3>The moments worth keeping.</h3>
              <p>
                Build highlights from confirmed events, or trim your own clip.
                Filter reels by team or reviewed player identity.
              </p>
              <button
                className="button primary"
                onClick={() => setModal("clip")}
              >
                Create highlights <ArrowRight size={16} />
              </button>
            </div>
            <div className="panel export-action">
              <span className="round-icon">
                <FileText size={23} />
              </span>
              <h3>A report you can stand behind.</h3>
              <p>
                Statistics, coverage, field visualization, and the timeline—with
                JSON and CSV for your own analysis.
              </p>
              <button
                className="button"
                disabled={busy}
                onClick={() =>
                  act(
                    () => api(`/matches/${selected}/report`, "POST"),
                    "Report queued",
                  )
                }
              >
                Generate report <ArrowRight size={16} />
              </button>
            </div>
          </div>
          <div className="panel">
            <div className="panel-header">
              <h3>Your exports</h3>
              <span className="muted">Local files · versioned results</span>
            </div>
            {detail.exports.map((a) => (
              <div className="export-row" key={a.id}>
                <span className="file-icon">
                  {a.kind === "report" ? (
                    <FileText size={22} />
                  ) : (
                    <Film size={22} />
                  )}
                </span>
                <div>
                  <strong>{a.title}</strong>
                  <small>
                    Revision {a.revision}{" "}
                    {a.revision !== detail.match.revision
                      ? "· older than current review"
                      : ""}
                    {a.duration ? ` · ${clock(a.duration)}` : ""}
                  </small>
                </div>
                <div className="export-links">
                  {Object.keys(a.files).map((name) => (
                    <a
                      className="button small"
                      key={name}
                      href={exportUrl(a, name)}
                      target="_blank"
                      rel="noreferrer"
                    >
                      <Download size={13} />
                      {name.split(".").at(-1)?.toUpperCase()}
                    </a>
                  ))}
                </div>
              </div>
            ))}
            {!detail.exports.length && (
              <div className="small-empty">
                <ArrowDownToLine size={28} />
                <p>Your clips and reports will appear here.</p>
              </div>
            )}
          </div>
        </>
      )}
    </>
  );
}
