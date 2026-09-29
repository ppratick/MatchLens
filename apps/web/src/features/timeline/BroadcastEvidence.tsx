export type BroadcastSetup = {
  scoreboard: number[] | null;
  observations: {
    time: number;
    home: number;
    away: number;
    clock: string;
    note: string;
  }[];
  goal_suggestions: boolean;
};
export function BroadcastEvidence({
  value,
  change,
  time,
}: {
  value: BroadcastSetup;
  change: (value: BroadcastSetup) => void;
  time: number;
}) {
  return (
    <details>
      <summary>Scoreboard evidence · experimental suggestions</summary>
      <p className="muted">
        Use the scoreboard drawing tool to mark its region. Enter what you can
        read; this evidence never updates the confirmed match score by itself.
        OCR is not enabled. Suggestions require a score increment plus a
        separately marked replay.
      </p>
      <p>
        {value.scoreboard
          ? `Region: ${value.scoreboard.map((v) => v.toFixed(3)).join(", ")}`
          : "No scoreboard region selected"}
      </p>
      {value.scoreboard && (
        <button
          className="text-button"
          onClick={() => change({ ...value, scoreboard: null })}
        >
          Clear scoreboard region
        </button>
      )}
      <label className="checkbox">
        <input
          type="checkbox"
          checked={value.goal_suggestions}
          onChange={(e) =>
            change({ ...value, goal_suggestions: e.target.checked })
          }
        />{" "}
        Enable goal review suggestions · unvalidated, 0 evaluated samples
      </label>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          const f = new FormData(e.currentTarget);
          const observation = {
            time: Number(f.get("scoreTime")),
            home: Number(f.get("homeScore")),
            away: Number(f.get("awayScore")),
            clock: String(f.get("scoreClock")),
            note: String(f.get("scoreNote")),
          };
          change({
            ...value,
            observations: [
              ...value.observations.filter((o) => o.time !== observation.time),
              observation,
            ].sort((a, b) => a.time - b.time),
          });
        }}
      >
        <div className="form-row">
          <label>
            Score evidence time
            <input
              name="scoreTime"
              type="number"
              min="0"
              step=".001"
              required
              defaultValue={time}
            />
          </label>
          <label>
            Home scoreboard value
            <input
              name="homeScore"
              type="number"
              min="0"
              max="99"
              required
              defaultValue="0"
            />
          </label>
          <label>
            Away scoreboard value
            <input
              name="awayScore"
              type="number"
              min="0"
              max="99"
              required
              defaultValue="0"
            />
          </label>
        </div>
        <div className="form-row">
          <label>
            Visible scoreboard clock
            <input name="scoreClock" maxLength={40} />
          </label>
          <label>
            Scoreboard context
            <input name="scoreNote" maxLength={500} />
          </label>
        </div>
        <button className="button small">Add scoreboard evidence</button>
      </form>
      {value.observations.map((o) => (
        <p key={o.time}>
          {o.time.toFixed(3)} s · scoreboard {o.home}–{o.away} · {o.clock}{" "}
          <button
            className="text-button"
            onClick={() =>
              change({
                ...value,
                observations: value.observations.filter((x) => x !== o),
              })
            }
          >
            Remove evidence
          </button>
        </p>
      ))}
      <p className="muted">
        A suggestion never changes score. Review the action, timing and legality
        before confirming. Other automatic event types remain disabled until
        evaluated. Detection confidence is not accuracy.
      </p>
    </details>
  );
}
