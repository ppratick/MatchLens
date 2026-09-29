from matchlens.live import live_policy


def test_overload_degrades_analysis_without_changing_recording():
    normal = live_policy(3, 5)
    assert normal.sample_fps == 5 and normal.visualizations and not normal.skip_stale
    slower = live_policy(9, 5)
    assert slower.sample_fps == 2.5 and slower.visualizations
    light = live_policy(15, 2.5)
    assert not light.visualizations and not light.skip_stale
    stale = live_policy(25, 1.25)
    assert stale.skip_stale and not stale.recording_only
    stopped = live_policy(65, 0.5)
    assert stopped.recording_only
    assert live_policy(30, 0.5).sample_fps == 0.5
