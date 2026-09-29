export type Team = "home" | "away" | "unknown";
export type Match = {
  id: string;
  title: string;
  home: string;
  away: string;
  date: string;
  duration: number;
  created: number;
  updated: number;
  status: string;
  revision: number;
  profile: string;
  sport: string;
};
export type Source = {
  id: string;
  name: string;
  kind: string;
  status: string;
  duration: number;
  width: number;
  height: number;
  poster?: string;
  path?: string;
  proxy?: string;
  offset: number;
  segments?: { id: string; path: string; start: number; end: number }[];
  gaps?: { after: number; reason: string }[];
};
export type Event = {
  id: string;
  kind: string;
  start: number;
  end: number | null;
  team: Team;
  player: string;
  status: "proposed" | "confirmed" | "rejected";
  note: string;
  origin: string;
  evidence?: string;
  score?: number | null;
  source_id?: string | null;
  excluded?: boolean;
};
export type Track = {
  id: string;
  kind: string;
  start: number;
  end: number;
  observed_seconds: number;
  samples: number;
  player: string;
  team: Team;
  role: string;
  path: number[][];
  team_hint?: string;
};
export type Job = {
  id: string;
  kind: string;
  status: string;
  progress: number;
  error?: string;
  cancel?: boolean;
  config: Record<string, unknown>;
  metrics?: {
    processed_frames?: number;
    processed_fps?: number;
    rss_mb?: number;
    analysis_delay?: number;
    sample_fps?: number;
    recorded_seconds?: number;
    segments?: number;
  };
  checkpoint?: { time: number };
};
export type Artifact = {
  id: string;
  kind: string;
  title: string;
  revision: number;
  created: number;
  duration?: number;
  files: Record<string, string>;
  boundary_note?: string;
};
export type Review = {
  events: Record<string, Event>;
  labels: unknown[];
  calibrations: {
    source_id: string;
    start: number;
    end: number;
    fit_error: number;
    image: number[][];
    field: number[][];
  }[];
  points: unknown[];
  exclusions: { start: number; end: number; reason: string }[];
  clock: { period: number; media_anchor: number; match_anchor: number };
};
export type Statistics = {
  players?: {
    player: string;
    team: Team;
    counts: Record<string, number>;
    observed_seconds: number;
  }[];
  score: Record<Team, number>;
  counts: Record<Team, Record<string, number>>;
  coverage_percent: number;
  coverage_seconds: number;
  unique_tracks: number;
  confirmed_events: number;
  proposed_events: number;
  reliability: string;
  spatial_note: string;
  possession: {
    seconds: Record<string, number>;
    percent: Record<Team, number | null>;
    denominator: number;
    reliability: string;
  };
};
export type Detail = {
  match: Match;
  sources: Source[];
  review: Review;
  events: Event[];
  statistics: Statistics;
  tracks: Track[];
  heatmap: Record<Team, number[][]>;
  jobs: Job[];
  exports: Artifact[];
  warnings: string[];
  active_runs: Record<string, string>;
};
export type Frame = {
  time: number;
  sample_interval: number;
  source_id: string;
  calibrated: boolean;
  excluded: boolean;
  tracks: {
    id: string;
    display_id: string;
    box: number[];
    ground_point: number[];
    field: number[] | null;
    team: Team;
    player: string;
    kind: string;
    role: string;
  }[];
};
export type System = {
  version: string;
  data_dir: string;
  disk_free: number;
  memory_total: number;
  model_ready: boolean;
  providers: string[];
  platform: string;
  capabilities: Record<string, string>;
};
