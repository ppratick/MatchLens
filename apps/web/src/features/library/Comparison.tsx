import { useEffect, useState } from "react";
import { Layers, AlertTriangle } from "lucide-react";
import { api } from "../../api";
import type { Detail, Match, Team } from "../../types";
export function Comparison({
  matches,
  notify,
}: {
  matches: Match[];
  notify: (s: string) => void;
}) {
  const [left, setLeft] = useState(""),
    [right, setRight] = useState(""),
    [data, setData] = useState<Detail[]>([]);
  useEffect(() => {
    if (!left || !right) {
      setData([]);
      return;
    }
    Promise.all([
      api<Detail>("/matches/" + left),
      api<Detail>("/matches/" + right),
    ])
      .then(setData)
      .catch((e) => notify(e.message));
  }, [left, right, notify]);
  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <div className="eyebrow">THE BIGGER PICTURE</div>
          <h1>
            A game is part of a story<span>.</span>
          </h1>
          <p>
            Compare reviewed results, with coverage and source differences kept
            in view.
          </p>
        </div>
      </div>
      <div className="compare-select">
        <label>
          First match
          <select value={left} onChange={(e) => setLeft(e.target.value)}>
            <option value="">Choose a match</option>
            {matches.map((m) => (
              <option value={m.id} key={m.id}>
                {m.title}
              </option>
            ))}
          </select>
        </label>
        <Layers size={24} />
        <label>
          Second match
          <select value={right} onChange={(e) => setRight(e.target.value)}>
            <option value="">Choose a match</option>
            {matches.map((m) => (
              <option value={m.id} key={m.id}>
                {m.title}
              </option>
            ))}
          </select>
        </label>
      </div>
      {data.length === 2 ? (
        <>
          <div className="notice">
            <AlertTriangle size={17} />
            {data[0].match.profile !== data[1].match.profile
              ? "Different capture profiles: statistics are not directly comparable."
              : "Counts cover confirmed events only; review completeness and footage coverage may differ."}
          </div>
          <div className="panel">
            <table>
              <thead>
                <tr>
                  <th>Reviewed measure</th>
                  {data.map((d) => (
                    <th key={d.match.id}>{d.match.title}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[
                  "Coverage",
                  "Confirmed events",
                  "Goals",
                  "Shots",
                  "Passes",
                  "Saves",
                ].map((metric) => (
                  <tr key={metric}>
                    <th>{metric}</th>
                    {data.map((d) => (
                      <td key={d.match.id}>
                        {metric === "Coverage"
                          ? d.statistics.coverage_percent + "%"
                          : metric === "Confirmed events"
                            ? d.statistics.confirmed_events
                            : ["home", "away"]
                                .map(
                                  (t) =>
                                    d.statistics.counts[t as Team][
                                      {
                                        Goals: "goal",
                                        Shots: "shot",
                                        Passes: "pass",
                                        Saves: "save",
                                      }[metric] || ""
                                    ] || 0,
                                )
                                .join(" — ")}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : (
        <div className="panel comparison-empty">
          <Layers size={35} />
          <h3>Two matches. More context.</h3>
          <p>
            Select two matches to inspect their confirmed events and analysis
            coverage side by side.
          </p>
        </div>
      )}
    </div>
  );
}
