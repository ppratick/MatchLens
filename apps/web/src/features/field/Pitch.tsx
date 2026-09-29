import type { Team } from "../../types";
import { teamColor } from "../../shared/constants";
export function Pitch({
  points = [],
  paths = [],
  heat = false,
  selected,
  onSelect,
}: {
  points?: { id: string; x: number; y: number; team: Team }[];
  paths?: { id: string; points: number[][]; team: Team }[];
  heat?: boolean;
  selected?: string;
  onSelect?: (id: string) => void;
}) {
  return (
    <svg
      className="pitch"
      viewBox="0 0 680 450"
      role="img"
      aria-label={heat ? "Player position heatmap" : "Top-down soccer field"}
    >
      <defs>
        <pattern
          id="stripes"
          width="120"
          height="450"
          patternUnits="userSpaceOnUse"
        >
          <rect width="60" height="450" fill="#ffffff" opacity=".018" />
        </pattern>
        <radialGradient id="heat">
          <stop offset="0" stopColor="#d9f58c" stopOpacity=".6" />
          <stop offset="1" stopColor="#d9f58c" stopOpacity="0" />
        </radialGradient>
      </defs>
      <rect width="680" height="450" rx="12" fill="#173c31" />
      <rect x="25" y="25" width="630" height="400" fill="url(#stripes)" />
      <g fill="none" stroke="#8bab95" strokeWidth="1.3" opacity=".6">
        <rect x="25" y="25" width="630" height="400" />
        <path d="M340 25V425M25 112H125V338H25M655 112H555V338H655M25 170H62V280H25M655 170H618V280H655" />
        <circle cx="340" cy="225" r="55" />
        <path d="M125 179Q166 225 125 271M555 179Q514 225 555 271" />
        <rect x="14" y="199" width="11" height="52" />
        <rect x="655" y="199" width="11" height="52" />
      </g>
      <g fill="#8bab95">
        <circle cx="340" cy="225" r="2" />
        <circle cx="94" cy="225" r="2" />
        <circle cx="586" cy="225" r="2" />
      </g>
      {paths.map((path) =>
        heat ? (
          <g key={path.id}>
            {path.points.map(([x, y], i) => (
              <circle
                key={i}
                cx={25 + x * 630}
                cy={25 + y * 400}
                r="16"
                fill="url(#heat)"
              />
            ))}
          </g>
        ) : (
          <path
            key={path.id}
            d={path.points
              .map(
                ([x, y, t], i) =>
                  `${i === 0 || t - path.points[i - 1][2] > 3 ? "M" : "L"}${25 + x * 630},${25 + y * 400}`,
              )
              .join(" ")}
            fill="none"
            stroke={teamColor[path.team]}
            strokeWidth="1.5"
            opacity=".55"
          />
        ),
      )}
      {points.map((p) => (
        <g
          key={p.id}
          onClick={() => onSelect?.(p.id)}
          style={{ cursor: onSelect ? "pointer" : "default" }}
        >
          <circle
            cx={25 + p.x * 630}
            cy={25 + p.y * 400}
            r={selected === p.id ? 9 : 6}
            fill={teamColor[p.team]}
            stroke="#fff"
            strokeWidth="1.5"
          />
          {selected === p.id && (
            <circle
              cx={25 + p.x * 630}
              cy={25 + p.y * 400}
              r="15"
              fill="none"
              stroke="#fff"
            />
          )}
        </g>
      ))}
    </svg>
  );
}
