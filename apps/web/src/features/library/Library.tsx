import {
  ArrowRight,
  Clock3,
  Film,
  Plus,
  ScanLine,
  Search,
  ShieldCheck,
  Upload,
  Video,
} from "lucide-react";
import { api } from "../../api";
import type { Match } from "../../types";
import { Pitch } from "../../features/field/Pitch";
import { MatchCard } from "../../features/library/MatchCard";
import type { Workspace } from "../../hooks/useWorkspace";
export function Library(
  workspace: Pick<
    Workspace,
    | "section"
    | "setModal"
    | "matches"
    | "query"
    | "setQuery"
    | "busy"
    | "act"
    | "openMatch"
  >,
) {
  const { section, setModal, matches, query, setQuery, busy, act, openMatch } =
    workspace;

  return (
    <>
      {section === "library" && (
        <div className="page">
          <div className="page-heading">
            <div>
              <div className="eyebrow">THE GAME, IN FOCUS</div>
              <h1>
                Your match library<span>.</span>
              </h1>
              <p>Every moment. A clearer picture of the game.</p>
            </div>
            <button className="button primary" onClick={() => setModal("new")}>
              <Plus size={18} />
              New match
            </button>
          </div>
          <div className="library-stats">
            <div>
              <span className="stat-icon">
                <Film size={19} />
              </span>
              <div>
                <strong>{matches.length.toString().padStart(2, "0")}</strong>
                <span>Matches in your library</span>
              </div>
            </div>
            <div>
              <span className="stat-icon">
                <Clock3 size={19} />
              </span>
              <div>
                <strong>
                  {Math.round(matches.reduce((s, m) => s + m.duration, 0) / 60)}
                  <small> min</small>
                </strong>
                <span>Recorded match time</span>
              </div>
            </div>
            <div>
              <span className="stat-icon">
                <ShieldCheck size={19} />
              </span>
              <div>
                <strong>
                  100%<small> local</small>
                </strong>
                <span>Your data stays with you</span>
              </div>
            </div>
          </div>
          <div className="section-toolbar">
            <h2>
              All matches <span className="count">{matches.length}</span>
            </h2>
            <div className="search">
              <Search size={17} />
              <input
                aria-label="Search matches"
                placeholder="Search your matches"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </div>
          </div>
          {matches.length === 0 ? (
            <div className="welcome-grid">
              <div className="welcome">
                <span className="round-icon">
                  <Video size={26} />
                </span>
                <h2>It starts with a recording.</h2>
                <p>
                  Bring in a game, follow your players, and turn the moments
                  that matter into a reviewable match story.
                </p>
                <button
                  className="button primary"
                  onClick={() => setModal("new")}
                >
                  <Upload size={17} />
                  Import your first match
                </button>
                <button
                  className="text-button"
                  disabled={busy}
                  onClick={() =>
                    act(async () => {
                      const m = await api<Match>("/demo", "POST");
                      openMatch(m.id);
                    }, "Generating a clearly labeled synthetic demo…")
                  }
                >
                  Explore a synthetic demo <ArrowRight size={16} />
                </button>
                <div className="supported">
                  MP4 · MOV · MKV · WEBM · SCREEN RECORDINGS
                </div>
              </div>
              <div className="welcome-field">
                <div className="field-card-heading">
                  <span>
                    <i className="dot" />A DIFFERENT PERSPECTIVE
                  </span>
                  <ScanLine size={18} />
                </div>
                <Pitch />
                <div className="field-caption">
                  <strong>See the shape of your game.</strong>
                  <p>Track players. Review decisions. Keep the evidence.</p>
                </div>
              </div>
            </div>
          ) : (
            <div className="match-grid">
              {matches
                .filter((m) =>
                  `${m.title} ${m.home} ${m.away}`
                    .toLowerCase()
                    .includes(query.toLowerCase()),
                )
                .map((m) => (
                  <MatchCard
                    key={m.id}
                    match={m}
                    onClick={() => openMatch(m.id)}
                  />
                ))}
              <button
                className="new-match-card"
                onClick={() => setModal("new")}
              >
                <Plus size={26} />
                <strong>Add another match</strong>
                <span>Import a recording or set up capture</span>
              </button>
            </div>
          )}
          <div className="footnote">
            <ShieldCheck size={15} />
            <span>
              Original recordings are preserved. Analysis can always be reviewed
              and corrected.
            </span>
          </div>
        </div>
      )}
    </>
  );
}
