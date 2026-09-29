import { useEffect, useState } from "react";
import { ArrowRight, Play } from "lucide-react";
import { api, clock } from "../../api";
import type { Detail, Match, Source } from "../../types";
import { Pitch } from "../../features/field/Pitch";
export function MatchCard({
  match,
  onClick,
}: {
  match: Match;
  onClick: () => void;
}) {
  const [source, setSource] = useState<Source | null>(null);
  useEffect(() => {
    api<Detail>("/matches/" + match.id)
      .then((d) => setSource(d.sources[0] || null))
      .catch(() => {});
  }, [match.id, match.updated]);
  return (
    <button className="match-card" onClick={onClick}>
      <div className="match-poster">
        {source?.poster ? (
          <img
            src={`/api/matches/${match.id}/poster/${source.id}`}
            alt="Recording preview"
          />
        ) : (
          <Pitch />
        )}
        <span className="poster-tag">
          {match.profile === "synthetic" ? "SYNTHETIC DEMO" : "SOCCER"}
        </span>
        <span className="poster-duration">{clock(match.duration)}</span>
        <span className="poster-play">
          <Play size={20} />
        </span>
      </div>
      <div className="match-card-body">
        <div className="card-date">
          {match.date || new Date(match.created * 1000).toLocaleDateString()}
        </div>
        <h3>{match.title}</h3>
        <p>
          {match.home} <span>vs</span> {match.away}
        </p>
        <div className="card-bottom">
          <span>
            <i className="dot" />
            {source ? "Ready to review" : "Awaiting recording"}
          </span>
          <ArrowRight size={17} />
        </div>
      </div>
    </button>
  );
}
