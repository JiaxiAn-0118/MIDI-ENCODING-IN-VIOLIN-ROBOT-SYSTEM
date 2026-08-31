import pytest

from violin_midi_json.fingering_planner import (
    GlobalFingeringPlanner,
    OnlineFingeringPlanner,
)
from violin_midi_json.models import MidiNote


def make_midi_note(pitch: int, start: float = 0.0, duration: float = 0.5) -> MidiNote:
    return MidiNote(start=start, end=start + duration, duration=duration, pitch=pitch, velocity=64)


def make_scale() -> list[MidiNote]:
    """A 弦上的上行音阶：A4 B4 C#5 D5 E5 F#5 G#5 A5。"""
    pitches = [69, 71, 73, 74, 76, 78, 80, 81]
    return [make_midi_note(p, i * 0.5) for i, p in enumerate(pitches)]


def test_window_larger_than_piece_flushes_to_global_plan():
    # 窗口大于整曲时，feed 阶段不提交，flush 一次性跑全局 DP，结果应与全局规划一致。
    notes = make_scale()
    online = OnlineFingeringPlanner(window_size=100, lookahead_size=4)
    assert online.feed(notes) == []
    flushed = online.flush()
    assert [f.fingering for f in flushed] == GlobalFingeringPlanner().plan(notes)


def test_feed_in_measures_commits_every_note_in_order():
    notes = make_scale()
    online = OnlineFingeringPlanner(window_size=4, lookahead_size=2)  # 每次提交 2 个
    committed = []
    for measure in [notes[:3], notes[3:6], notes[6:]]:
        committed.extend(online.feed(measure))
    committed.extend(online.flush())

    assert len(committed) == len(notes)
    for fingered, note in zip(committed, notes):
        assert fingered.note == note
        assert fingered.fingering.pitch == note.pitch
        assert fingered.fingering.string in ("G", "D", "A", "E")
        assert fingered.fingering.position in (1, 2, 3)
        assert fingered.fingering.finger in (0, 1, 2, 3, 4)


def test_flush_with_empty_buffer_returns_empty():
    online = OnlineFingeringPlanner()
    assert online.flush() == []


def test_invalid_window_config_raises():
    with pytest.raises(ValueError):
        OnlineFingeringPlanner(window_size=0, lookahead_size=0)
    with pytest.raises(ValueError):
        OnlineFingeringPlanner(window_size=4, lookahead_size=4)
    with pytest.raises(ValueError):
        OnlineFingeringPlanner(window_size=4, lookahead_size=-1)
