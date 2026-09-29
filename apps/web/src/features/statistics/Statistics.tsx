import {
  Check,
  CheckCircle2,
  Clock3,
  Flag,
  Goal,
  Plus,
  Target,
} from "lucide-react";
import { clock } from "../../api";
import { teamColor } from "../../shared/constants";
import { labels } from "../../shared/constants";
import type { Workspace } from "../../hooks/useWorkspace";
export function Statistics(
  workspace: Pick<
    Workspace,
    | "setModal"
    | "detail"
    | "time"
    | "tab"
    | "setEventEdit"
    | "seek"
    | "eventAction"
  >,
) {
  const { setModal, detail, time, tab, setEventEdit, seek, eventAction } =
    workspace;
  if (!detail) return null;
  return (
    <>
      <aside className="insight-column">
        <div className="panel scoreboard">
          <div className="score-label">
            <span className="eyebrow">REVIEWED SCORE</span>
            <button
              className="icon-button"
              title="Set match clock"
              onClick={() => setModal("clock")}
            >
              <Clock3 size={15} />
            </button>
          </div>
          <div className="score-teams">
            <div>
              <span className="team-crest home">
                {detail.match.home.slice(0, 2).toUpperCase()}
              </span>
              <strong>{detail.match.home}</strong>
            </div>
            <div className="score-number">
              {detail.statistics.score.home}
              <span>:</span>
              {detail.statistics.score.away}
            </div>
            <div>
              <span className="team-crest away">
                {detail.match.away.slice(0, 2).toUpperCase()}
              </span>
              <strong>{detail.match.away}</strong>
            </div>
          </div>
          <div className="match-clock">
            Period {detail.review.clock.period} ·{" "}
            {clock(
              Math.max(
                0,
                time -
                  detail.review.clock.media_anchor +
                  detail.review.clock.match_anchor,
              ),
            )}
            <span>From confirmed goals</span>
          </div>
        </div>
        <div className="panel">
          <div className="panel-header">
            <h3>Match insights</h3>
            <span className="pill">REVIEWABLE</span>
          </div>
          <div className="insights">
            <div className="metric-big">
              <span>Analysis coverage</span>
              <strong>
                {detail.statistics.coverage_percent}
                <small>%</small>
              </strong>
            </div>
            <div className="meter">
              <i
                style={{
                  width: detail.statistics.coverage_percent + "%",
                }}
              />
            </div>
            <small>Sampled time, not guaranteed visibility</small>
            <div className="mini-stats">
              <div>
                <strong>{detail.statistics.unique_tracks}</strong>
                <span>Player tracks</span>
              </div>
              <div>
                <strong>{detail.statistics.confirmed_events}</strong>
                <span>Confirmed events</span>
              </div>
            </div>
            <div className="possession-title">
              Reviewed possession{" "}
              <span>
                UNKNOWN {detail.statistics.possession.percent.unknown ?? 100}%
              </span>
            </div>
            <div className="possession-bar">
              <i
                style={{
                  width: (detail.statistics.possession.percent.home || 0) + "%",
                  background: teamColor.home,
                }}
              />
              <i
                style={{
                  width: (detail.statistics.possession.percent.away || 0) + "%",
                  background: teamColor.away,
                }}
              />
            </div>
            <small>
              Unknown includes{" "}
              {detail.statistics.possession.contested_seconds ?? 0} s contested;
              neither team is assigned control.
            </small>
            <div className="team-legend">
              <span>
                <i style={{ background: teamColor.home }} />
                {detail.match.home}
              </span>
              <span>
                <i style={{ background: teamColor.away }} />
                {detail.match.away}
              </span>
            </div>
          </div>
        </div>
        <div className="panel events-panel">
          <div className="panel-header">
            <h3>
              Match moments{" "}
              <span className="count">
                {
                  detail.events.filter(
                    (e) => tab === "timeline" || e.status !== "rejected",
                  ).length
                }
              </span>
            </h3>
            <button
              className="icon-button"
              title="Add event"
              onClick={() => {
                setEventEdit(null);
                setModal("event");
              }}
            >
              <Plus size={18} />
            </button>
          </div>
          <div className="event-list">
            {detail.events
              .filter((e) => tab === "timeline" || e.status !== "rejected")
              .map((e) => (
                <div
                  className={"event-row " + (e.excluded ? "excluded" : "")}
                  key={e.id}
                >
                  <button className="event-time" onClick={() => seek(e.start)}>
                    {clock(e.start)}
                  </button>
                  <span
                    className="event-icon"
                    style={{ color: teamColor[e.team] }}
                  >
                    {e.kind === "goal" ? (
                      <Goal size={17} />
                    ) : e.kind === "shot" ? (
                      <Target size={17} />
                    ) : e.kind === "possession" ? (
                      <Clock3 size={17} />
                    ) : (
                      <Flag size={16} />
                    )}
                  </span>
                  <button
                    className="event-description"
                    onClick={() => {
                      setEventEdit(e);
                      setModal("event");
                    }}
                  >
                    <strong>
                      {labels[e.kind]}
                      {e.status === "rejected" ? " · rejected" : ""}
                      {e.excluded ? " · excluded" : ""}
                    </strong>
                    <span>
                      {e.player ||
                        {
                          home: detail.match.home,
                          away: detail.match.away,
                          unknown: "Unassigned",
                        }[e.team]}
                    </span>
                  </button>
                  {e.status === "confirmed" ? (
                    <CheckCircle2 size={15} className="confirmed" />
                  ) : (
                    <button
                      className="icon-button"
                      title="Confirm event"
                      onClick={() => eventAction(e, "confirmed")}
                    >
                      <Check size={16} />
                    </button>
                  )}
                </div>
              ))}
            {detail.events.length === 0 && (
              <div className="small-empty">
                <Flag size={25} />
                <strong>Your timeline starts here</strong>
                <p>
                  Tag a moment while you watch. Confirmed events power your
                  report.
                </p>
              </div>
            )}
          </div>
          <button
            className="panel-footer-button"
            onClick={() => {
              setEventEdit(null);
              setModal("event");
            }}
          >
            <Plus size={16} />
            Add a match moment
          </button>
        </div>
      </aside>
    </>
  );
}
