"""sample_timestamps() is the pure, DB-free half of services/video_frame_service.py —
these pin its trimming behavior (skip likely black intro/outro frames on anything long
enough to have a real "middle", fall back to an even split on very short clips) without
needing a real video to decode.
"""

from app.services.video_frame_service import sample_timestamps


def test_single_frame_returns_midpoint():
    assert sample_timestamps(100.0, 1) == [50.0]


def test_short_clip_uses_full_even_split_no_trim():
    # Under the 3s trim threshold: 0%-100%, not 5%-95%.
    result = sample_timestamps(2.0, 3)
    assert result == [0.0, 1.0, 2.0]


def test_long_clip_trims_first_and_last_five_percent():
    result = sample_timestamps(100.0, 3)
    assert result[0] == 5.0
    assert result[-1] == 95.0
    assert result == sorted(result)


def test_count_matches_requested_length():
    for count in (1, 2, 6, 10):
        assert len(sample_timestamps(60.0, count)) == count


def test_timestamps_are_evenly_spaced():
    result = sample_timestamps(100.0, 5)
    gaps = [round(b - a, 6) for a, b in zip(result, result[1:])]
    assert len(set(gaps)) == 1
