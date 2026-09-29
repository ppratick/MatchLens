"""Analysis-only overload policy; it has no access to recording files or queues."""

from dataclasses import dataclass


@dataclass(frozen=True)
class LivePolicy:
    sample_fps: float
    visualizations: bool
    skip_stale: bool
    recording_only: bool


def live_policy(delay: float, sample_fps: float):
    reduced = max(0.5, sample_fps / 2) if delay > 8 else sample_fps
    return LivePolicy(
        sample_fps=min(sample_fps, reduced),
        visualizations=delay <= 12,
        skip_stale=delay > 20,
        recording_only=delay > 60 and sample_fps <= 0.5,
    )
