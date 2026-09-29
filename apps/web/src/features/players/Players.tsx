import { SlidersHorizontal, Users } from "lucide-react";
import { clock } from "../../api";
import { teamColor } from "../../shared/constants";
import type { Workspace } from "../../hooks/useWorkspace";
export function Players(
  workspace: Pick<
    Workspace,
    "tab" | "detail" | "setTab" | "seek" | "setTrackId" | "setModal"
  >,
) {
  const { tab, detail, setTab, seek, setTrackId, setModal } = workspace;
  if (!detail) return null;
  return (
    <>
      {tab === "players" && (
        <div className="panel">
          <div className="panel-header">
            <div>
              <h2>Follow the player, not just the box.</h2>
              <p className="muted">
                Anonymous tracks become player identities only when you link
                them. Visibility gaps stay unknown.
              </p>
            </div>
            <Users size={22} />
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Track / player</th>
                  <th>Team</th>
                  <th>Role</th>
                  <th>Observed</th>
                  <th>Video interval</th>
                  <th>Review</th>
                </tr>
              </thead>
              <tbody>
                {detail.tracks.map((t) => (
                  <tr key={t.id}>
                    <td>
                      <span
                        className="player-dot"
                        style={{ background: teamColor[t.team] }}
                      />
                      {t.player || `Track ${t.id.split("-").at(-1)}`}
                      <small>{t.id}</small>
                    </td>
                    <td>
                      {t.team === "unknown"
                        ? `Unassigned${t.team_hint && t.team_hint !== "unknown" ? " · " + t.team_hint : ""}`
                        : detail.match[t.team]}
                    </td>
                    <td>{t.role}</td>
                    <td>{t.observed_seconds.toFixed(1)} s</td>
                    <td>
                      <button
                        className="text-button"
                        onClick={() => {
                          setTab("overview");
                          setTimeout(() => seek(t.start), 100);
                        }}
                      >
                        {clock(t.start)}–{clock(t.end)}
                      </button>
                    </td>
                    <td>
                      <button
                        className="button small"
                        onClick={() => {
                          setTrackId(t.id);
                          setModal("track");
                        }}
                      >
                        <SlidersHorizontal size={14} />
                        Edit identity
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!detail.tracks.length && (
              <div className="small-empty">
                <Users size={30} />
                <h3>No player tracks yet</h3>
                <p>
                  Run analysis on your recording to inspect its player tracks.
                </p>
                <button className="button" onClick={() => setModal("analyze")}>
                  Set up analysis
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
