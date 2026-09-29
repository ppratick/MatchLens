import { labels } from "../../shared/constants";
import type { Workspace } from "../../hooks/useWorkspace";
export function PlayerSummaries(workspace: Pick<Workspace, "tab" | "detail">) {
  const { tab, detail } = workspace;
  if (!detail) return null;
  return (
    <>
      {tab === "players" && !!detail.statistics.players?.length && (
        <div className="panel" style={{ marginBottom: 20 }}>
          <div className="panel-header">
            <h3>Reviewed player summaries</h3>
          </div>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Player</th>
                  <th>Team</th>
                  <th>Observed time</th>
                  <th>Confirmed events</th>
                </tr>
              </thead>
              <tbody>
                {detail.statistics.players.map((p, i) => (
                  <tr key={i}>
                    <td>{p.player}</td>
                    <td>
                      {p.team === "unknown" ? "Unknown" : detail.match[p.team]}
                    </td>
                    <td>{p.observed_seconds.toFixed(1)} s</td>
                    <td>
                      {Object.entries(p.counts)
                        .map(([kind, n]) => `${labels[kind] || kind}: ${n}`)
                        .join(" · ") || "None reviewed"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="panel-description">
            Observed time is not minutes played. Counts include reviewed events
            only; linked fragments are not double-counted in observed time.
          </p>
        </div>
      )}
    </>
  );
}
