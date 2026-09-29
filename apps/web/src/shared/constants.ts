import type { Team } from "../types";
export const teamColor: Record<Team, string> = {
  home: "#ed815a",
  away: "#7aabfa",
  unknown: "#bec9bf",
};
export const labels: Record<string, string> = {
  goal: "Goal",
  shot: "Shot",
  pass: "Pass",
  turnover: "Turnover",
  save: "Save",
  possession: "Possession",
  note: "Note",
  period: "Period",
};
